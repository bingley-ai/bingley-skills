"""install_capture_rule — idempotent installer for the always-on sales-brain capture rule.

Setup is the kickoff; what the user WORKS ON keeps the sales brain smart. This installs the
standing in-chat rule into the file the session ACTUALLY LOADS so downstream chats keep the brain
current as a zero-click side effect of normal use. No scheduler (a daily scan needs the app open
to fire reliably here, so it's dropped — the standing rule + the sales skills' own writes cover it).

⛔ TARGET = the WORKING FOLDER ROOT `CLAUDE.md`, not `Claude HQ/CLAUDE.md` (fixed 21 Aug 2026).
The host auto-loads `<working folder>/CLAUDE.md` each session. Until this fix the rule was written
to `<working folder>/Claude HQ/CLAUDE.md`, which is loaded only by an operator who already has a
root stub pointing into it — so for every ordinary user the rule was installed into a file their
session never read, and silently never fired. `--base` still points at the brain dir (that is where
the profile and libs live); the rule file is resolved as `base.parent`.

⛔ NEVER CREATE THE ROOT CLAUDE.md SILENTLY. That file governs everything the user does in the
folder, not just sales. Appending a fenced block to one they already have is fair; conjuring one
into existence because they installed a sales tool is not. With no root CLAUDE.md this returns
`action:"needs-consent"` and writes nothing; the calling skill asks once, then re-runs with
`--create-root`.

⛔ ORDER IS LOAD-BEARING: install the new block FIRST, strip the legacy one SECOND. Never a window
where the user has neither. A legacy strip always takes a timestamped backup first.

Idempotent by design: the rule lives inside a fenced marker block. Re-running never double-appends;
if the block already exists it's left untouched (or, with --update, its body is refreshed in place).
Prints JSON status so the calling skill can report the truth.

CLI:
  python3 install_capture_rule.py --base "<wf>/Claude HQ"
  python3 install_capture_rule.py --base "<wf>/Claude HQ" --create-root   # after the user says yes
  python3 install_capture_rule.py --base "<wf>/Claude HQ" --update        # refresh body if drifted
  python3 install_capture_rule.py --base "<wf>/Claude HQ" --root "<dir>"  # override target (tests)
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

BEGIN = "<!-- SALES-BRAIN-AUTOCAPTURE:BEGIN (managed by sales-brain-setup — do not edit inside) -->"
END = "<!-- SALES-BRAIN-AUTOCAPTURE:END -->"

# The standing rule, verbatim to SKILL.md. ⛔ NO ABSOLUTE PATH may be baked into this block
# (fixed 21 Aug 2026): a session mount path like /sessions/<name>/mnt/... dies when the session
# ends, so the block instructs RELATIVE resolution against the connected working folder at runtime.
RULE_BODY = """## AI sales brain auto-capture (installed by sales-brain-setup — standing rule, no scheduler)
In any chat, when the user reveals something durable about THEIR OWN business, keep the AI sales brain
current: from the connected working folder, run
`python3 "Claude HQ/_lib/brain/brain_bridge.py" save --skill sales-setup --base "Claude HQ"`.
(Resolve `Claude HQ` against wherever this working folder is mounted in YOUR session — never a
remembered absolute path. If that path has moved, the same libs are bundled inside each sales
skill's scripts/ dir.)
- **Live working context** (a campaign they're running, accounts they're targeting, an objection they
  heard, a win) -> save to the workingContext keys: `wcCampaigns=`, `wcTargets=`, `wcObjections=`,
  `wcWins=`, `wcNotes=`. Each save is APPENDED as dated history (never overwritten) and can never
  touch confirmed identity.
- **A change to core identity** (they now sell something new, changed who they target, repriced) -> do
  NOT overwrite silently. Say "Looks like your offer changed — update your AI sales brain?" and ONLY on a
  yes, save with the `--confirmed` flag. Without `--confirmed`, an identity write cannot replace what
  the user confirmed in setup — the bridge downgrades and rejects it. That is deliberate.
- **Do NOT capture**: questions the user asks, hypotheticals, or facts about OTHER companies they
  research (a prospect's pricing is the prospect's, never the user's). When unsure whether it's about
  the user's own business, skip it.
Fires as a side effect of normal chats. Zero click.

**This block is the only thing the AI sales brain adds to this file.** It writes only to its own files
under `Claude HQ/` — the profile, its log, working context, snapshots and a lock file — and never
creates, moves or renames anything else. Delete this block and it stops."""

# lib files installed alongside the rule, so the standing rule always has a runnable bridge at a
# stable path ({base}/_lib/brain/) even in chats where no sales skill is loaded.
LIB_FILES = ("schema.py", "brainstore.py", "brain_bridge.py", "brain_maps.py", "wcontext.py",
             "ledger.py")


def _install_libs(base: str) -> list:
    """Copy the bundled brain libs (siblings of this installer) into <base>/_lib/brain/.
    Overwrites — the newest-installed skill keeps the shared runtime current. Best-effort:
    a missing sibling is skipped, never fatal."""
    src = Path(__file__).resolve().parent
    dst = Path(base) / "_lib" / "brain"
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in LIB_FILES:
        s = src / name
        if s.exists():
            (dst / name).write_text(s.read_text(encoding="utf-8"), encoding="utf-8")
            copied.append(name)
    return copied


def _block(base: str) -> str:
    # `base` deliberately unused in the body: the block must carry NO absolute path.
    return f"{BEGIN}\n{RULE_BODY}\n{END}"


def _backup(md: Path, text: str) -> str:
    b = md.with_name(md.name + ".bak-" + time.strftime("%Y%m%d-%H%M%S"))
    b.write_text(text, encoding="utf-8", errors="surrogateescape")
    return str(b)


def _strip_block(text: str) -> tuple:
    """Remove a whole managed block, or repair a half-block. Returns (new_text, found)."""
    if BEGIN in text and END in text:
        pre = text.split(BEGIN, 1)[0].rstrip("\n")
        post = text.split(END, 1)[1].lstrip("\n")
        joined = (pre + ("\n\n" if pre and post else "") + post).strip("\n")
        return (joined + "\n" if joined else ""), True
    if BEGIN in text:
        return text.split(BEGIN, 1)[0].rstrip("\n") + "\n", True
    if END in text:
        kept = "\n".join(l for l in text.splitlines() if END not in l).rstrip("\n")
        return (kept + "\n" if kept else ""), True
    return text, False


def _upsert(md: Path, block: str, update: bool) -> dict:
    """Put exactly one managed block into an EXISTING file, disturbing nothing else.
    surrogateescape on read AND write so non-UTF-8 bytes round-trip untouched (fixed 21 Aug 2026:
    a single stray byte used to kill the whole install with a UnicodeDecodeError traceback)."""
    text = md.read_text(encoding="utf-8", errors="surrogateescape")

    if BEGIN in text and END in text:
        if not update:
            return {"installed": False, "action": "already-present", "path": str(md)}
        # ⛔ Strip EVERY managed block, not just the first (fixed 21 Aug 2026, found by the
        # adversarial suite). The old split-on-first-BEGIN / first-END kept everything after the
        # first END as `post` — so a file that already carried two blocks (hand-paste, a merge, or
        # the wreckage of an older bug) came out of --update still carrying two, and the duplicate
        # was now pinned in place by a "successful" update.
        stripped = text
        while BEGIN in stripped and END in stripped:
            head = stripped.split(BEGIN, 1)[0]
            tail = stripped.split(END, 1)[1]
            stripped = head.rstrip("\n") + ("\n\n" if head.strip() and tail.strip() else "") + tail.lstrip("\n")
        pre = stripped.rstrip("\n")
        new = (pre + ("\n\n" if pre else "") + block).rstrip("\n") + "\n"
        if new == text:
            return {"installed": False, "action": "already-current", "path": str(md)}
        _backup(md, text)
        md.write_text(new, encoding="utf-8", errors="surrogateescape")
        return {"installed": True, "action": "updated", "path": str(md)}

    if BEGIN in text or END in text:
        # CORRUPTED block (one marker lost): a blind append would duplicate the rule and orphan
        # the surviving marker. Back up, strip the wreckage, append one clean block.
        _backup(md, text)
        stripped, _ = _strip_block(text)
        stripped = stripped.rstrip("\n")
        sep = "\n\n" if stripped else ""
        md.write_text(stripped + sep + block + "\n", encoding="utf-8", errors="surrogateescape")
        return {"installed": True, "action": "repaired", "path": str(md)}

    # append with a clean separator; never disturb existing content
    sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    md.write_text(text + sep + block + "\n", encoding="utf-8", errors="surrogateescape")
    return {"installed": True, "action": "appended", "path": str(md)}


def _retire_legacy(legacy: Path) -> dict:
    """Strip the managed block out of the OLD location (<base>/CLAUDE.md), if it's there.
    Backs up first. If stripping empties a file this installer originally created, remove it;
    a file with other content of the user's is always kept."""
    if not legacy.exists():
        return {"legacy": "absent"}
    if not legacy.is_file():          # a directory named CLAUDE.md — never read, never touch
        return {"legacy": "not-a-file", "legacy_path": str(legacy)}
    text = legacy.read_text(encoding="utf-8", errors="surrogateescape")
    if BEGIN not in text and END not in text:
        return {"legacy": "no-block"}
    bak = _backup(legacy, text)
    new, _ = _strip_block(text)
    if new.strip():
        legacy.write_text(new, encoding="utf-8", errors="surrogateescape")
        return {"legacy": "block-removed", "legacy_path": str(legacy), "legacy_backup": bak}
    legacy.unlink()
    return {"legacy": "file-removed (held nothing but the block)",
            "legacy_path": str(legacy), "legacy_backup": bak}


def install(base: str, update: bool = False, create_root: bool = False, root: str = None) -> dict:
    hq = Path(base)
    try:
        hq.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        # `--base` pointing at an existing FILE, or an unwritable parent. Fail as JSON.
        return {"installed": False, "action": "blocked",
                "error": f"cannot use {hq} as the brain directory: {e.__class__.__name__}: {e}",
                "path": str(hq), "libs": []}

    root_dir = Path(root) if root else hq.parent
    md = root_dir / "CLAUDE.md"
    legacy = hq / "CLAUDE.md"
    block = _block(base)

    # ⛔ A non-file at the target (directory, socket, dangling symlink) must fail as JSON, not as a
    # traceback (added 21 Aug 2026, found by the adversarial suite). `md.exists()` is True for a
    # directory, so without this guard the next read_text raises IsADirectoryError straight out of
    # the process and the calling skill sees a stack trace instead of a status it can act on.
    if md.exists() and not md.is_file():
        return {"installed": False, "action": "blocked",
                "error": f"{md} exists but is not a regular file; refusing to touch it",
                "path": str(md), "libs": []}

    # ⛔ THE LIBS ARE INSTALLED BEFORE THE CONSENT GATE, ON PURPOSE. DO NOT "FIX" THIS.
    # (Re-confirmed 21 Aug 2026 after an adversarial run flagged it as a consent leak and was wrong.)
    # The consent being asked for is narrowly about creating a ROOT `CLAUDE.md` — a file that
    # governs EVERY session in the folder, sales or not. It is not consent to have a sales brain:
    # the user already gave that by running setup, and their profile already lives in `base`.
    # `_lib/brain/` is part of that brain, and list-builder-apollo, list-builder-ocean and
    # sales-control-panel each probe `<base>/_lib/brain/brain_bridge.py` and silently fall back to
    # standalone when it is missing. Deferring the libs behind this gate therefore costs a user who
    # declines the standing rule their brain in three other skills, silently. Install them either
    # way; the SKILL.md rule is what stops them being shown to the user.
    libs = _install_libs(base)

    if not md.exists():
        if not create_root:
            # No root CLAUDE.md is written here. Do NOT retire the legacy block either:
            # until the new one exists, it may be the only rule the user has.
            return {"installed": False, "action": "needs-consent", "path": str(md),
                    "libs": libs,
                    "why": ("no CLAUDE.md in the working folder root. That file governs every "
                            "session in this folder, so the user has to agree before one is "
                            "created. Ask once, then re-run with --create-root."),
                    "legacy_present": legacy.exists() and legacy.is_file()
                                      and BEGIN in legacy.read_text(encoding="utf-8",
                                                                    errors="surrogateescape")}
        root_dir.mkdir(parents=True, exist_ok=True)
        md.write_text(block + "\n", encoding="utf-8")
        result = {"installed": True, "action": "created", "path": str(md), "libs": libs}
        result.update(_retire_legacy(legacy))
        return result

    result = _upsert(md, block, update)
    result["libs"] = libs
    # only retire the old copy once a live one is confirmed at the root
    if BEGIN in md.read_text(encoding="utf-8", errors="surrogateescape"):
        result.update(_retire_legacy(legacy))
    return result


def _main(argv) -> int:
    base, update, create_root, root = None, False, False, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--base" and i + 1 < len(argv):
            base = argv[i + 1]; i += 2; continue
        if a == "--root" and i + 1 < len(argv):
            root = argv[i + 1]; i += 2; continue
        if a == "--update":
            update = True
        if a == "--create-root":
            create_root = True
        i += 1
    if not base:
        print(json.dumps({"installed": False, "error": "missing --base"}))
        return 2
    # ⛔ The caller is a chat agent reading one JSON line, not a developer reading a stack trace
    # (added 21 Aug 2026). A read-only CLAUDE.md, a folder locked by Dropbox/OneDrive sync, a full
    # disk or a permissions-hardened home directory all raise OSError from deep inside pathlib —
    # which used to escape as a traceback and leave the skill with nothing it could report or act
    # on. Every filesystem failure now leaves as a status the skill can read out loud.
    try:
        result = install(base, update, create_root, root)
    except (OSError, ValueError) as e:
        # ValueError covers UnicodeDecodeError/UnicodeEncodeError from an undecodable file —
        # still a JSON status, never a traceback (widened 21 Aug 2026).
        print(json.dumps({"installed": False, "action": "blocked",
                          "error": f"{e.__class__.__name__}: {e}",
                          "hint": ("the folder or file could not be read or written — check it is "
                                   "not read-only, locked by a sync client, or out of disk space"),
                          "libs": []}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
