"""Wall clock is confined to journal/lock metadata; never used for project content."""

import os
import sys
from datetime import UTC, datetime
from time import monotonic_ns, time_ns

from .errors import invalid


def now():
    value = os.environ.get("CYBERSPRITE_NOW")
    if value is None:
        return datetime.now(UTC).isoformat()
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Timezone is required.")
    except ValueError as error:
        raise invalid("CYBERSPRITE_NOW must be ISO 8601 with a timezone.") from error
    return value


def elapsed_clock():
    return monotonic_ns()


def filesystem_clock():
    return time_ns()


def wait_poll():
    """Yield for 25 integer milliseconds without floating-point core arithmetic."""
    if sys.platform == "win32":
        import ctypes

        sleep = ctypes.windll.kernel32.Sleep
        sleep.argtypes = [ctypes.c_uint32]
        sleep.restype = None
        sleep(25)
    else:
        import select

        select.poll().poll(25)
