"""wcontext — Tier-B/C working-context store (added in BRAIN_LIB_VERSION 3).

Identity lives in the brain (sales-os-profile.json). What the user is WORKING ON lives here:
an append-only, dated JSONL — so "recency-weighted" is real (dated entries, newest first),
history is never overwritten, and the brain's workingContext.* string keys become bounded
DIGESTS derived from this file. Back-compat: old readers of the brain keys still see a value,
now a dated newest-first digest instead of one last-write-wins fragment.

File: <base>/working-context.jsonl — one JSON object per line:
  {"ts": <epoch>, "date": "YYYY-MM-DD", "kind": "win", "text": "...", "skill": "cold-email"}

Kinds: campaign · target · objection · win · note.
DURABLE entries — a `note` whose text starts with "disqualifier" or "sign-off"/"signoff" —
are exempt from age expiry and the per-kind cap: they power list filtering and tone and must
never be silently rotated out by ambient chatter.

Pure append + bounded read. No locks needed for append (O_APPEND single-line writes); digests
are advisory views, never a source of truth.
"""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from pathlib import Path

FILE_NAME = "working-context.jsonl"

# brain_bridge field -> kind
KIND_FOR_FIELD = {
    "wcCampaigns": "campaign",
    "wcTargets": "target",
    "wcObjections": "objection",
    "wcWins": "win",
    "wcNotes": "note",
}

PER_KIND = 6            # newest N entries per kind in a digest
MAX_AGE_DAYS = 90       # older entries drop out of digests (log keeps everything)
MAX_DIGEST_CHARS = 700  # hard cap per kind so brain values stay bounded

_DURABLE_PREFIXES = ("disqualifier", "sign-off", "signoff")


def _path(base):
    return Path(base) / FILE_NAME


def exists(base):
    return _path(base).exists()


def _durable(entry):
    t = (entry.get("text") or "").strip().lower()
    return any(t.startswith(p) for p in _DURABLE_PREFIXES)


def add(base, kind, text, skill="chat"):
    """Append one dated entry. Returns the entry. Creates the file (and base dir) on first write."""
    if kind not in set(KIND_FOR_FIELD.values()):
        raise ValueError(f"unknown working-context kind {kind!r}")
    text = (text or "").strip()
    if not text:
        return None
    p = _path(base)
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = time.time()
    entry = {"ts": ts, "date": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d"),
             "kind": kind, "text": text, "skill": skill}
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def _load(base):
    p = _path(base)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue                       # one bad line never sinks a read
        if isinstance(e, dict) and e.get("kind") and e.get("text"):
            out.append(e)
    return out


def digest(base, kind, per_kind=PER_KIND, max_age_days=MAX_AGE_DAYS):
    """Newest-first list of entries for `kind`: the newest `per_kind` non-durable entries
    within `max_age_days`, plus ALL durable entries (any age). Deduped on exact text."""
    cutoff = time.time() - max_age_days * 86400
    seen, fresh, durable = set(), [], []
    for e in sorted(_load(base), key=lambda e: e.get("ts", 0), reverse=True):
        if e.get("kind") != kind:
            continue
        key = e.get("text", "").strip().lower()
        if key in seen:
            continue
        seen.add(key)
        if _durable(e):
            durable.append(e)
        elif e.get("ts", 0) >= cutoff and len(fresh) < per_kind:
            fresh.append(e)
    return durable + fresh                 # durable first (they're the standing facts)


def digest_text(base, kind):
    """The bounded string form written into the brain's workingContext.* key:
    one '[YYYY-MM-DD] text' line per entry, durable first then newest-first, capped."""
    lines, total = [], 0
    for e in digest(base, kind):
        line = f"[{e.get('date', '?')}] {e.get('text', '').strip()}"
        if total + len(line) + 1 > MAX_DIGEST_CHARS and lines:
            break
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines)
