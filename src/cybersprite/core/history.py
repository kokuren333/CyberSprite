"""Portable locks, atomic file replacement, and bounded deterministic snapshots."""

import base64
import gzip
import io
import json
import os
from hashlib import sha256
from pathlib import Path
from threading import Event, Thread, get_ident

from .canonical import dumps_project, json_bytes, loads_project
from .errors import CyberSpriteError
from .execution import _active, _records, check_deadline, committed_bytes, recover_pending
from .journal_clock import elapsed_clock, filesystem_clock, now

LOCK_WAIT_SECONDS = 10
LOCK_STALE_SECONDS = 30
LOCK_REFRESH_SECONDS = 5
SNAPSHOT_COUNT = 200
SNAPSHOT_BYTES = 256 * 1024 * 1024
JOURNAL_SEGMENT_BYTES = 8 * 1024 * 1024


def io_error(error, path):
    return CyberSpriteError(
        "E_IO",
        f"Cannot persist {path}: {error}",
        "Check free disk space, permissions, and applications holding the file open.",
        {"path": str(path), "os_error": str(error)},
    )


def atomic_write(path, data):
    scope = _active.get()
    if scope is not None:
        path = scope.remember(path)
    _atomic_write(path, data)
    check_deadline()


def _atomic_write(path, data):
    path = Path(path)
    temp = path.with_name(path.name + f".{os.getpid()}.{get_ident()}.tmp")
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
            check_deadline()
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
                Event().wait(25 / 1000)
            except OSError as error:
                if self.fd is not None:
                    os.close(self.fd)
                    self.fd = None
                    if self._owned():
                        self.path.unlink(missing_ok=True)
                raise io_error(error, self.path) from error
        self.thread = Thread(target=self._refresh, daemon=True)
        self.thread.start()
        try:
            recover_pending(self.path.parent.parent)
            repair_tail(self.path.parent.parent)
        except BaseException:
            self.__exit__()
            raise
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


def project_lock(root, actor):
    scope = _active.get()
    if scope is not None and scope.lock is not None and Path(root).absolute() == scope.root:
        from contextlib import nullcontext

        return nullcontext(scope.lock)
    return ProjectLock(root, actor)


def read_state(root):
    path = paths(root) / "state.json"
    if not path.exists():
        return {"undo_stack": [], "redo_stack": [], "last_saved_sha256": None}
    try:
        state = json.loads(committed_bytes(path, root))
        if not all(type(v) is int for k in ("undo_stack", "redo_stack") for v in state[k]):
            raise ValueError("Invalid history stacks.")
        position = state.get("journal_position")
        if position is not None and (
            not isinstance(position, dict)
            or type(position.get("bytes")) is not int
            or position["bytes"] < 0
            or type(position.get("revision")) is not int
            or position["revision"] < 0
            or position.get("segment") != "journal.jsonl"
        ):
            raise ValueError("Invalid committed journal position.")
        return state
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CyberSpriteError(
            "E_HISTORY_UNAVAILABLE",
            "History state is missing or corrupt.",
            "Keep project.json; remove corrupt derived history to start a new baseline.",
        ) from error


def journal_paths(root):
    return [*sorted(paths(root).glob("journal-*.jsonl")), paths(root) / "journal.jsonl"]


def journal_tail(root, limit=None, after_revision=None, *, transactions=False):
    """Read backwards in blocks, stopping as soon as the requested page is filled."""
    scope = _active.get()
    if scope is not None and scope.lock is not None:
        return _journal_tail(root, limit, after_revision, [], transactions)
    while True:
        records = _records(root)
        stamp = journal_stamp(root)
        result = _journal_tail(root, limit, after_revision, records, transactions)
        if records == _records(root) and stamp == journal_stamp(root):
            return result
        check_deadline()


