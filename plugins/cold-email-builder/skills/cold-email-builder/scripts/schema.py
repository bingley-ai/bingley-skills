"""sales-os second brain — LOCKED SCHEMA (M2).

Single source of truth for the brain's shape: every section, every key name,
its type, and its default. Adopted from the Outbound Room design spec (section 1)
as the v1 baseline (21 Jun 2026).

Design rules this file encodes:
  * Key names are FIXED here. Skills and adapters import them; nobody hand-types paths.
  * Every key has a default, so a reader NEVER throws on a missing field (default-on-read).
  * `preferences.lens` is a valid two-value enum: "B2B" or "B2C", treated equally (21 Jun 2026 — B2C is NOT rejected or parked). "B2B" is the DEFAULT (the current focus, and
    the stricter bar); a B2C user's lens is carried through untouched. validate_profile() accepts
    either and flags only an UNKNOWN value (a typo like "B2X"). The quality bar stays high for
    both — that's a scoring-engine concern handled when the cold-email scorer is ported (M3), not
    a brain concern.
  * Unknown / future keys are TOLERATED (forward-compat): validation only checks known paths,
    never rejects extras. This keeps brainstore's "unknown future keys preserved" guarantee.
  * `_prov` IS the design spec's `provenance` map, renamed with a leading underscore as an
    internal/system field; brainstore reads and writes provenance under that key.

This file is pure data + pure functions. No IO, no dependency on brainstore (so either can
import the other without a cycle).
"""
from __future__ import annotations
import copy

SCHEMA_VERSION = 1
# Bumped when the shared brain libs (schema/brainstore/brain_bridge) change shape. Each skill
# bundles copies of these libs; the bridge asserts this matches on load so a STALE bundled copy
# fails loud instead of drifting silently. Bundled copies are generated, never hand-edited.
BRAIN_LIB_VERSION = 3   # v3: --confirmed identity gate, working-context JSONL (wcontext.py),
                        #     auto-compaction in brainstore, stale-identity flags in read_view

# --- lens enum: B2B and B2C are both valid; B2B is the default (21 Jun 2026) ----
LENS_DEFAULT = "B2B"
ALLOWED_LENS = ("B2B", "B2C")    # both valid, treated equally; B2B is just the default


def blank_profile():
    """A fully-defaulted profile. Every canonical key present; lens locked to B2B.

    Returned fresh each call (deep copy safe to mutate)."""
    return {
        "schemaVersion": SCHEMA_VERSION,
        "createdBy": None,
        "createdAt": None,
        "updatedAt": None,

        # the unification spine — maps straight off cold-email + pitch positioning
        "business": {
            "name": None,
            "product": None,
            "audience": None,          # FREE-TEXT descriptive (NOT the scoring lens)
            "problem": None,           # the USER's problem (never a target's BANT need)
            "benefit": None,
            "differentiator": None,
            "proof": None,
            "ask": None,
            "website": None,
        },

        "wedge": None,                 # the whole argument in one move (pitch positioning)

        "voice": {
            "register": None,
            "profileRef": None,        # path to a voice profile if one exists, else None
        },

        "preferences": {
            "lens": LENS_DEFAULT,      # default "B2B"; "B2C" is equally valid
            "dealSizeProfile": "A",
            "mode": "cold",
            "priceInEmail": False,
        },

        "connectedSources": {          # drives the three-tier on-ramp; more true = fewer questions
            "site": False,
            "sentMailVoice": False,
            "callNotes": False,
            "apollo": False,
            "gmail": False,
            "outlook": False,
        },

        "capture": {                   # progressive-capture progress flags
            "seen": False,
            "deepDone": False,
            "deepSkips": 0,
        },

        "_prov": {},                   # sparse, per-field provenance: path -> {source, confidence, ts}
    }


