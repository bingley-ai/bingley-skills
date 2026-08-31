"""brain_bridge — the ONE generic skill<->brain integration layer (M3, generalised in the
simplification pass).

A skill never talks to the brain files directly. It calls this with its name; the per-skill
field map lives as DATA in `brain_maps.py`. Adding a skill in M4 = add a map entry, reuse this
file unchanged. One tested read/write path for every skill.

Contract (unchanged from the cold-email bridge it replaces):
  * READ order, per field: brain (`sales-os-profile.json`) -> the skill's legacy file -> schema
    default. Brain wins only where it actually holds a value (raw projection, so a default never
    masquerades as a real value). Defaults come from schema.py (single source of truth).
  * WRITES go to the BRAIN only; legacy files are a read-only safety net (never written here).
  * NON-BREAKING: with no brain on disk, reads create NOTHING and return exactly today's
    legacy/default behaviour. Only a write creates the brain (the first deposit).
  * Operational "force" fields (a skill's `force` set, e.g. capture flags) always apply and a
    `+N` value increments — so a bump can never be silently rejected and always reports the
    stored truth. Everything else keeps normal provenance precedence.

CLI (what the prose skill calls), two verbs, both print JSON:
  python3 brain_bridge.py get  --skill cold-email --base <wf>
  python3 brain_bridge.py save --skill cold-email --base <wf> product="..." lens=B2C deepSkips=+1
  python3 brain_bridge.py save --skill sales-setup --source inferred --base <wf> audience="..."

Notes:
  * `save` REQUIRES an explicit --skill (no silent default — a forgotten --skill used to
    silently drop every field not in the cold-email map).
  * `--source inferred` writes non-force fields as source="skill"/Inferred instead of
    user/High — for site-inferred fills of questions the user SKIPPED, so a machine guess
    never masquerades as user-confirmed identity. Any later real answer overrides it.
  * The save result includes "dropped": [...] listing any field names that are not in the
    skill's map (typos, unmapped fields) — they are NOT written; nothing is silent.
  * `--confirmed` (v3): REQUIRED to replace an existing user-confirmed IDENTITY value
    (business.* or wedge). Without it, such a write is downgraded to skill/Inferred and
    precedence-rejected (logged) — so an ambient chat can never clobber confirmed identity.
    Filling an EMPTY identity field, and all non-identity fields, need no flag.
  * workingContext (v3): wc* fields are appended as dated history to working-context.jsonl
    (never overwritten); the brain key holds a bounded newest-first DIGEST, recomputed on read.
  * `get` result includes "stale": [...] — identity fields user-confirmed >180 days ago,
    so a reading skill can nudge "still right?" instead of trusting year-old positioning.
"""
from __future__ import annotations
import json
import re
import time
from pathlib import Path
import schema
import wcontext
from schema import ALLOWED_LENS, BRAIN_LIB_VERSION
from brainstore import BrainStore
from brain_maps import SKILLS

# Drift guard: this bridge was built against this brain-lib version. A stale bundled schema/brainstore
# (mismatched copy in a skill) fails loud here instead of misbehaving silently.
_REQUIRES_BRAIN_LIB = 3
if BRAIN_LIB_VERSION != _REQUIRES_BRAIN_LIB:
    raise RuntimeError(f"brain lib version mismatch: bridge needs {_REQUIRES_BRAIN_LIB}, "
                       f"bundled schema is {BRAIN_LIB_VERSION} — re-bundle the brain libs.")

LOG_NAME = "sales-os-brain.log.jsonl"
PROJ_NAME = "sales-os-profile.json"
_MISS = object()


def _skill(name):
    if name not in SKILLS:
        raise KeyError(f"unknown skill {name!r}; known: {sorted(SKILLS)}")
    return SKILLS[name]


def _get(d, path):
    cur = d
    for seg in path.split("."):
        if not isinstance(cur, dict) or seg not in cur:
            return _MISS
        cur = cur[seg]
    return cur


