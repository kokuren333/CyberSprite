"""Small public data contracts for optional in-repo and external implementations."""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class IndexedImage:
    pixels: np.ndarray
    palette: list[tuple[int, int, int, int]]


@dataclass(frozen=True)
class PipelineStep:
    step: str
    method: str
    run: Callable
    level_a: bool = False
    run_frames: Callable | None = None
    plugin_api = 1


@dataclass(frozen=True)
class Validator:
    rule: str
    default_severity: str
    check: Callable
    plugin_api = 1