def _journal_tail(root, limit, after_revision, records, transactions):
    entries: list[tuple[dict, str]] = []
    if limit == 0:
        return entries
    try:
        for path in reversed(journal_paths(root)):
            scope = _active.get()
            if scope is not None:
                path = scope.resolve(path)
            old = next(
                (item for item in records if item["path"] == path.absolute().as_posix()), None
            )
            if old is not None and "data" in old:
                if old["data"] is None:
                    continue
                source = io.BytesIO(base64.b64decode(old["data"]))
            else:
                source = None
            if not path.exists():
                continue
            with source if source is not None else path.open("rb") as stream:
                stream.seek(0, 2)
                end = stream.tell()
                if old is not None and "length" in old:
                    end = min(end, old["length"])
                buffer = b""
                pos = end
                first = True
                while pos:
                    start = max(0, pos - 65536)
                    stream.seek(start)
                    buffer = stream.read(pos - start) + buffer
                    pos = start
                    lines = buffer.split(b"\n")
                    buffer = lines.pop(0)
                    if first and lines:
                        # An unterminated last line is an uncommitted/torn append.
                        lines.pop()
                        first = False
                    for line in reversed(lines):
                        if not line:
                            continue
                        entry = json.loads(line)
                        if transactions and entry.get("kind") in ("create", "external"):
                            continue
                        if after_revision is not None and entry["revision"] <= after_revision:
                            return list(reversed(entries))
                        entries.append((entry, path.name))
                        if limit is not None and len(entries) >= limit:
                            return list(reversed(entries))
                if buffer and not first:
                    entry = json.loads(buffer)
                    if transactions and entry.get("kind") in ("create", "external"):
                        continue
                    if after_revision is not None and entry["revision"] <= after_revision:
                        return list(reversed(entries))
                    entries.append((entry, path.name))
                    if limit is not None and len(entries) >= limit:
                        return list(reversed(entries))
        return list(reversed(entries))
    except (OSError, ValueError) as error:
        raise CyberSpriteError(
            "E_HISTORY_UNAVAILABLE",
            "History journal is corrupt.",
            "Keep project.json and restore or remove derived history.",
        ) from error


def read_journal(root, limit=None, *, after_revision=None):
    return [entry for entry, _ in journal_tail(root, limit, after_revision)]


def repair_tail(root):
    path = paths(root) / "journal.jsonl"
    marker = read_state(root).get("journal_position")
    committed = marker["bytes"] if marker and marker["revision"] > 0 else 0

    def require_committed(end):
        if end < committed:
            raise CyberSpriteError(
                "E_HISTORY_UNAVAILABLE",
                "Committed journal bytes are missing.",
                "Restore the journal tail from backup before retrying an idempotency key. "
                "Keep project.json when resetting corrupt derived history.",
                {"committed_bytes": committed, "available_bytes": end},
            )

    size = path.stat().st_size if path.exists() else 0
    require_committed(size)
    if not size:
        return
    with path.open("r+b") as stream:
        stream.seek(-1, 2)
        if stream.read(1) == b"\n":
            return
        pos = stream.tell()
        while pos:
            start = max(0, pos - 65536)
            stream.seek(start)
            data = stream.read(pos - start)
            offset = data.rfind(b"\n")
            if offset >= 0:
                pos = start + offset + 1
                break
            pos = start
        require_committed(pos)
        stream.truncate(pos)
        stream.flush()
        os.fsync(stream.fileno())


