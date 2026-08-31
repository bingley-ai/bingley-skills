"""sales-os second brain — the access layer shared by the sales skills.

Design:
  * Source of truth = an APPEND-ONLY event log (sales-os-brain.log.jsonl). Never edited in place.
  * sales-os-profile.json = a DERIVED, rebuildable view (projection). Disposable, never precious.
  * Every write: append event -> update in-memory state -> atomic write of the projection.

Guarantees this buys:
  * No clobber       — writes are field-level (path like "business.audience"); a skill can never
                       wipe a field it didn't touch. Two skills/processes writing different fields
                       both persist (file lock + reload-under-lock).
  * Provenance       — each field records source+confidence; a weaker source can't overwrite a
                       stronger one (user-confirmed beats inferred) unless forced. Rejections logged.
  * Self-heal        — if the projection is missing/corrupt/invalid, load() rebuilds it from the log.
  * Atomic writes    — temp file + os.replace, so a crash never leaves a half-written file.
  * Compaction       — fold the log into one snapshot when it grows; old log archived.
  * One-call revert   — roll a field back to its previous logged value; nobody hand-edits JSON.
"""
from __future__ import annotations
import json, os, time, tempfile, threading, contextlib, fcntl
from pathlib import Path
from schema import SCHEMA_VERSION as _SCHEMA_VERSION, merge_defaults, validate_profile

SCHEMA_VERSION = _SCHEMA_VERSION   # single source of truth lives in schema.py
# precedence levels: higher wins. user-confirmed (3) > inferred/scraped (1) > default (0)
_LEVEL = {"user": 3, "High": 3, "confirmed": 3, "revert": 3,
          "Inferred": 1, "scrape": 1, "skill": 1, "migration": 2, "default": 0}

# auto-compaction threshold: when the log exceeds this, set()/increment() fold it into a
# snapshot (under the lock they already hold). The old log is ALWAYS archived to snapshots/
# first — archives are never pruned automatically. ~1 MB ≈ 2,500 events ≈ months of heavy use;
# compaction cuts load() from ~30ms back to <1ms, so nobody ever feels the O(n) replay.
AUTO_COMPACT_BYTES = 1_000_000


def _prec(source, confidence):
    return max(_LEVEL.get(source, 0), _LEVEL.get(confidence, 0))


def _get(d, path):
    cur = d
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _set(d, path, value):
    cur = d
    parts = path.split(".")
    for k in parts[:-1]:
        nxt = cur.get(k)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[k] = nxt
        cur = nxt
    cur[parts[-1]] = value


class BrainError(Exception):
    pass


