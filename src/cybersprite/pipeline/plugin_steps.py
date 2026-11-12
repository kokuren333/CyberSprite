"""Selected optional methods with strict image boundaries and reproducible provenance."""

from copy import deepcopy

import numpy as np

from cybersprite.core.canonical import metadata_bytes
from cybersprite.core.errors import invalid
from cybersprite.plugins import PluginManager, plugin_error
from cybersprite.plugins.contracts import IndexedImage

BUILTINS = {
    "grid": ("auto", "fixed", "none", "target"),
    "downsample": ("auto", "center", "kcentroid", "median", "mode"),
    "quantize": ("exact", "extract", "fixed", "project"),
    "cleanup": ("components",),
    "reconstruct": (),
}


def rgba_image(value):
    if (
        not isinstance(value, np.ndarray)
        or value.dtype != np.uint8
        or value.ndim != 3
        or value.shape[2] != 4
        or not all(value.shape[:2])
    ):
        raise ValueError("output must be nonempty uint8 RGBA[H,W,4]")
    return value.copy()


def indexed_image(value):
    if not isinstance(value, IndexedImage):
        raise ValueError("output must be IndexedImage(pixels, palette)")
    pixels, palette = value.pixels, value.palette
    if (
        not isinstance(pixels, np.ndarray)
        or pixels.dtype != np.uint8
        or pixels.ndim != 2
        or not all(pixels.shape)
    ):
        raise ValueError("indexed output must be nonempty uint8[H,W]")
    if not 1 <= len(palette) <= 256 or any(
        len(color) != 4 or any(type(c) is not int or not 0 <= c <= 255 for c in color)
        for color in palette
    ):
        raise ValueError("palette must contain 1..256 integer RGBA colors")
    if int(pixels.max()) >= len(palette):
        raise ValueError("indexed output contains an out-of-palette index")
    return IndexedImage(pixels.copy(), [tuple(color) for color in palette])


class StepRunner:
    def __init__(self, manager=None):
        self.manager = manager or PluginManager(groups=("cybersprite.pipeline_steps",))
        self.records = []
        self.methods = {}

    def resolve(self, step, method):
        if method in BUILTINS[step] or method is None:
            return None
        descriptors = self.manager.descriptors("cybersprite.pipeline_steps")
        names = {d.name for d in descriptors}
        name = f"{step}.{method}" if f"{step}.{method}" in names else method
        if name not in names:
            available = sorted(
                set(BUILTINS[step])
                | {
                    d.name.removeprefix(step + ".")
                    for d in descriptors
                    if "." not in d.name or d.name.startswith(step + ".")
                }
            )
            raise invalid(
                f"Unknown {step} method {method!r}; available methods: {', '.join(available)}.",
                step=step,
                method=method,
                available_methods=available,
            )
        try:
            implementation = self.manager.load("cybersprite.pipeline_steps", name)
            if implementation.step != step or implementation.method != method:
                raise ValueError("step and method must match the selected entry point")
            if type(implementation.level_a) is not bool or not callable(implementation.run):
                raise ValueError("step requires level_a: bool and callable run")
            self.methods[(step, method)] = (name, implementation)
            return implementation
        except Exception as error:
            self.manager.discard("cybersprite.pipeline_steps", name)
            raise plugin_error(name, f"step registration failed: {error}") from error

    def run(self, step, method, images, settings, **context):
        if (step, method) not in self.methods:
            self.resolve(step, method)
        name, implementation = self.methods[(step, method)]
        descriptor = self.manager.find("cybersprite.pipeline_steps", name)
        records = dict(
            **descriptor.describe(),
            step=step,
            method=method,
            params=deepcopy(settings),
            level_a=implementation.level_a,
            determinism="level-a" if implementation.level_a else "same-platform",
        )
        outputs, metrics = [], []
        try:
            params = {k: deepcopy(v) for k, v in settings.items() if k not in ("method", "params")}
            params.update(deepcopy(settings.get("params", {})))
            params.update(context)
            for image in images:
                source = (
                    IndexedImage(image.pixels.copy(), list(image.palette))
                    if isinstance(image, IndexedImage)
                    else image.copy()
                )
                result, measurements = implementation.run(source, deepcopy(params))
                output = (
                    indexed_image(result) if step in ("quantize", "cleanup") else rgba_image(result)
                )
                if not isinstance(measurements, dict):
                    raise ValueError("step metrics must be a dictionary")
                metadata_bytes(measurements)
                outputs.append(output)
                metrics.append(measurements)
            shapes = [
                im.pixels.shape if isinstance(im, IndexedImage) else im.shape for im in outputs
            ]
            if not shapes or any(shape != shapes[0] for shape in shapes):
                raise ValueError("step must preserve a consistent shape across frames")
            if step in ("quantize", "cleanup"):
                if any(im.palette != outputs[0].palette for im in outputs):
                    raise ValueError("step must return the same locked palette for all frames")
            if step == "cleanup" and any(
                im.palette != src.palette or im.pixels.shape != src.pixels.shape
                for im, src in zip(outputs, images, strict=True)
            ):
                raise ValueError("cleanup must preserve palette and image dimensions")
        except Exception as error:
            raise plugin_error(name, f"{step} failed: {error}", step=step, method=method) from error
        self.records.append(records)
        return outputs, {"method": method, "frames": metrics}