def append_journal(root, entries):
    path = paths(root) / "journal.jsonl"
    scope = _active.get()
    if scope is not None:
        path = scope.remember(path, append=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("ab") as stream:
            stream.write(journal_bytes(entries))
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as error:
        raise io_error(error, path) from error
    check_deadline()


def journal_stamp(root):
    path = paths(root) / "journal.jsonl"
    if not path.exists():
        return [0, 0]
    stat = path.stat()
    return [stat.st_size, stat.st_mtime_ns]


def read_index(root):
    path = paths(root) / "idempotency.json"
    try:
        index = json.loads(committed_bytes(path, root))
        if (
            index.get("version") == 2
            and index["stamp"] == journal_stamp(root)
            and type(index["position"]) is int
            and isinstance(index["segments"], dict)
            and isinstance(index["keys"], dict)
            and all(
                isinstance(item, dict)
                and type(item.get("position")) is int
                and "segment" in item
                and "revision" in item
                for item in index["keys"].values()
            )
        ):
            return index
    except (OSError, ValueError, KeyError, TypeError):
        pass
    index = {"version": 2, "stamp": journal_stamp(root), "position": 0, "segments": {}, "keys": {}}
    for position, (entry, segment) in enumerate(journal_tail(root, 1000, transactions=True), 1):
        index["position"] = position
        index["segments"][segment] = position
        key = entry.get("idempotency_key")
        if key is not None:
            index["keys"][key] = {
                "position": position,
                "revision": entry["revision"],
                "replay": entry.get("replay"),
                "segment": segment,
            }
    return index


def replay(root, key):
    if not key:
        return None
    item = read_index(root)["keys"].get(key)
    if item is None:
        return None
    if item.get("replay"):
        try:
            result = json.loads(
                gzip.decompress(committed_bytes(paths(root) / item["replay"], root))
            )
        except (OSError, ValueError, EOFError) as error:
            raise CyberSpriteError(
                "E_HISTORY_UNAVAILABLE",
                "Idempotent response is unavailable.",
                "Restore the retained replay file before repeating this edit with another key.",
            ) from error
    else:
        result = next(
            (
                e.get("result")
                for e, _ in reversed(journal_tail(root, 1000, transactions=True))
                if e.get("idempotency_key") == key
            ),
            None,
        )
    if result is not None:
        result["replayed"] = True
    return result


def commit_journal(root, entries, result=None):
    index = read_index(root)
    path = paths(root) / "journal.jsonl"
    if path.exists() and path.stat().st_size >= JOURNAL_SEGMENT_BYTES:
        sequence = (
            max([int(p.stem.split("-")[-1]) for p in paths(root).glob("journal-*.jsonl")] or [0])
            + 1
        )
        name = f"journal-{sequence:06d}.jsonl"
        atomic_write(paths(root) / name, path.read_bytes())
        atomic_write(path, b"")
        if "journal.jsonl" in index["segments"]:
            index["segments"][name] = index["segments"].pop("journal.jsonl")
        for item in index["keys"].values():
            if item["segment"] == "journal.jsonl":
                item["segment"] = name
    for entry in entries:
        key = entry.get("idempotency_key")
        if key and result is not None:
            digest = sha256(key.encode()).hexdigest()
            name = f"replays/r{entry['revision']:06d}-{digest}.json.gz"
            atomic_write(paths(root) / name, gzip.compress(json_bytes(result), mtime=0))
            entry["replay"] = name
        entry.pop("result", None)
        if entry.get("kind") in ("create", "external"):
            continue
        index["position"] += 1
        position = index["position"]
        index["segments"]["journal.jsonl"] = position
        if key:
            index["keys"][key] = {
                "position": position,
                "revision": entry["revision"],
                "replay": entry.get("replay"),
                "segment": "journal.jsonl",
            }
    append_journal(root, entries)
    cutoff = index["position"] - 1000
    index["keys"] = {
        key: index["keys"][key]
        for key in sorted(index["keys"])
        if index["keys"][key]["position"] > cutoff
    }
    index["segments"] = {
        name: position for name, position in sorted(index["segments"].items()) if position > cutoff
    }
    index["stamp"] = journal_stamp(root)
    atomic_write(paths(root) / "idempotency.json", json_bytes(index))


def retain_journal(root):
    index = read_index(root)
    for path in sorted(paths(root).glob("journal-*.jsonl")):
        if path.name not in index["segments"]:
            path.unlink()
    replays = {item["replay"] for item in index["keys"].values() if item.get("replay")}
    for path in sorted((paths(root) / "replays").glob("*.gz")):
        if path.relative_to(paths(root)).as_posix() not in replays:
            path.unlink()


def snapshot_path(root, revision):
    return paths(root) / f"snapshots/r{revision:06d}.json.gz"


def snapshot_bytes(p, *, canonical=None):
    data = bytearray(
        gzip.compress(
            dumps_project(p) if canonical is None else canonical, compresslevel=1, mtime=0
        )
    )
    data[9] = 255  # Normalize zlib's platform-specific OS header byte on Python 3.12.
    return bytes(data)


def restore(root, revision):
    try:
        return loads_project(gzip.decompress(committed_bytes(snapshot_path(root, revision), root)))
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
    for entry in reversed(read_journal(root, limit)):
        values = {
            k: entry.get(k) for k in ("revision", "kind", "actor", "label", "time", "changed")
        }
        values["ops"] = [item["op"] for item in entry["ops"]]
        entries.append(values)
    raw = committed_bytes(Path(root) / "project.json", root)
    external = state["last_saved_sha256"] not in (None, sha256(raw).hexdigest())
    if external:
        entries = [
            {
                "revision": json.loads(raw)["revision"],
                "kind": "external",
                "actor": "external",
                "label": None,
                "time": None,
                "changed": {},
                "ops": [],
            },
            *entries,
        ][:limit]
    return {
        "entries": entries,
        "can_undo": not external and bool(state["undo_stack"]),
        "can_redo": not external and bool(state["redo_stack"]),
    }
