"""Explicit request save context, cooperative deadlines, and durable rollback intent."""

import base64
import json
import os
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from .errors import CyberSpriteError

_active: ContextVar["SaveContext | None"] = ContextVar("core_execution", default=None)


class DeadlineExpired(BaseException):
    """Bypass recoverable preview errors and finish rollback before replying."""


def check_deadline():
    scope = _active.get()
    if scope is not None:
        scope.check()


def intent_path(root):
    return Path(root) / ".cybersprite/history/pending.json"


def _records(root):
    path = intent_path(root)
    scope = _active.get()
    if scope is not None:
        path = scope.resolve(path)
    try:
        records = json.loads(path.read_bytes())["files"]
        if not isinstance(records, list) or not all(
            isinstance(item, dict)
            and isinstance(item.get("path"), str)
            and (
                ("data" in item and (item["data"] is None or isinstance(item["data"], str)))
                or (type(item.get("length")) is int and item["length"] >= 0)
            )
            for item in records
        ):
            raise ValueError("Invalid pending file records.")
        for item in records:
            if item.get("data") is not None:
                base64.b64decode(item["data"], validate=True)
        return records
    except FileNotFoundError:
        return []
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CyberSpriteError(
            "E_HISTORY_UNAVAILABLE",
            "Pending save record is corrupt.",
            "Keep project.json and restore pending.json from a backup before retrying.",
        ) from error


def committed_bytes(path, root):
    """Readers observe pre-save bytes until the durable intent is removed."""
    path = Path(path)
    scope = _active.get()
    if scope is not None:
        path = scope.resolve(path)
    if scope is None or scope.lock is None:
        name = path.absolute()
        while True:
            records = _records(root)
            missing = False
            data = None
            for item in records:
                if Path(item["path"]) == name and "data" in item:
                    missing = item["data"] is None
                    if not missing:
                        data = base64.b64decode(item["data"])
                    break
            else:
                try:
                    data = path.read_bytes()
                except FileNotFoundError:
                    missing = True
            if records == _records(root):
                if missing:
                    raise FileNotFoundError(path)
                return data
            check_deadline()
    return path.read_bytes()


def _restore(records):
    from .history import _atomic_write

    for item in reversed(records):
        path = Path(item["path"])
        if "length" in item:
            with path.open("r+b") as stream:
                stream.truncate(item["length"])
                stream.flush()
                os.fsync(stream.fileno())
        elif item["data"] is None:
            path.unlink(missing_ok=True)
        else:
            data = base64.b64decode(item["data"])
            if not path.exists() or path.read_bytes() != data:
                _atomic_write(path, data)


def recover_pending(root):
    """Called only after acquiring the real writer lock, before reading history."""
    records = _records(root)
    scope = _active.get()
    # Intent is local derived metadata, never authority to write arbitrary paths.
    for item in records:
        path = Path(item["path"]).resolve()
        if scope is not None and scope.resolver is not None:
            scope.resolve(path)
        elif not path.is_relative_to(Path(root).resolve()):
            raise CyberSpriteError(
                "E_HISTORY_UNAVAILABLE",
                "Pending save refers outside the project.",
                "Retry in MCP with the original allow-dir, or restore that output manually.",
            )
    _restore(records)
    intent_path(root).unlink(missing_ok=True)


class SaveContext:
    def __init__(self, root, *, check=None, resolve=None, durable=True, lock=None):
        self.root = Path(root).absolute()
        self.checker = check
        self.resolver = resolve
        self.durable = durable
        self.lock = lock
        self.backups = {}
        self.retention = []

    def check(self):
        if self.checker is not None:
            self.checker()

    def resolve(self, path):
        return self.resolver(path) if self.resolver is not None else Path(path).absolute()

    def remember(self, path, *, append=False):
        from .canonical import json_bytes
        from .history import _atomic_write

        self.check()
        path = self.resolve(path)
        changed = path not in self.backups
        if changed:
            item = {"path": path.as_posix()}
            if append and path.exists():
                item["length"] = path.stat().st_size
            else:
                item["data"] = (
                    base64.b64encode(path.read_bytes()).decode("ascii") if path.exists() else None
                )
            self.backups[path] = item
        elif not append and "length" in self.backups[path]:
            length = self.backups[path]["length"]
            self.backups[path] = {
                "path": path.as_posix(),
                "data": base64.b64encode(path.read_bytes()[:length]).decode("ascii"),
            }
            changed = True
        if changed and self.durable:
            _atomic_write(
                self.resolve(intent_path(self.root)),
                json_bytes({"files": list(self.backups.values())}),
            )
        return path

    def rollback(self):
        _restore(list(self.backups.values()))
        if self.durable:
            intent_path(self.root).unlink(missing_ok=True)

    def finish(self):
        self.check()
        if self.durable:
            intent_path(self.root).unlink(missing_ok=True)

    def maintain(self):
        for function, root in self.retention:
            try:
                function(root)
            except (OSError, CyberSpriteError):
                pass


@contextmanager
def save_context(root, **options):
    """Nested transactions share the caller's response-lifetime save context."""
    current = _active.get()
    if current is not None:
        current.check()
        yield current
        current.check()
        return
    scope = SaveContext(root, **options)
    token = _active.set(scope)
    try:
        scope.check()
        yield scope
        scope.finish()
    except BaseException:
        scope.rollback()
        raise
    finally:
        _active.reset(token)
    scope.maintain()


def defer_retention(function, root):
    scope = _active.get()
    if scope is None:
        function(root)
    elif (function, root) not in scope.retention:
        scope.retention.append((function, root))
