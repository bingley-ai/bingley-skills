"""ledger — the append-only record of what the sales skills actually made.

WHY THIS IS SEPARATE FROM THE BRAIN (read before changing anything here).

`sales-os-profile.json` answers "who is this user and what are they working on". It is small,
projected, and bounded: `wcontext.py` digests working-context history into a short newest-first
string inside the profile. That design is correct and it works. Pouring raw artefacts — every cold
email, every research pass — into `working-context.jsonl` would corrupt exactly that: the digest
would fill with volume and the signal would fall off the end.

So the ledger is a SECOND store that projects into NOTHING. It is written, never read by the
runtime, and never merged into the profile. Because it does not project, it needs no `brain_maps`
entry, no `wcontext` kind, and no BRAIN_LIB_VERSION bump — which is the whole reason adding it
cannot disturb a skill already wired to the brain.

WHAT IT IS FOR. Not making today's answer smarter. Today's answer must stay deterministic — the
cold-email rubric in particular is sold on same-email-same-score and is gated on it. The ledger is
for the question nobody has asked yet: "how has cold email changed over the last six months",
"which segments did we actually work", "what did we already research". You can add a reader any
time; you cannot recover six months you failed to store.

  * Append-only. Nothing here is ever updated or rewritten.
  * Every event carries a stable `id`, returned by `append`. Later events reference it with `--of`,
    which is how an outcome is tied to the exact artefact that produced it. Found in the 21 Aug
    soak: joining on a human subject line is ambiguous the moment one subject has a before AND an
    after, and "which one did you actually send" is the only question that makes an outcome worth
    storing.
  * Raw, not summarised. A summary answers only the question you thought of today.
  * Monthly files (`ledger/YYYY-MM.jsonl`) so it never becomes one unopenable blob.
  * Its own flock — it must never contend with a brain write.
  * NEVER FATAL. Every failure path returns status and exits 0. A skill's real work must not die
    because an archive write failed (the working folder may be unmounted, or the FUSE mount may
    refuse the write — both seen in the wild).
  * Opt out by creating `ledger/.disabled`; deleting the `ledger/` dir is the delete path. Both are
    honoured silently.

CLI:
  python3 ledger.py append --base <hq> --skill cold-email --kind email.graded \\
      --subject "Acme outreach v2" --text "<the artefact>" --meta score=74 --meta archetype=pitch-slap
  python3 ledger.py append --base <hq> --skill list-builder --kind list.built \\
      --subject "UK dental SaaS" --ref "/path/to/list.xlsx" --meta rows=212
  python3 ledger.py append --base <hq> --skill cold-email --kind email.outcome \\
      --of 9f2c1a4be0d7 --meta outcome="replied in 2h, booked"
  python3 ledger.py read  --base <hq> [--skill S] [--kind K] [--since YYYY-MM] [--limit N] [--of ID]
  python3 ledger.py stats --base <hq>

KIND CONVENTION: `<noun>.<pastTenseVerb>`, lowercase, dot-separated — `email.graded`, `email.built`,
`company.researched`, `list.built`, `book.graded`, `sitting.ruled`. Keep them stable; a renamed kind
splits the dataset you are trying to mine.
"""
from __future__ import annotations
import contextlib
import fcntl
import json
import os
import sys
import time
import uuid
from pathlib import Path

LEDGER_VERSION = 1
DIR_NAME = "ledger"
DISABLED = ".disabled"

# A single payload cap. Generous for any real artefact (an email is ~1KB, a long research note
# ~20KB) and small enough that one pasted novel cannot bloat a month file. Over the cap the text is
# stored truncated with `truncated: true` — the event is never dropped, because knowing an oversized
# artefact existed is itself worth keeping.
MAX_TEXT = 262_144


def _ledger_dir(base) -> Path:
    return Path(base) / DIR_NAME


@contextlib.contextmanager
def _flock(d: Path):
    """Own lock file, deliberately NOT the brain's .lock — an archive write must never block or be
    blocked by a profile write."""
    lf = open(d / ".lock", "w")
    try:
        fcntl.flock(lf, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lf, fcntl.LOCK_UN)
        lf.close()


def _fingerprint(path: str) -> dict:
    """Enough to notice later that a referenced file has moved, changed or gone."""
    try:
        st = os.stat(path)
        return {"bytes": st.st_size, "mtime": round(st.st_mtime, 3)}
    except OSError:
        return {"missing": True}


