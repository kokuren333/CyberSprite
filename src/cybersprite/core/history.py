"""Portable locks, atomic file replacement, and bounded deterministic snapshots."""

import gzip
import json
import os
from hashlib import sha256
from pathlib import Path
from threading import Event, Thread

from .canonical import dumps_project, json_bytes, loads_project
from .errors import CyberSpriteError
from .journal_clock import elapsed_clock, filesystem_clock, now

LOCK_WAIT_SECONDS = 10
LOCK_STALE_SECONDS = 30
LOCK_REFRESH_SECONDS = 5
SNAPSHOT_COUNT = 200
SNAPSHOT_BYTES = 256 * 1024 * 1024


def io_error(error, path):
    return CyberSpriteError(
        "E_IO",
        f"Cannot persist {path}: {error}",
        "Check free disk space, permissions, and applications holding the file open.",
        {"path": str(path), "os_error": str(error)},
    )


def atomic_write(path, data):
    path = Path(path)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with temp.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(4):
            try:
                os.replace(temp, path)
                return
            except PermissionError:
                if attempt == 3:
                    raise
                Event().wait(1)
    except OSError as error:
        raise io_error(error, path) from error
    finally:
        temp.unlink(missing_ok=True)


class ProjectLock:
    def __init__(self, root, actor):
        self.path = Path(root) / ".cybersprite/lock"
        self.actor = actor
        self.fd = None
        self.stop = Event()
        self.thread = None
        self.identity = None

    def __enter__(self):
        data = json_bytes({"pid": os.getpid(), "actor": self.actor, "time": now()})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = elapsed_clock() + LOCK_WAIT_SECONDS * 1_000_000_000
        while True:
            try:
                self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                stat = os.fstat(self.fd)
                self.identity = (stat.st_dev, stat.st_ino)
                os.write(self.fd, data)
                os.fsync(self.fd)
                # Windows cannot steal a stale lock while a non-delete-sharing fd stays open.
                os.close(self.fd)
                self.fd = None
                break
            except FileExistsError:
                try:
                    stat = self.path.stat()
                    if filesystem_clock() - stat.st_mtime_ns >= LOCK_STALE_SECONDS * 1_000_000_000:
                        # Compare again before unlinking to avoid stealing a refreshed lock.
                        if self.path.stat().st_mtime_ns == stat.st_mtime_ns:
                            self.path.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    continue
                if elapsed_clock() >= deadline:
                    try:
                        holder = json.loads(self.path.read_bytes())
                    except (OSError, ValueError):
                        holder = {}
                    raise CyberSpriteError(
                        "E_LOCKED",
                        "Project is locked by another writer.",
                        "Wait for the active writer to finish, then retry.",
                        holder,
                    ) from None
                Event().wait(1)
            except OSError as error:
                if self.fd is not None:
                    os.close(self.fd)
                    self.fd = None
                    if self._owned():
                        self.path.unlink(missing_ok=True)
                raise io_error(error, self.path) from error
        self.thread = Thread(target=self._refresh, daemon=True)
        self.thread.start()
        return self

    def _owned(self):
        try:
            stat = self.path.stat()
            return (stat.st_dev, stat.st_ino) == self.identity
        except FileNotFoundError:
            return False

    def _refresh(self):
        while not self.stop.wait(LOCK_REFRESH_SECONDS):
            if not self._owned():
                break
            try:
                os.utime(self.path, None)
            except OSError:
                break

    def require_owned(self):
        if not self._owned():
            raise CyberSpriteError(
                "E_LOCKED",
                "Project lock was replaced while the operation was running.",
                "Read the current revision, then retry after the other writer finishes.",
            )

    def __exit__(self, *_):
        self.stop.set()
        if self.thread:
            self.thread.join()
        if self.fd is not None:
            os.close(self.fd)
        if self._owned():
            self.path.unlink(missing_ok=True)


def paths(root):
    return Path(root) / ".cybersprite/history"