def _read_json(p):
    """Read a legacy JSON file as a dict. Anything that isn't a JSON object — a list, a scalar,
    null, or malformed text — is treated as 'no legacy data' and returns {}. This keeps a corrupt
    or unexpected legacy file from crashing a read (and, on a save, from committing to the brain
    and THEN crashing in the trailing read_view, which would half-apply and mislead a retry)."""
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8-sig"))   # utf-8-sig tolerates a leading BOM
    except Exception:
        return {}
    return d if isinstance(d, dict) else {}


def _to_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("yes", "true", "y", "1", "on")
    return bool(v)


# ------------------------------------------------------------------ reads (non-creating) --
def brain_exists(base):
    base = Path(base)
    return (base / LOG_NAME).exists() or (base / PROJ_NAME).exists()


def _brain_raw_or_none(base):
    """RAW brain projection (no default fill), or None if no brain on disk. Never constructs a
    BrainStore when the brain is absent, so a read creates no files."""
    if not brain_exists(base):
        return None
    return BrainStore(base).load()


def _classify_lens(d):
    """Legacy lens file -> {lens, dealSizeProfile, mode, priceInEmail}, classified by VALUE
    (legacy key naming is unreconciled, so a B2B/B2C value is read whatever key holds it)."""
    out = {}
    for key, v in d.items():
        if key == "price":
            out["priceInEmail"] = _to_bool(v)
            continue
        if not isinstance(v, str):
            continue
        u = v.strip().upper()
        if u in ALLOWED_LENS:
            out["lens"] = u
        elif u in ("A", "B"):
            out["dealSizeProfile"] = u
        elif u in ("COLD", "FOLLOW-UP", "FOLLOWUP", "WARM", "REACTIVATION"):
            out["mode"] = v.strip().lower()
    return out


def _merge_view(fmap, raw, legacy_vals):
    out = {}
    for k, path in fmap.items():
        bv = _get(raw, path) if raw is not None else _MISS
        if bv is not _MISS and bv is not None:
            out[k] = bv
        elif k in legacy_vals and legacy_vals[k] not in (None, ""):
            lv = legacy_vals[k]
            out[k] = _coerce(lv, path) if isinstance(lv, str) else lv   # type-correct a legacy string
        else:
            out[k] = schema.get_default(path)        # default-on-read, from the schema
    return out


_IDENTITY_STALE_DAYS = 180


def _is_identity(path):
    """Tier-A identity: what the user confirmed they are. Guarded by the --confirmed gate
    and surfaced by staleness. voice.*/preferences.* are low-stakes and deliberately NOT gated."""
    return path == "wedge" or path.startswith("business.")


def read_view(base, skill):
    """{'profile': {...}, 'lens': {...}, 'stale': [...]} merged brain->legacy->default.
    Read-only / non-creating. wc* fields are overlaid with a FRESH digest from
    working-context.jsonl (so expiry/caps apply on read, not just at write time).
    'stale' lists identity fields user-confirmed > _IDENTITY_STALE_DAYS ago — a reading
    skill should nudge once ("still right?") rather than trust year-old positioning."""
    sk = _skill(skill)
    raw = _brain_raw_or_none(base)
    legacy_p = _read_json(Path(base) / sk["legacy_profile"]) if sk.get("legacy_profile") else {}
    legacy_l = _classify_lens(_read_json(Path(base) / sk["legacy_lens"])) if sk.get("legacy_lens") else {}
    view = {"profile": _merge_view(sk["profile"], raw, legacy_p),
            "lens": _merge_view(sk["lens"], raw, legacy_l)}
    # fresh working-context digests (never stale-cached in the brain key)
    if wcontext.exists(base):
        for k in sk["profile"]:
            kind = wcontext.KIND_FOR_FIELD.get(k)
            if kind:
                d = wcontext.digest_text(base, kind)
                if d:
                    view["profile"][k] = d
    # stale identity flags
    stale = []
    if raw is not None:
        prov, now = raw.get("_prov", {}), time.time()
        for k, path in sk["profile"].items():
            if not _is_identity(path):
                continue
            p = prov.get(path, {})
            if (p.get("source") in ("user", "confirmed", "revert") and p.get("ts")
                    and now - p["ts"] > _IDENTITY_STALE_DAYS * 86400):
                stale.append(k)
    view["stale"] = stale
    return view


