"""Validation and lazy loading for user-installed, non-Level-A tools."""

import importlib
from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError, version
from threading import RLock

import numpy as np

from cybersprite.core.errors import CyberSpriteError, invalid

LOCK = RLock()


def describe(name, distribution, license):
    try:
        installed = version(distribution)
    except PackageNotFoundError:
        installed = "uninstalled"
    return {"name": name, "version": installed, "license": license, "level_a": False}


def load(module, installation):
    try:
        return importlib.import_module(module)
    except (ImportError, OSError) as error:
        raise CyberSpriteError(
            "E_PLUGIN",
            f"Cannot load external pixelizer {module}: {error}",
            installation,
            {"plugin": module},
        ) from error


def available(module, installation):
    try:
        load(module, installation)
    except CyberSpriteError as error:
        return False, f"{error.message} {installation}"
    return (
        True,
        "User-installed runtime detected; review its dependency licenses separately.",
    )


def inputs(rgba, params, allowed, *, multiple=False):
    if not isinstance(params, dict) or set(params) - set(allowed):
        raise invalid("Unknown external pixelizer parameters.", allowed=sorted(allowed))
    single = isinstance(rgba, np.ndarray)
    frames = (
        [rgba] if single else list(rgba) if multiple and isinstance(rgba, (list, tuple)) else []
    )
    if not frames or any(
        not isinstance(frame, np.ndarray)
        or frame.dtype != np.uint8
        or frame.ndim != 3
        or frame.shape[2] != 4
        or min(frame.shape[:2]) < 1
        for frame in frames
    ):
        raise invalid("External pixelizers require nonempty uint8 H x W x 4 RGBA arrays.")
    if any(frame.shape != frames[0].shape for frame in frames):
        raise invalid("All external pixelizer frames must have the same dimensions.")
    return [np.ascontiguousarray(frame).copy() for frame in frames], single


def positive(params, name, default=None, maximum=65536):
    value = params.get(name, default)
    if type(value) is not int or not 1 <= value <= maximum:
        raise invalid(f"External pixelizer {name} must be an integer from 1 to {maximum}.")
    return value


def output(value):
    result = np.asarray(value)
    if (
        result.dtype != np.uint8
        or result.ndim != 3
        or result.shape[2] != 4
        or min(result.shape[:2]) < 1
    ):
        raise CyberSpriteError(
            "E_PLUGIN",
            "External pixelizer returned invalid RGBA pixels.",
            "Use a supported upstream version returning uint8 H x W x 4 pixels.",
        )
    return result.copy()


@contextmanager
def serial_cv(module):
    """Serialize adapter calls and restore the upstream thread count."""
    with LOCK:
        previous = module.getNumThreads()
        module.setNumThreads(1)
        module.setRNGSeed(0)
        try:
            yield
        finally:
            module.setNumThreads(previous)