def read_state(root):
    path = paths(root) / "state.json"
    if not path.exists():
        return {"undo_stack": [], "redo_stack": [], "last_saved_sha256": None}
    try:
        state = json.loads(path.read_bytes())
        if not all(type(v) is int for k in ("undo_stack", "redo_stack") for v in state[k]):
            raise ValueError("Invalid history stacks.")
        return state
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CyberSpriteError(
            "E_HISTORY_UNAVAILABLE",
            "History state is missing or corrupt.",
            "Keep project.json; remove corrupt derived history to start a new baseline.",
        ) from error


def read_journal(root):
    path = paths(root) / "journal.jsonl"
    if not path.exists():
        return []
    try:
        return [json.loads(line) for line in path.read_bytes().splitlines() if line]
    except (OSError, ValueError) as error:
        raise CyberSpriteError(
            "E_HISTORY_UNAVAILABLE",
            "History journal is corrupt.",
            "Keep project.json and restore or remove derived history.",
        ) from error


def snapshot_path(root, revision):
    return paths(root) / f"snapshots/r{revision:06d}.json.gz"


def snapshot_bytes(p):
    data = bytearray(gzip.compress(dumps_project(p), mtime=0))
    data[9] = 255  # Normalize zlib's platform-specific OS header byte on Python 3.12.
    return bytes(data)


def restore(root, revision):
    try:
        return loads_project(gzip.decompress(snapshot_path(root, revision).read_bytes()))
    except (OSError, EOFError, ValueError) as error:
        raise CyberSpriteError(
            "E_HISTORY_UNAVAILABLE",
            "Required revision snapshot is unavailable.",
            "Use a retained revision from get_history; expired snapshots cannot be undone.",
            {"revision": revision},
        ) from error


def journal_bytes(entries):
    return b"".join(
        json.dumps(entry, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
        + b"\n"
        for entry in entries
    )


def compact_entry(entry):
    if len(journal_bytes([entry])) <= 1024 * 1024:
        return entry
    entry = dict(entry)
    entry["ops"] = [
        {
            "op": item["op"],
            "args": {
                "sha256": sha256(json_bytes(item["args"])).hexdigest(),
                "bytes": len(json_bytes(item["args"])),
            },
        }
        for item in entry["ops"]
    ]
    return entry


def retain(root):
    snapshots = sorted((paths(root) / "snapshots").glob("r*.json.gz"))
    total = sum(path.stat().st_size for path in snapshots)
    while snapshots and (len(snapshots) > SNAPSHOT_COUNT or total > SNAPSHOT_BYTES):
        path = snapshots.pop(0)
        total -= path.stat().st_size
        path.unlink()


def save_files(files):
    """Rollback all persisted bytes if any member of a commit cannot be saved."""
    backups = [(path, path.read_bytes() if path.exists() else None) for path, _ in files]
    try:
        for path, data in files:
            atomic_write(path, data)
    except BaseException:
        restore_files(backups)
        raise
    return backups


def restore_files(backups):
    for path, data in reversed(backups):
        if data is None:
            path.unlink(missing_ok=True)
        elif not path.exists() or path.read_bytes() != data:
            atomic_write(path, data)


def retain_previews(root):
    folder = Path(root) / ".cybersprite/previews"
    revisions = sorted({path.name.split("_")[0] for path in folder.glob("r*_*.png")})
    for expired in revisions[:-100]:
        for path in folder.glob(expired + "_*.png"):
            path.unlink()


def history_result(root, limit=20):
    state = read_state(root)
    entries = []
    for entry in read_journal(root)[-limit:][::-1]:
        values = {
            k: entry.get(k) for k in ("revision", "kind", "actor", "label", "time", "changed")
        }
        values["ops"] = [item["op"] for item in entry["ops"]]
        entries.append(values)
    return {
        "entries": entries,
        "can_undo": bool(state["undo_stack"]),
        "can_redo": bool(state["redo_stack"]),
    }