# ------------------------------------------------------------------ writes (to the brain) --
def _coerce(v, path):
    """Coerce a CLI string by the SCHEMA TYPE of `path` — never a blanket guess.
      * bool field -> yes/true/y/1/on -> True;  no/false/n/0/off (or anything else) -> False.
      * int  field -> a bare integer is parsed; '+N' increments are handled atomically in write_view.
      * str  field -> returned EXACTLY as typed (a product literally '+1', '007' or 'true' stays a
        string); the lens enum is upper-cased so 'b2c' -> 'B2C' stays schema-valid.
    Non-str inputs pass through unchanged."""
    if not isinstance(v, str):
        return v
    s = v.strip()
    types = schema.field_types(path)
    if types == (bool,):
        return _to_bool(s)
    if types == (int,):
        # strict: a single optional sign then digits. '++5'/'+-3'/'3.14'/'abc' are NOT ints and are
        # returned unchanged (write_view then skips them) — never crash, never store a wrong type.
        return int(s) if re.fullmatch(r"[+-]?\d+", s) else v
    if path == "preferences.lens":
        u = s.upper()
        return u if u in ALLOWED_LENS else v
    if path == "preferences.dealSizeProfile":
        return s.upper()                 # 'a'/'b' -> 'A'/'B'
    if path == "preferences.mode":
        return s.lower()                 # 'Follow-Up' -> 'follow-up'
    return v


def _user_holds(raw, path):
    """True iff the brain currently holds a USER-CONFIRMED value at `path`."""
    if raw is None:
        return False
    v = _get(raw, path)
    if v is _MISS or v is None:
        return False
    p = raw.get("_prov", {}).get(path, {})
    return p.get("source") in ("user", "confirmed", "revert") or p.get("confidence") == "High"


def write_view(base, skill, fields, source="user", confirmed=False):
    """Write skill fields to the BRAIN (legacy never touched). force-set fields always apply;
    others keep normal precedence. `source` governs non-force fields: "user" (default, High)
    or "inferred" (skill/Inferred — for machine-guessed fills of skipped questions, so they
    never masquerade as user-confirmed and any later real answer overrides them).

    v3 rules:
      * IDENTITY GATE — replacing an existing user-confirmed identity value (business.*/wedge)
        requires confirmed=True. Without it the write is downgraded to skill/Inferred, which
        brainstore precedence-rejects and logs. Filling an EMPTY identity field, and all
        non-identity fields, are unaffected. This makes "ambient capture can never clobber
        confirmed identity" mechanical instead of prose.
      * WORKING CONTEXT — wc* fields append a dated entry to working-context.jsonl (history,
        never overwritten); the brain key is then set to the bounded newest-first digest.

    Returns the fresh read_view plus "dropped": [unmapped field names] so a typo'd or
    unmapped field is never silently swallowed. Empty write creates nothing."""
    if source not in ("user", "inferred"):
        raise ValueError(f"unknown source {source!r}; expected 'user' or 'inferred'")
    sk = _skill(skill)
    allmap = {**sk["profile"], **sk["lens"]}
    force_keys = set(sk.get("force", ()))
    dropped = sorted(k for k in fields if k not in allmap)
    rejected = []                            # fields refused by the identity gate / precedence
    raw0 = _brain_raw_or_none(base)          # provenance snapshot for the identity gate
    # skip None and empty/whitespace-only strings: an empty value must never clobber a stored field
    usable = {k: v for k, v in fields.items()
              if k in allmap and v is not None and not (isinstance(v, str) and v.strip() == "")}
    if not usable:
        return {**read_view(base, skill), "dropped": dropped, "rejected": []}   # nothing to write
    b = None                                          # constructed lazily, only on a real write
    for k, v in usable.items():
        path = allmap[k]
        # working-context fields: append dated history, then store the bounded digest
        kind = wcontext.KIND_FOR_FIELD.get(k)
        if kind:
            wcontext.add(base, kind, str(v), skill)
            d = wcontext.digest_text(base, kind)
            b = b or BrainStore(base)
            b.set(path, d, skill, source="skill", confidence="Inferred", force=True)
            continue
        is_int = schema.field_types(path) == (int,)
        s = v.strip() if isinstance(v, str) else v
        # '+N' on an INT field => atomic increment (read-modify-write under the store lock: no lost
        # updates when the skill runs twice at once).
        if is_int and isinstance(s, str) and s.startswith("+") and s[1:].isdigit():
            b = b or BrainStore(base)
            b.increment(path, int(s[1:]), skill, source="skill", confidence="Inferred")
            continue
        cv = _coerce(v, path)
        # never store a wrong TYPE in an int field (a malformed absolute set like '3.14'/'++5'):
        # skip it rather than crash or persist a string where an int belongs. The skill never sends
        # a malformed counter; '+N' increments are handled above.
        if is_int and not (isinstance(cv, int) and not isinstance(cv, bool)):
            continue
        if is_int and cv < 0:
            continue                     # a counter never goes negative; ignore a stray negative set
        if path == "preferences.lens" and cv not in ALLOWED_LENS:
            continue                     # never store an unrecognised lens (keeps the profile valid)
        b = b or BrainStore(base)
        if k in force_keys:
            b.set(path, cv, skill, source="skill", confidence="Inferred", force=True)
        elif source == "inferred":
            b.set(path, cv, skill, source="skill", confidence="Inferred")
        elif _is_identity(path) and not confirmed and _user_holds(raw0, path):
            # identity gate: unconfirmed replacement of a user-confirmed value is downgraded,
            # which brainstore precedence-rejects and logs — never applied, and REPORTED below
            # so the caller can't mistake a rejection for a successful save.
            b.set(path, cv, skill, source="skill", confidence="Inferred")
            rejected.append(k)
        else:
            b.set(path, cv, skill, source="user", confidence="High")
        if source == "inferred" and _is_identity(path) and _user_holds(raw0, path) and k not in rejected:
            rejected.append(k)               # inferred-over-confirmed is precedence-rejected too
    return {**read_view(base, skill), "dropped": dropped, "rejected": rejected}