# --- known paths + expected types (None always allowed unless noted) ----------
# Only KNOWN paths are checked. Anything not listed is tolerated (forward-compat).
_NONE = type(None)
_TYPES = {
    "schemaVersion": (int,),
    "createdBy": (str, _NONE),
    "createdAt": (str, _NONE),
    "updatedAt": (str, _NONE),

    "business.name": (str, _NONE),
    "business.product": (str, _NONE),
    "business.audience": (str, _NONE),
    "business.problem": (str, _NONE),
    "business.benefit": (str, _NONE),
    "business.differentiator": (str, _NONE),
    "business.proof": (str, _NONE),
    "business.ask": (str, _NONE),
    "business.website": (str, _NONE),

    "wedge": (str, _NONE),

    "voice.register": (str, _NONE),
    "voice.profileRef": (str, _NONE),

    "preferences.lens": (str,),                 # value also constrained to ALLOWED_LENS
    "preferences.dealSizeProfile": (str, _NONE),
    "preferences.mode": (str, _NONE),
    "preferences.priceInEmail": (bool,),

    "connectedSources.site": (bool,),
    "connectedSources.sentMailVoice": (bool,),
    "connectedSources.callNotes": (bool,),
    "connectedSources.apollo": (bool,),
    "connectedSources.gmail": (bool,),
    "connectedSources.outlook": (bool,),

    "capture.seen": (bool,),
    "capture.deepDone": (bool,),
    "capture.deepSkips": (int,),
}

# flat list of every canonical key path, for docs/tests
CANONICAL_KEYS = tuple(_TYPES.keys())


def _get(d, path):
    cur = d
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return _MISSING
        cur = cur[k]
    return cur


_MISSING = object()


def get_default(path):
    """The schema default for a canonical path (or None if the path isn't canonical)."""
    v = _get(blank_profile(), path)
    return None if v is _MISSING else v


def field_types(path):
    """The declared type tuple for a canonical path, or (str,) if the path is unknown/free-text.
    The bridge uses this to coerce a CLI value by the field's REAL type instead of guessing, so a
    free-text value that happens to look numeric or boolean (a product named '+1', '007' or 'true')
    is never silently retyped."""
    return _TYPES.get(path, (str,))


def _deep_merge(base, over):
    """Recursively overlay `over` onto `base`. `over` wins; dicts merge; lists/scalars replace.
    Unknown keys in `over` are preserved (forward-compat)."""
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def merge_defaults(state):
    """Return `state` with every missing canonical key filled from defaults.

    Non-destructive view: callers get the full shape without the stored state being rewritten.
    `state` values always win; unknown/future keys are preserved. Missing lens defaults to B2B.
    """
    merged = _deep_merge(blank_profile(), state or {})
    # safety net: a missing/empty lens falls back to the default (B2B). A present B2C is kept.
    if not merged.get("preferences", {}).get("lens"):
        merged.setdefault("preferences", {})["lens"] = LENS_DEFAULT
    return merged


def _type_ok(v, types):
    """Type check that keeps bool and int distinct (bool subclasses int in Python)."""
    if types == (bool,):
        return isinstance(v, bool)
    if types == (int,):
        return isinstance(v, int) and not isinstance(v, bool)
    if isinstance(v, bool):                        # a stray bool only fits a bool-typed field
        return bool in types
    return isinstance(v, types)


def validate_profile(state):
    """Strict shape check for a REAL profile. Returns (ok: bool, problems: list[str]).

    Checks: dict, schemaVersion, _prov is a dict, known-path types, and the B2B lens lock.
    Tolerates unknown/future keys (never a failure). Separate from brainstore.validate(),
    which is the looser structural gate used during fuzz."""
    problems = []
    if not isinstance(state, dict):
        return False, ["state is not a dict"]
    if state.get("schemaVersion") != SCHEMA_VERSION:
        problems.append(f"schemaVersion != {SCHEMA_VERSION}")
    if not isinstance(state.get("_prov", {}), dict):
        problems.append("_prov is not a dict")

    for path, types in _TYPES.items():
        v = _get(state, path)
        if v is _MISSING:
            continue                              # missing is fine (default-on-read covers it)
        if not _type_ok(v, types):
            problems.append(f"{path}: expected {tuple(t.__name__ for t in types)}, got {type(v).__name__}")

    lens = _get(state, "preferences.lens")
    if lens not in (_MISSING, None) and lens not in ALLOWED_LENS:
        problems.append(f"preferences.lens = {lens!r} is not a known lens (expected one of {ALLOWED_LENS})")

    return (len(problems) == 0), problems


def is_b2b(state):
    """True iff the lens is B2B (missing counts as B2B by default). Informational only —
    B2C is equally valid; this just tells a caller which lens is in effect."""
    lens = _get(state, "preferences.lens")
    return lens in (_MISSING, None, LENS_DEFAULT)
