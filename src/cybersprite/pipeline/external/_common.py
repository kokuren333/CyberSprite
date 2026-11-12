"""Validation and lazy loading for user-installed, non-Level-A tools."""

import importlib
import logging
import sys
from contextlib import contextmanager
from importlib.abc import MetaPathFinder
from importlib.metadata import PackageNotFoundError, version
from threading import RLock, get_ident

import numpy as np

from cybersprite.core.errors import CyberSpriteError, invalid

LOCK = RLock()


@contextmanager
def without_optional_namespace(namespace):
    """Let a CPU-only upstream import use its optional-backend ImportError fallback.

    The finder applies only to this thread and is removed even after import failure.
    Never redirect process-wide native stdout: it may carry another MCP response.
    """
    owner = get_ident()

    class ExcludeOptional(MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if get_ident() == owner and (
                fullname == namespace or fullname.startswith(namespace + ".")
            ):
                raise ModuleNotFoundError(
                    f"CPU-only adapter does not initialize optional backend {fullname}.",
                    name=fullname,
                )
            return None

    with LOCK:
        finder = ExcludeOptional()
        sys.meta_path.insert(0, finder)
        try:
            yield
        finally:
            sys.meta_path.remove(finder)


@contextmanager
def muted_logger(name):
    """Keep upstream handlers bound to stdout from corrupting CLI/MCP JSON."""
    logger = logging.getLogger(name)
    previous = logger.disabled
    logger.disabled = True
    try:
        yield
    finally:
        logger.disabled = previous


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
