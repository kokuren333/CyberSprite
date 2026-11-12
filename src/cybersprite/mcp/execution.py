"""MCP policy adapter for the core explicit request save context."""

from contextlib import nullcontext
from time import monotonic_ns

from cybersprite.core import history
from cybersprite.core.execution import (
    DeadlineExpired as DeadlineExpired,
)
from cybersprite.core.execution import (
    SaveContext,
)
from cybersprite.core.execution import (
    _active as _active,
)


class Execution:
    def __init__(self, policy, root, actor, seconds, *, writable=True, clock=None):
        self.policy, self.root, self.actor = policy, root, actor
        self.clock = clock or monotonic_ns
        self.deadline = self.clock() + seconds * 1_000_000_000
        self.writable = writable

    def check(self):
        if self.clock() >= self.deadline:
            raise DeadlineExpired()

    def run(self, function):
        scope = SaveContext(
            self.root,
            check=self.check,
            resolve=self.policy.resolve,
            durable=self.writable,
        )
        token = _active.set(scope)
        lock = history.ProjectLock(self.root, self.actor) if self.writable else nullcontext()
        try:
            self.check()
            with lock as held:
                scope.lock = held
                try:
                    self.check()
                    result = function()
                    scope.finish()
                except BaseException:
                    scope.rollback()
                    raise
                scope.maintain()
        finally:
            _active.reset(token)
        return result
