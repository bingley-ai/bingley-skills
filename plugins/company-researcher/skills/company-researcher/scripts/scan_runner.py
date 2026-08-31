#!/usr/bin/env python3
"""scan_runner.py — the OVERNIGHT ENGINE for Full Accounts Scan.

This is orchestration only. It does NOT change what the user sees: the rendered
artefact still comes from `render_instance.py` against the same DATA schema, with the
same ranked dashboard, same GO/maybe/skip, same per-company cheat-sheet cards. This
file just lets a big book (≈1,000–4,000 companies) run as up to 5 concurrent agents,
checkpoint each company to disk, and resume after a crash instead of restarting.

Why it exists (see Second Brain/"Whole-Book Scan - design (21 Jun 2026).md"):
  * PARALLEL FAN-OUT (max 5). `plan` splits the deduped book into ≤5 shards. The
    driving agent spawns one Task sub-agent per shard. The cap is structural — there
    are never more than 5 shard files, so there are never more than 5 workers.
  * CHECKPOINT / RESUME. Each shard owns its OWN append-only log
    (run/<run_id>/shard-NN.log.jsonl). Each company moves through a small state
    machine: queued -> researched -> done  (or  nogo_done / failed). A worker calls
    `mark` after each step; the agent crashing mid-book loses at most the one
    in-flight company. On restart, `next` replays the shard log, takes each
    company's LAST state, and hands back only the companies not yet terminal —
    so the run resumes from where it died, never from the top.
  * DEDUPE BY DOMAIN. `plan` normalises domains and drops duplicates BEFORE sharding,
    so the same company is never researched twice even across overlapping input rows.
  * TIME ESTIMATE. `estimate` (also printed by `plan`) gives an honest hours range
    from accounts ÷ throughput ÷ agents, throughput ≈ 15–25 accounts/hr per agent.

It REUSES the proven brainstore machinery (atomic temp-file+replace writes, fsync,
file lock) rather than reinventing durability — the same append-only/derived-view
pattern. Per-company state lives in the SHARD log (sharded, not one giant log) so
replay on resume is O(shard) not O(book²) — exactly the design's anti-O(n²) note.

Free web data only: there is NO Apollo, no credits, no budget governor, no enrich
pass. The state machine is therefore just research -> done, with nogo_done for an
instant SKIP (hard disqualifier) and failed for an unrecoverable company.

CLI (all print JSON unless noted):
  python3 scan_runner.py estimate --count 1800 [--agents 5]
  python3 scan_runner.py plan  --in book.json   --run-dir <dir> [--agents 5] [--run-id RID]
  python3 scan_runner.py next  --run-dir <dir>  --shard 0
  python3 scan_runner.py mark  --run-dir <dir>  --shard 0 --key acme.com --state researched
      (pass the exact `key` that `next` returned; for a domain-less company that is
       'name:<slug>'. --domain still works for companies keyed by a real domain. An
       unknown/blank key is a hard error, never a silent no-op.)
  python3 scan_runner.py status --run-dir <dir>
  python3 scan_runner.py merge --run-dir <dir>  [--out companies.json]

`book.json` is a JSON list of input rows, each {"name": "...", "domain": "..."} (domain
optional; either field may carry the company). This is the same list the agent already
parses from the pasted list / dropped Excel — scan_runner just shards and tracks it.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
import math
import tempfile
import contextlib
import fcntl
from pathlib import Path

# ---- state machine -------------------------------------------------------------
# queued      : known, not started
# researched  : full deep research captured (the company's `scan` + card DATA written)
# done        : terminal — researched and committed to the merge store
# nogo_done   : terminal — instant SKIP via Step-0 hard disqualifier, no full research spent
# failed      : terminal — could not be completed (data dead-end / repeated error); never retried blindly
STATES = ("queued", "researched", "done", "nogo_done", "failed")
TERMINAL = {"done", "nogo_done", "failed"}

# MEASURED throughput (3-company live run, 30 Jul 2026): a full per-company deep pass took
# 230-235s wall-clock per worker (~10-17 WebSearch + ~11-15 WebFetch each), i.e. ~15-19/hr.
# Band widened to 15-25 to allow for thin/obvious companies. Do NOT raise these without a
# fresh measured run -- the old 90-130 was a design guess and overstated speed by ~7x.
THROUGHPUT_LOW = 15.0     # accounts/hr/agent  (slow end -> the LONGER time estimate)
THROUGHPUT_HIGH = 25.0    # accounts/hr/agent  (fast end -> the SHORTER time estimate)
MAX_AGENTS = 5            # HARD CAP. Never more than 5 concurrent workers.


# ---- durability primitives (same pattern as brainstore.py) ---------------------
@contextlib.contextmanager
def _flock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lf = open(path, "w")
    try:
        fcntl.flock(lf, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lf, fcntl.LOCK_UN)
        lf.close()


def _append(log: Path, event: dict):
    """Append one event to a shard log, fsynced — crash-durable, the checkpoint write."""
    log.parent.mkdir(parents=True, exist_ok=True)
    event.setdefault("ts", time.time())
    with open(log, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _atomic_write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _read_lines(p: Path):
    if not p.exists():
        return []
    out = []
    dropped = 0
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            dropped += 1  # one bad line never sinks the replay
    if dropped:
        # a corrupt/truncated line is rare (a crash mid-append), but must be VISIBLE not silent:
        # a dropped `add` line would otherwise remove a company from the run with zero trace.
        print(f"WARN: scan_runner: {dropped} unparseable line(s) skipped in {p.name} "
              f"(possible crash-truncated checkpoint — a dropped 'add' means a company went missing).",
              file=sys.stderr)
    return out


# ---- identity / dedupe ---------------------------------------------------------
def norm_domain(row: dict) -> str:
    """Stable dedupe key for a company. Prefer the domain; fall back to a slug of the name.
    Strips scheme / www / path / port and lower-cases, so 'https://www.Acme.com/x' and
    'acme.com' collapse to the same company and are never researched twice."""
    raw = (row.get("domain") or "").strip().lower()
    if raw:
        raw = raw.split("//")[-1]            # drop scheme
        raw = raw.split("/")[0]              # drop path
        raw = raw.split("?")[0].split("#")[0]
        raw = raw.split(":")[0]              # drop port
        if raw.startswith("www."):
            raw = raw[4:]
        raw = raw.strip(".")
        if raw:
            return raw
    name = (row.get("name") or "").strip().lower()
    slug = "".join(c if c.isalnum() else "-" for c in name).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return ("name:" + slug) if slug else ""


def dedupe(rows: list) -> list:
    """Drop duplicate companies by normalised domain, keeping first occurrence and the
    richest name/domain seen. Rows with no usable identity are dropped (can't track them)."""
    seen, out = {}, []
    for r in rows:
        if not isinstance(r, dict):
            # a bare string is a legitimate company name (pasted-list input); null / numbers /
            # bools / blank strings are junk rows (e.g. a stray empty Excel row → JSON null) —
            # drop them, never manufacture a phantom company literally named "None" / "123".
            if isinstance(r, str) and r.strip():
                s = r.strip()
                # a bare token that LOOKS like a domain (no spaces, has a dot, optional scheme/path)
                # is a domain, not a name — so it dedupes against {domain:…} rows for the same
                # company instead of becoming a separate name:<slug> row.
                probe = s.lower().split("//")[-1].split("/")[0]
                r = {"domain": s} if re.match(r"^[a-z0-9][a-z0-9-]*(\.[a-z0-9-]+)+$", probe) else {"name": s}
            else:
                continue
        key = norm_domain(r)
        if not key:
            continue
        # store the CLEAN domain the render/logo contract expects (scheme/www/path/port already
        # stripped by norm_domain), never the raw first-seen URL. name-only rows carry no domain.
        clean_domain = key if not key.startswith("name:") else ""
        if key in seen:
            # enrich the kept row with any field the dup fills in
            kept = seen[key]
            if not kept.get("domain") and clean_domain:
                kept["domain"] = clean_domain
            if not kept.get("name") and r.get("name"):
                kept["name"] = r["name"]
            continue
        rec = {"key": key, "name": r.get("name", ""), "domain": clean_domain}
        seen[key] = rec
        out.append(rec)
    return out


# ---- time estimate -------------------------------------------------------------
def estimate(count: int, agents: int) -> dict:
    agents = max(1, min(int(agents), MAX_AGENTS))
    count = max(0, int(count))
    # hours = accounts / (per-agent throughput) / agents.  Low throughput -> high hours.
    hi_hours = count / (THROUGHPUT_LOW * agents) if count else 0.0
    lo_hours = count / (THROUGHPUT_HIGH * agents) if count else 0.0
    return {
        "accounts": count,
        "agents": agents,
        "throughput_per_agent": [THROUGHPUT_LOW, THROUGHPUT_HIGH],
        "hours_low": round(lo_hours, 1),
        "hours_high": round(hi_hours, 1),
        "human": _human_range(lo_hours, hi_hours, count, agents),
    }


def _human_range(lo, hi, count, agents):
    if count == 0:
        return "nothing to scan."
    def fmt(h):
        if h < 1:
            m = int(round(h * 60))
            return "<1 min" if m < 1 else f"~{m} min"   # never print the nonsensical "~0 min"
        return f"~{h:.1f} hr"
    nights = "" if hi <= 9 else f"  Won't finish in one night — plan {math.ceil(hi / 8)} scheduled nights (the dashboard ships partial after night one)."
    return (f"{count} companies across {agents} agent(s): roughly {fmt(lo)}–{fmt(hi)} "
            f"(≈{int(THROUGHPUT_LOW)}–{int(THROUGHPUT_HIGH)}/hr per agent).{nights}")


# ---- plan / shard --------------------------------------------------------------
def _shard_log(run_dir: Path, shard: int) -> Path:
    return run_dir / f"shard-{shard:02d}.log.jsonl"


def _manifest_path(run_dir: Path) -> Path:
    return run_dir / "manifest.json"


def plan(rows: list, run_dir: Path, agents: int, run_id: str | None) -> dict:
    """Dedupe -> shard into ≤MAX_AGENTS shards -> seed each shard log with `queued` events
    for any company not already present (idempotent: re-running plan on the same run_dir adds
    only genuinely new companies, never duplicates an existing checkpoint). Returns the plan
    + the time estimate. The agent reads `shards` and spawns one sub-agent per shard."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    agents = max(1, min(int(agents), MAX_AGENTS))
    companies = dedupe(rows)

    # Round-robin assignment is stable: company key -> shard. Re-planning keeps each company
    # on its original shard, so resume + add-more-companies both work without reshuffling.
    # Never shrink the shard count on a re-plan: a smaller follow-up book (e.g. "add these 2")
    # must not collapse n_shards below the width already on disk, or status/fan-out would
    # orphan pending work on the higher shards. Floor to the prior manifest + on-disk shards.
    prior = 0
    _mp = _manifest_path(run_dir)
    if _mp.exists():
        try:
            prior = int((json.loads(_mp.read_text() or "{}")).get("n_shards") or 0)
        except Exception:
            prior = 0
    prior = max(prior, len(list(run_dir.glob("shard-*.log.jsonl"))))
    n_shards = min(MAX_AGENTS, max(min(agents, max(1, len(companies))), prior))
    assign = {c["key"]: (i % n_shards) for i, c in enumerate(companies)}

    with _flock(run_dir / ".lock"):
        # what's already checkpointed (so a re-plan is additive, never duplicating)
        existing = set()
        for s in range(n_shards):
            for ev in _read_lines(_shard_log(run_dir, s)):
                if ev.get("op") == "add" and ev.get("key"):
                    existing.add(ev["key"])
        added = 0
        for c in companies:
            if c["key"] in existing:
                continue
            s = assign[c["key"]]
            _append(_shard_log(run_dir, s), {
                "op": "add", "key": c["key"], "name": c["name"],
                "domain": c["domain"], "state": "queued"})
            added += 1

        manifest = {
            "run_id": run_id or f"scan-{int(time.time())}",
            "agents": agents, "n_shards": n_shards,
            "total_companies": len(companies), "added_this_plan": added,
            "shards": list(range(n_shards)),
            "max_agents": MAX_AGENTS,
            "created": time.time(),
        }
        _atomic_write(_manifest_path(run_dir), json.dumps(manifest, indent=2, ensure_ascii=False))

    est = estimate(len(companies), agents)
    return {**manifest, "estimate": est,
            "note": f"Spawn ONE sub-agent per shard (0..{n_shards-1}). HARD CAP {MAX_AGENTS} concurrent."}


# ---- replay current state of a shard -------------------------------------------
def _shard_state(run_dir: Path, shard: int) -> dict:
    """Replay one shard log -> {key: {name, domain, state}} with each company's LAST state.
    This IS the resume mechanism: terminal companies are skipped, the rest are worklist."""
    state = {}
    for ev in _read_lines(_shard_log(run_dir, shard)):
        key = ev.get("key")
        if not key:
            continue
        op = ev.get("op")
        if op == "add":
            state.setdefault(key, {"name": ev.get("name", ""), "domain": ev.get("domain", ""),
                                   "state": "queued"})
        elif op == "mark":
            rec = state.setdefault(key, {"name": ev.get("name", ""), "domain": ev.get("domain", ""),
                                         "state": "queued"})
            st = ev.get("state")
            if st in STATES:
                rec["state"] = st
            if ev.get("data") is not None:
                rec["data"] = ev["data"]
    return state


def next_work(run_dir: Path, shard: int) -> dict:
    """Return the companies in this shard NOT yet terminal (queued or researched), in order.
    On a fresh start that's all of them; after a crash it's only the unfinished tail."""
    run_dir = Path(run_dir)
    st = _shard_state(run_dir, shard)
    pending = [{"key": k, "name": v["name"], "domain": v["domain"], "state": v["state"]}
               for k, v in st.items() if v["state"] not in TERMINAL]
    done = sum(1 for v in st.values() if v["state"] in TERMINAL)
    return {"shard": shard, "total": len(st), "done": done,
            "pending_count": len(pending), "pending": pending}


def mark(run_dir: Path, shard: int, domain_key: str, state: str, data=None, key: str | None = None) -> dict:
    """Checkpoint one company's new state to its shard log (append-only, fsynced).
    Resolve the key from `--key` (preferred: the exact key `next` returned, REQUIRED for
    domain-less companies whose key is 'name:<slug>') or by normalising `--domain`.
    Optionally carries the company's rendered card DATA so `merge` can assemble the output."""
    if state not in STATES:
        raise SystemExit(f"ERROR: state must be one of {STATES}")
    run_dir = Path(run_dir)
    if key:
        resolved = key.strip()
    else:
        dk = (domain_key or "").strip()
        resolved = dk if dk.startswith("name:") else norm_domain({"domain": dk})
    log = _shard_log(run_dir, shard)
    with _flock(run_dir / ".lock"):
        # Validate the key against what `plan` actually added to THIS shard, and carry forward
        # its name/domain so the mark is self-describing. Marking an unknown/blank key is a hard
        # error, never a silent no-op: a mismatched or empty key would otherwise strand the real
        # company in `queued` forever (or write a disconnected phantom) while reporting success.
        adds = {}
        for ev in _read_lines(log):
            if ev.get("op") == "add" and ev.get("key"):
                adds[ev["key"]] = {"name": ev.get("name", ""), "domain": ev.get("domain", "")}
        if resolved not in adds:
            raise SystemExit(
                f"ERROR: mark got key {resolved!r}, which was never planned into shard {shard}. "
                f"Pass the exact `key` field that `next` returned — use --key for domain-less "
                f"companies (their key looks like 'name:<slug>'). Nothing was written.")
        meta = adds[resolved]
        ev = {"op": "mark", "key": resolved, "state": state, **meta}
        if data is not None:
            ev["data"] = data
        _append(log, ev)
    return {"shard": shard, "key": resolved, "state": state}


# ---- status / merge ------------------------------------------------------------
def status(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    man = {}
    if _manifest_path(run_dir).exists():
        man = json.loads(_manifest_path(run_dir).read_text())
    n_shards = man.get("n_shards") or _count_shards(run_dir)
    counts = {s: 0 for s in STATES}
    per_shard = []
    total = 0
    for s in range(n_shards):
        st = _shard_state(run_dir, s)
        sc = {k: 0 for k in STATES}
        for v in st.values():
            sc[v["state"]] = sc.get(v["state"], 0) + 1
            counts[v["state"]] += 1
        total += len(st)
        per_shard.append({"shard": s, "total": len(st), **sc})
    terminal = sum(counts[k] for k in TERMINAL)
    return {"run_id": man.get("run_id"), "total": total,
            "terminal": terminal, "remaining": total - terminal,
            "pct_complete": round(100 * terminal / total, 1) if total else 0.0,
            "states": counts, "per_shard": per_shard}


def _count_shards(run_dir: Path) -> int:
    return len(list(Path(run_dir).glob("shard-*.log.jsonl"))) or 1


def _skip_card(v: dict, key: str) -> dict:
    """Minimal DATA card for an instant-SKIP (nogo_done) company that carries no researched
    card. Keeps disqualified firms VISIBLE in the ranked dashboard as a 'skip' row instead of
    silently dropping them, so the output stays identical to the serial path (which always
    renders a row per company). Schema-compatible: name/domain + a `scan` object with verdict
    SKIP and score 0, exactly what the ranked-list view reads."""
    name = v.get("name") or (key[5:] if key.startswith("name:") else key)
    return {
        "name": name,
        "domain": v.get("domain", ""),
        "summary": "",
        "scan": {"score": 0, "verdict": "SKIP",
                 "buyer": False,
                 "why": v.get("why") or "Hard disqualifier (competitor, geography, or excluded business model)."},
    }


def merge(run_dir: Path) -> list:
    """Assemble the final `companies` list from every shard's checkpoint data, deduped by key.
    Companies marked done/researched contribute their stored card DATA (the same per-company
    object the DATA schema expects, INCLUDING its `scan` object). nogo_done companies contribute
    a synthesised SKIP row when they carry no card (instant disqualifier, no research spent), so
    they still appear in the ranked list. failed companies are omitted. This list goes straight
    into render_instance.py — the output and schema are unchanged; merge only re-collects (and,
    for bare nogo, reconstructs) what the workers produced."""
    run_dir = Path(run_dir)
    n_shards = _count_shards(run_dir)
    out, seen, cardless_done = [], set(), []
    for s in range(n_shards):
        st = _shard_state(run_dir, s)
        for key, v in st.items():
            if key in seen:
                continue
            if v["state"] == "failed":
                continue
            card = v.get("data")
            if card is None:
                if v["state"] == "nogo_done":
                    seen.add(key)
                    out.append(_skip_card(v, key))   # keep the SKIP visible in the dashboard
                elif v["state"] == "done":
                    cardless_done.append(key)  # committed done but no card attached (worker bug)
                continue  # queued/researched with no card captured yet: nothing to render
            seen.add(key)
            out.append(card)
    if cardless_done:
        # a `done` company with no card silently vanishes from the dashboard — surface it, don't hide it.
        print(f"WARN: scan_runner merge: {len(cardless_done)} company(ies) marked 'done' with no "
              f"card data, omitted from output: {cardless_done[:8]}", file=sys.stderr)
    # Enforce the ranked order HERE (band: Strong→Fair→Longshot, then score desc within band), so
    # the rendered list and 'Save all PDF' overview can never come out in shard/completion order.
    # Stable sort: companies with no scan (e.g. an unranked index) keep insertion order at the end.
    band = {"GO": 0, "MAYBE": 1, "SKIP": 2}
    def _rank(card):
        sc = card.get("scan") or {}
        v = str(sc.get("verdict") or "").upper()
        score = sc.get("score")
        score = score if isinstance(score, (int, float)) and not isinstance(score, bool) else -1
        return (band.get(v, 3), -score)
    out.sort(key=_rank)
    return out


# ---- CLI -----------------------------------------------------------------------
def _load_rows(path: str) -> list:
    if path == "-":
        data = json.load(sys.stdin)
    else:
        data = json.loads(Path(path).read_text())
    if isinstance(data, dict) and "companies" in data:
        data = data["companies"]
    if not isinstance(data, list):
        raise SystemExit("ERROR: --in must be a JSON list of {name, domain} rows")
    return data


def main(argv):
    ap = argparse.ArgumentParser(description="Full Accounts Scan overnight engine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("estimate")
    pe.add_argument("--count", type=int, required=True)
    pe.add_argument("--agents", type=int, default=MAX_AGENTS)

    pp = sub.add_parser("plan")
    pp.add_argument("--in", dest="infile", required=True)
    pp.add_argument("--run-dir", required=True)
    pp.add_argument("--agents", type=int, default=MAX_AGENTS)
    pp.add_argument("--run-id", default=None)

    pn = sub.add_parser("next")
    pn.add_argument("--run-dir", required=True)
    pn.add_argument("--shard", type=int, required=True)

    pm = sub.add_parser("mark")
    pm.add_argument("--run-dir", required=True)
    pm.add_argument("--shard", type=int, required=True)
    pm.add_argument("--domain", default=None, help="company's domain (back-compat; normalised to the key)")
    pm.add_argument("--key", default=None,
                    help="exact key `next` returned (REQUIRED for domain-less companies: 'name:<slug>')")
    pm.add_argument("--state", required=True)
    pm.add_argument("--data", default=None, help="path to JSON card data, or '-' for stdin")

    ps = sub.add_parser("status")
    ps.add_argument("--run-dir", required=True)

    pg = sub.add_parser("merge")
    pg.add_argument("--run-dir", required=True)
    pg.add_argument("--out", default=None)

    a = ap.parse_args(argv)

    if a.cmd == "estimate":
        print(json.dumps(estimate(a.count, a.agents), ensure_ascii=False, indent=2))
    elif a.cmd == "plan":
        rows = _load_rows(a.infile)
        print(json.dumps(plan(rows, Path(a.run_dir), a.agents, a.run_id),
                         ensure_ascii=False, indent=2))
    elif a.cmd == "next":
        print(json.dumps(next_work(Path(a.run_dir), a.shard), ensure_ascii=False, indent=2))
    elif a.cmd == "mark":
        data = None
        if a.data == "-":
            data = json.load(sys.stdin)
        elif a.data:
            data = json.loads(Path(a.data).read_text())
        if not a.key and not a.domain:
            raise SystemExit("ERROR: mark needs --key (preferred: the exact key from `next`) or --domain")
        print(json.dumps(mark(Path(a.run_dir), a.shard, a.domain or "", a.state, data, a.key),
                         ensure_ascii=False, indent=2))
    elif a.cmd == "status":
        print(json.dumps(status(Path(a.run_dir)), ensure_ascii=False, indent=2))
    elif a.cmd == "merge":
        companies = merge(Path(a.run_dir))
        if a.out:
            _atomic_write(Path(a.out), json.dumps(companies, ensure_ascii=False, indent=2))
            print(json.dumps({"merged": len(companies), "out": a.out}, ensure_ascii=False))
        else:
            print(json.dumps(companies, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
