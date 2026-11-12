"""Request-scoped deadlines and rollback around the registry persistence boundary.

Hooks are installed once. ContextVar dispatch keeps ordinary CLI calls and other
threads unchanged. MCP borrows one outer core lock through the entire execution,
serialization and rollback, so another writer cannot observe a failed revision.
No alternate project serializer or mutation implementation lives here.
"""

import sys
from contextvars import ContextVar
from threading import Lock
from time import monotonic_ns

from cybersprite.core import history

_active = ContextVar("mcp_execution", default=None)
_install_lock = Lock()
_installed = False
_atomic_write = history.atomic_write
_project_lock = history.ProjectLock
_retain = history.retain
_retain_previews = history.retain_previews


class DeadlineExpired(BaseException):
    """Must bypass the core's post-commit preview error recovery."""


def _write(path, data):
    scope = _active.get()
    if scope is not None:
        path = scope.policy.resolve(path)
        scope.check()
        if path not in scope.backups:
            scope.backups[path] = path.read_bytes() if path.exists() else None
    _atomic_write(path, data)
    if scope is not None:
        scope.check()


class _BorrowLock:
    def __init__(self, scope):
        self.scope = scope

    def __enter__(self):
        self.scope.check()
        return self.scope.lock

    def __exit__(self, *_):
        return False

    def require_owned(self):
        self.scope.check()
        self.scope.lock.require_owned()


def _lock(root, actor):
    scope = _active.get()
    if scope is not None and scope.policy.resolve(root) == scope.root:
        return _BorrowLock(scope)
    return _project_lock(root, actor)


def _retention(function, root):
    scope = _active.get()
    if scope is None:
        return function(root)
    scope.retention.add((function, root))


def install_hooks():
    global _installed
    with _install_lock:
        if not _installed:
            history.atomic_write = _write
            history.ProjectLock = _lock
            history.retain = lambda root: _retention(_retain, root)
            history.retain_previews = lambda root: _retention(_retain_previews, root)
            _installed = True


class Execution:
    def __init__(self, policy, root, actor, seconds):
        self.policy, self.root = policy, root
        self.actor = actor
        self.deadline = monotonic_ns() + seconds * 1_000_000_000
        self.backups = {}
        self.retention = set()

    def check(self):
        if monotonic_ns() >= self.deadline:
            raise DeadlineExpired()

    def trace(self, frame, event, arg):
        self.check()
        return self.trace

    def run(self, function):
        install_hooks()
        # The lock is held before touching revision/history, and through rollback.
        with _project_lock(self.root, self.actor) as self.lock:
            token = _active.set(self)
            previous_trace = sys.gettrace()
            try:
                self.check()
                sys.settrace(self.trace)
                result = function()
                self.check()
            except BaseException:
                sys.settrace(previous_trace)
                _active.reset(token)
                # Restore through core persistence, in reverse write order.
                for path, data in reversed(list(self.backups.items())):
                    if data is None:
                        path.unlink(missing_ok=True)
                    else:
                        _atomic_write(path, data)
                raise
            else:
                sys.settrace(previous_trace)
                _active.reset(token)
                for function, root in sorted(self.retention, key=lambda item: item[0].__name__):
                    try:
                        function(root)
                    except Exception:
                        # Derived retention cannot invalidate a committed request.
                        pass
                return result