class BrainStore:
    def __init__(self, base):
        self.base = Path(base)
        self.base.mkdir(parents=True, exist_ok=True)
        self.log = self.base / "sales-os-brain.log.jsonl"
        self.proj = self.base / "sales-os-profile.json"
        self.snaps = self.base / "snapshots"
        self.snaps.mkdir(exist_ok=True)
        self._tlock = threading.Lock()
        if not self.log.exists():
            self.log.write_text("")

    # ---------- low level ----------
    @contextlib.contextmanager
    def _flock(self):
        lf = open(self.base / ".lock", "w")
        try:
            fcntl.flock(lf, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
            lf.close()

    def _append(self, event):
        event.setdefault("ts", time.time())
        with open(self.log, "a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _atomic_write(self, path, text):
        if not isinstance(text, str):
            raise TypeError("atomic_write expects str")
        fd, tmp = tempfile.mkstemp(dir=str(self.base))
        try:
            with os.fdopen(fd, "w") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)            # atomic on POSIX
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _read_log_text(self):
        """Read the log, tolerating a brief window where a concurrent atomic replace (compaction)
        leaves the path momentarily unresolvable on NON-POSIX filesystems (FUSE / some network
        mounts). On a POSIX FS os.replace is atomic, so the first read always succeeds and this never
        spins. Returns '' if the log is genuinely absent. Also removes the old exists()+read TOCTOU."""
        for attempt in range(5):
            try:
                # errors="replace": a log with non-UTF-8 bytes in it (half-flushed write, a sync
                # client's conflict copy, disk corruption) used to raise UnicodeDecodeError straight
                # out of every read, making the whole brain unreadable — total loss from a few bad
                # bytes. Replacing them degrades those events to junk that the per-line JSON parse
                # already skips, so every intact event either side still loads. (21 Aug 2026.)
                return self.log.read_text(errors="replace")
            except FileNotFoundError:
                if attempt == 4:
                    return ""
                time.sleep(0.003)
        return ""

    def _replay(self):
        """Rebuild full state by replaying the append-only log. Corrupt lines are skipped."""
        state = {"schemaVersion": SCHEMA_VERSION, "_prov": {}}
        for line in self._read_log_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue                      # one bad line never sinks the rebuild
            op = ev.get("op")
            if op == "snapshot" and isinstance(ev.get("state"), dict):
                state = ev["state"]
                state.setdefault("_prov", {})
            elif op in ("set", "revert"):
                p = ev.get("path")
                if not p:
                    continue
                _set(state, p, ev.get("value"))
                state.setdefault("_prov", {})[p] = {
                    "source": ev.get("source"), "confidence": ev.get("confidence"), "ts": ev.get("ts")}
        return state

    def validate(self, state):
        return (isinstance(state, dict)
                and state.get("schemaVersion") == SCHEMA_VERSION
                and isinstance(state.get("_prov", {}), dict))

    def rebuild(self):
        state = self._replay()
        self._atomic_write(self.proj, json.dumps(state, indent=2, ensure_ascii=False))
        return state

    # ---------- public API (this is all a skill ever calls) ----------
    def load(self):
        """Return current state, rebuilt from the append-only LOG (the source of truth), so a
        projection that is STALE — e.g. a crash in the window between the log append and the
        projection write — or corrupt/missing is never trusted on read. The projection is a derived
        view (the design calls it disposable): kept in sync here as a convenience, never read as
        authoritative. Writers call this under the lock, so a write also builds on the true log
        state rather than a possibly-stale projection (closes the same seam for set/increment/revert)."""
        state = self._replay()
        try:
            on_disk = json.loads(self.proj.read_text()) if self.proj.exists() else None
        except (json.JSONDecodeError, ValueError, OSError):
            on_disk = None
        if on_disk != state:
            log_empty = set(state) <= {"schemaVersion", "_prov"}
            # LEGACY ADOPTION (v3.1): a projection with real content but an EMPTY log means the
            # projection is the only record (old install / log lost). Fold it into the log as a
            # snapshot instead of "self-healing" it to blank. v3 gated this on an EXACT
            # schemaVersion match, which silently WIPED any older/keyless/hand-edited brain on
            # first read — now ANY dict with real content is adopted (version stamp normalised),
            # because destroying the only copy of a user's brain is never the right move.
            # Racing adopters both append identical snapshots (harmless).
            if (log_empty and isinstance(on_disk, dict)
                    and set(on_disk) - {"schemaVersion", "_prov"}):
                on_disk.setdefault("_prov", {})
                on_disk["schemaVersion"] = SCHEMA_VERSION
                self._append({"op": "snapshot", "state": on_disk, "note": "adopted legacy projection"})
                self._atomic_write(self.proj, json.dumps(on_disk, indent=2, ensure_ascii=False))
                return on_disk
            # UNREADABLE projection with no log to rebuild from: never destroy the only copy —
            # archive the original bytes to snapshots/ and warn before starting fresh.
            if log_empty and self.proj.exists():
                with contextlib.suppress(OSError):
                    raw = self.proj.read_bytes()
                    if raw.strip():
                        bak = self.snaps / ("unreadable-profile-%s.bak" % time.strftime("%Y%m%d-%H%M%S"))
                        bak.write_bytes(raw)
                        import sys as _sys
                        print("WARNING: existing sales-os-profile.json was unreadable; original archived to "
                              "snapshots/%s before starting fresh." % bak.name, file=_sys.stderr)
            self._atomic_write(self.proj, json.dumps(state, indent=2, ensure_ascii=False))
        return state

    def get(self, path, default=None):
        v = _get(self.load(), path)
        return default if v is None else v

    def profile(self):
        """The schema-aware view a SKILL should read: every canonical key present,
        lens defaulted to B2B, unknown/future keys preserved. Non-destructive — it does
        not rewrite the log or projection, so the stored state stays exactly as logged."""
        return merge_defaults(self.load())

    def profile_ok(self):
        """(ok, problems) — does the current profile satisfy the schema contract?
        Thin wrapper around schema.validate_profile for skills/tests to call."""
        return validate_profile(self.profile())

    def set(self, path, value, skill, source="skill", confidence="Inferred", force=False):
        with self._tlock, self._flock():
            state = self.load()                       # latest, under lock
            prev = _get(state, path)
            prov = state.get("_prov", {}).get(path, {})
            # guard: never destroy an existing scalar by treating it as a branch
            cur = state
            for seg in path.split(".")[:-1]:
                if isinstance(cur, dict) and seg in cur and not isinstance(cur[seg], dict):
                    self._append({"op": "reject", "reason": "path-collision", "path": path,
                                  "value": value, "skill": skill})
                    return state
                cur = cur.get(seg, {}) if isinstance(cur, dict) else {}
            if prev is not None and not force and \
               _prec(source, confidence) < _prec(prov.get("source"), prov.get("confidence")):
                self._append({"op": "reject", "path": path, "value": value, "prev": prev,
                              "skill": skill, "source": source, "confidence": confidence})
                return state                          # weaker source: value untouched, attempt logged
            ev = {"op": "set", "path": path, "value": value, "prev": prev,
                  "skill": skill, "source": source, "confidence": confidence}
            self._append(ev)                          # _append stamps ev["ts"]
            _set(state, path, value)
            # reuse the LOG EVENT's ts (single source of truth) so the projection is byte-identical
            # to a fresh replay of the log — not a second, slightly-later time.time().
            state.setdefault("_prov", {})[path] = {"source": source, "confidence": confidence, "ts": ev["ts"]}
            self._atomic_write(self.proj, json.dumps(state, indent=2, ensure_ascii=False))
            self._maybe_autocompact()
            return state

    def increment(self, path, delta, skill, source="skill", confidence="Inferred"):
        """Atomically add `delta` to the integer at `path` — the read-modify-write happens INSIDE the
        lock, so simultaneous bumps never lose updates (fixes the counter lost-update). A missing or
        non-int current value is treated as 0. Always applies (counters are operational/force state),
        and stamps provenance from the LOG EVENT's ts so the projection stays byte-identical to a
        fresh replay. Logged as a normal `set` event, so replay/compaction need no special case."""
        with self._tlock, self._flock():
            state = self.load()                       # latest, under lock
            # guard: never destroy an existing scalar by treating it as a branch (mirror of set())
            cur = state
            for seg in path.split(".")[:-1]:
                if isinstance(cur, dict) and seg in cur and not isinstance(cur[seg], dict):
                    self._append({"op": "reject", "reason": "path-collision", "path": path,
                                  "value": f"+{delta}", "skill": skill})
                    return state
                cur = cur.get(seg, {}) if isinstance(cur, dict) else {}
            prev = _get(state, path)
            base_n = prev if isinstance(prev, int) and not isinstance(prev, bool) else 0
            value = base_n + int(delta)
            ev = {"op": "set", "path": path, "value": value, "prev": prev,
                  "skill": skill, "source": source, "confidence": confidence}
            self._append(ev)                          # _append stamps ev["ts"]
            _set(state, path, value)
            state.setdefault("_prov", {})[path] = {"source": source, "confidence": confidence, "ts": ev["ts"]}
            self._atomic_write(self.proj, json.dumps(state, indent=2, ensure_ascii=False))
            self._maybe_autocompact()
            return state

    def revert(self, path, skill):
        """Roll a field back to its previous logged value. One call, no hand-editing."""
        with self._tlock, self._flock():
            history = []
            for line in self._read_log_text().splitlines():   # tolerant read: never die on bad bytes
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("path") == path and ev.get("op") in ("set", "revert"):
                    history.append(ev)
            if not history:
                raise BrainError(f"no history for {path}")
            prev_value = history[-1].get("prev")
            ev = {"op": "revert", "path": path, "value": prev_value,
                  "prev": history[-1].get("value"), "skill": skill,
                  "source": "revert", "confidence": "user"}
            self._append(ev)                          # _append stamps ev["ts"]
            state = self.load()
            _set(state, path, prev_value)
            state.setdefault("_prov", {})[path] = {"source": "revert", "confidence": "user", "ts": ev["ts"]}
            self._atomic_write(self.proj, json.dumps(state, indent=2, ensure_ascii=False))
            return state

    def _compact_locked(self):
        """Compaction body — caller MUST already hold _tlock + _flock."""
        state = self._replay()
        (self.snaps / f"log-{int(time.time()*1000)}.jsonl").write_text(self._read_log_text())
        self._atomic_write(self.log, json.dumps({"op": "snapshot", "ts": time.time(), "state": state},
                                                ensure_ascii=False) + "\n")
        self._atomic_write(self.proj, json.dumps(state, indent=2, ensure_ascii=False))
        return state

    def compact(self):
        """Fold the log into a single snapshot. Keeps state, shrinks the log, archives the old log."""
        with self._tlock, self._flock():
            return self._compact_locked()

    def _maybe_autocompact(self):
        """Auto-compact when the log outgrows AUTO_COMPACT_BYTES. Called at the end of
        set()/increment() while the locks are STILL HELD, so it can never race a writer.
        Best-effort: a stat failure never breaks the write that triggered it."""
        try:
            if self.log.stat().st_size > AUTO_COMPACT_BYTES:
                self._compact_locked()
        except OSError:
            pass