# ------------------------------------------------------------------ CLI --
def _main(argv):
    if not argv or argv[0] not in ("get", "save"):
        print(__doc__)
        return 2
    cmd = argv[0]
    skill, base, kv, source, confirmed = None, ".", {}, "user", False
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--skill" and i + 1 < len(argv):
            skill = argv[i + 1]; i += 2; continue
        if a == "--base" and i + 1 < len(argv):
            base = argv[i + 1]; i += 2; continue
        if a == "--source" and i + 1 < len(argv):
            source = argv[i + 1]; i += 2; continue
        if a == "--confirmed":
            confirmed = True; i += 1; continue
        if "=" in a:
            k, v = a.split("=", 1); kv[k] = v
        i += 1
    if cmd == "get":
        try:
            print(json.dumps(read_view(base, skill or "cold-email"), ensure_ascii=False))
        except KeyError as e:
            print(json.dumps({"error": f"unknown --skill: {e}", "known": sorted(SKILLS)}))
            return 2
        except OSError as e:
            print(json.dumps({"error": f"{type(e).__name__}: {e}", "hint": "check --base is a writable folder path"}))
            return 2
        return 0
    # save: an explicit --skill is REQUIRED. A silent cold-email default used to drop every
    # field not in the cold-email map — fail loud instead.
    if skill is None:
        print(json.dumps({"error": "save requires an explicit --skill "
                                   f"(known: {sorted(SKILLS)}); nothing was written"}))
        return 2
    try:
        print(json.dumps(write_view(base, skill, kv, source=source, confirmed=confirmed),
                         ensure_ascii=False))
    except KeyError as e:
        print(json.dumps({"error": f"unknown --skill: {e}; nothing was written",
                          "known": sorted(SKILLS)}))
        return 2
    except OSError as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}; nothing was written",
                          "hint": "check --base is a writable folder path"}))
        return 2
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(_main(sys.argv[1:]))
