"""Bundled entry-point factories; upstream packages are loaded only when selected."""

from importlib import import_module

from cybersprite.core.errors import CyberSpriteError
from cybersprite.plugins.contracts import PipelineStep


def _make(method, *, batch=False):
    adapter = import_module("cybersprite.pipeline.external." + method)
    ok, reason = adapter.available()
    if not ok:
        raise CyberSpriteError(
            "E_PLUGIN",
            f"External pixelizer {method!r} is unavailable.",
            reason,
            {"method": method, "installation": adapter.INSTALL},
        )

    def parameters(params):
        return {key: value for key, value in params.items() if key not in ("grid", "grid_settings")}

    def run(image, params):
        return adapter.run(image, parameters(params))

    def run_frames(images, params):
        outputs, metrics = adapter.run(images, parameters(params))
        return outputs, [metrics for _ in outputs]

    return PipelineStep("reconstruct", method, run, False, run_frames if batch else None)


def fixer():
    return _make("pixel_art_fixer")


def proper():
    return _make("proper_pixel_art", batch=True)


def pixeloe():
    return _make("pixeloe")


fixer.plugin_api = proper.plugin_api = pixeloe.plugin_api = 1