def append(base, skill, kind, subject=None, text=None, ref=None, meta=None, of=None) -> dict:
    """Append one event. Returns a status dict including its `id`. NEVER raises."""
    try:
        if not skill or not kind:
            return {"written": False, "reason": "skill and kind are both required"}

        d = _ledger_dir(base)
        if (d / DISABLED).exists():
            return {"written": False, "reason": "ledger disabled by the user (ledger/.disabled)"}
        d.mkdir(parents=True, exist_ok=True)

        truncated = False
        if text is not None:
            text = str(text)
            if len(text) > MAX_TEXT:
                text, truncated = text[:MAX_TEXT], True

        now = time.time()
        event = {
            "v": LEDGER_VERSION,
            "id": uuid.uuid4().hex[:12],
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
            "epoch": round(now, 3),
            "skill": str(skill),
            "kind": str(kind),
            "subject": (str(subject) if subject is not None else None),
            "text": text,
            "ref": (str(ref) if ref else None),
            "of": (str(of) if of else None),
            "meta": dict(meta or {}),
        }
        if truncated:
            event["truncated"] = True
        if ref:
            event["ref_fingerprint"] = _fingerprint(str(ref))

        month = time.strftime("%Y-%m", time.localtime(now))
        path = d / ("%s.jsonl" % month)
        line = json.dumps(event, ensure_ascii=False) + "\n"
        with _flock(d):
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        return {"written": True, "id": event["id"], "path": str(path), "kind": event["kind"],
                "bytes": len(line.encode("utf-8")), "truncated": truncated}
    except Exception as e:                                   # noqa: BLE001 - never fatal, by design
        return {"written": False, "reason": "%s: %s" % (type(e).__name__, e)}


def read(base, skill=None, kind=None, since=None, limit=None, of=None) -> dict:
    """Read events back, oldest first. The mining entry point; nothing at runtime calls it."""
    try:
        d = _ledger_dir(base)
        if not d.is_dir():
            return {"events": [], "months": [], "reason": "no ledger yet"}
        months = sorted(p.stem for p in d.glob("*.jsonl"))
        if since:
            months = [m for m in months if m >= since]
        out = []
        for m in months:
            for raw in (d / ("%s.jsonl" % m)).read_text(encoding="utf-8").splitlines():
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    e = json.loads(raw)
                except ValueError:
                    continue                                  # a torn line never breaks a read
                if skill and e.get("skill") != skill:
                    continue
                if kind and e.get("kind") != kind:
                    continue
                if of and e.get("of") != of and e.get("id") != of:
                    continue
                out.append(e)
        if limit:
            out = out[-int(limit):]
        return {"events": out, "months": months, "count": len(out)}
    except Exception as e:                                   # noqa: BLE001
        return {"events": [], "reason": "%s: %s" % (type(e).__name__, e)}


def stats(base) -> dict:
    r = read(base)
    ev = r.get("events") or []
    by_skill, by_kind = {}, {}
    for e in ev:
        by_skill[e.get("skill")] = by_skill.get(e.get("skill"), 0) + 1
        by_kind[e.get("kind")] = by_kind.get(e.get("kind"), 0) + 1
    d = _ledger_dir(base)
    size = sum(p.stat().st_size for p in d.glob("*.jsonl")) if d.is_dir() else 0
    return {"total": len(ev), "months": r.get("months") or [], "bytes": size,
            "by_skill": by_skill, "by_kind": by_kind,
            "disabled": (d / DISABLED).exists()}


def _main(argv) -> int:
    if not argv:
        print(json.dumps({"error": "usage: ledger.py append|read|stats --base <hq> ..."}))
        return 0
    verb, argv = argv[0], argv[1:]
    base = skill = kind = subject = text = ref = since = limit = of = None
    meta = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        nxt = argv[i + 1] if i + 1 < len(argv) else None
        if a == "--base" and nxt is not None:
            base = nxt; i += 2; continue
        if a == "--skill" and nxt is not None:
            skill = nxt; i += 2; continue
        if a == "--kind" and nxt is not None:
            kind = nxt; i += 2; continue
        if a == "--subject" and nxt is not None:
            subject = nxt; i += 2; continue
        if a == "--text" and nxt is not None:
            text = nxt; i += 2; continue
        if a == "--file" and nxt is not None:
            try:
                text = Path(nxt).read_text(encoding="utf-8")
            except OSError as e:
                print(json.dumps({"written": False, "reason": "could not read --file: %s" % e}))
                return 0
            i += 2; continue
        if a == "--ref" and nxt is not None:
            ref = nxt; i += 2; continue
        if a == "--since" and nxt is not None:
            since = nxt; i += 2; continue
        if a == "--limit" and nxt is not None:
            limit = nxt; i += 2; continue
        if a == "--of" and nxt is not None:
            of = nxt; i += 2; continue
        if a == "--meta" and nxt is not None:
            k, _, v = nxt.partition("=")
            if k:
                meta[k] = v
            i += 2; continue
        i += 1

    if not base:
        print(json.dumps({"written": False, "reason": "missing --base"}))
        return 0
    if verb == "append":
        print(json.dumps(append(base, skill, kind, subject, text, ref, meta, of),
                         ensure_ascii=False))
    elif verb == "read":
        print(json.dumps(read(base, skill, kind, since, limit, of), ensure_ascii=False))
    elif verb == "stats":
        print(json.dumps(stats(base), ensure_ascii=False))
    else:
        print(json.dumps({"error": "unknown verb %r" % verb}))
    return 0                                    # ALWAYS 0 — a shell chain must never break on this


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
