"""Adapter contracts; real upstream tests explicitly skip when not user-installed."""

import importlib
from types import SimpleNamespace

import numpy as np
import pytest

from cybersprite.core.errors import CyberSpriteError
from cybersprite.pipeline.external import _common, pixel_art_fixer, pixeloe, proper_pixel_art


@pytest.fixture
def image():
    pixels = np.zeros((8, 8, 4), dtype=np.uint8)
    pixels[2:6, 2:6] = (200, 100, 40, 255)
    return pixels


@pytest.mark.parametrize("adapter", [pixel_art_fixer, proper_pixel_art, pixeloe])
def test_describe_and_invalid_input(adapter, image):
    description = adapter.describe()
    assert set(description) == {"name", "version", "license", "level_a"}
    assert description["level_a"] is False
    for bad in (image.astype(np.int64), image[:, :, :3], np.empty((0, 2, 4), dtype=np.uint8)):
        with pytest.raises(CyberSpriteError, match="uint8 H x W x 4"):
            adapter.run(bad, {})
    with pytest.raises(CyberSpriteError, match="Unknown external"):
        adapter.run(image, {"arbitrary_code": "ignored"})


def test_missing_runtime_is_actionable(monkeypatch, image):
    def absent(name):
        raise ImportError("not installed")

    monkeypatch.setattr(_common.importlib, "import_module", absent)
    for adapter in (pixel_art_fixer, proper_pixel_art, pixeloe):
        available, reason = adapter.available()
        assert (
            not available
            and "Install" in reason
            and "license" in reason.lower()
            or "LGPL" in reason
        )
    with pytest.raises(CyberSpriteError) as error:
        pixel_art_fixer.run(image, {})
    assert error.value.code == "E_PLUGIN"


def test_fixer_contract_and_thread_restoration(monkeypatch, image):
    threads = [4]
    seeds = []
    cv = SimpleNamespace(
        getNumThreads=lambda: threads[0],
        setNumThreads=lambda n: threads.__setitem__(0, n),
        setRNGSeed=seeds.append,
    )
    grid = {"step_x": 2, "step_y": 2, "cols": 4, "rows": 4, "consensus": 0.9}

    def reconstruct(pixels, *args):
        assert args == (2, 2, 4, 4) and threads == [1]
        return pixels[::2, ::2]

    modules = {
        "pixelfixer": SimpleNamespace(detect=lambda pixels: grid),
        "pixelfixer.reconstruct": SimpleNamespace(reconstruct=reconstruct),
        "cv2": cv,
    }
    monkeypatch.setattr(_common, "load", lambda name, installation: modules[name])
    before = image.copy()
    out, metrics = pixel_art_fixer.run(image, {})
    assert np.array_equal(out, image[::2, ::2]) and np.array_equal(image, before)
    assert metrics["grid"] == grid and not metrics["quantized"]
    assert threads == [4] and seeds == [0]

    def broken(*args):
        raise RuntimeError("upstream failure")

    modules["pixelfixer"].detect = broken
    with pytest.raises(RuntimeError, match="upstream failure"):
        pixel_art_fixer.run(image, {})
    assert threads == [4]


def test_proper_frames_use_one_mesh_without_video(monkeypatch, image):
    threads = [4]
    cv = SimpleNamespace(
        getNumThreads=lambda: threads[0],
        setNumThreads=lambda n: threads.__setitem__(0, n),
        setRNGSeed=lambda n: None,
    )
    seen = []
    meshes = [([0, 4, 8], [0, 4, 8]), ([0, 2, 4, 6, 8], [0, 2, 4, 6, 8])]

    def config(**kwargs):
        return SimpleNamespace(
            colors=SimpleNamespace(method="palette", dominant=SimpleNamespace(merge_distance=12))
        )

    def pixelate(frame, config):
        assert config.colors.method == "dominant" and config.colors.dominant.merge_distance == 0
        return SimpleNamespace(mesh=meshes.pop(0), upscale_factor=1, pixel_width=4)

    def sample(frame, mesh, **kwargs):
        seen.append(mesh)
        return np.asarray(frame)[::4, ::4]

    modules = {
        "proper_pixel_art": SimpleNamespace(PixelateConfig=config, pixelate=pixelate),
        "proper_pixel_art.image": SimpleNamespace(downsample=sample),
        "proper_pixel_art.utils": SimpleNamespace(scale_img=lambda image, factor: image),
        "cv2": cv,
    }
    monkeypatch.setattr(_common, "load", lambda name, installation: modules[name])
    out, metrics = proper_pixel_art.run([image, image.copy()], {})
    assert len(out) == 2 and all(frame.shape == (2, 2, 4) for frame in out)
    assert seen[0] is seen[1] and metrics["selected_frame"] == 0
    assert metrics["shared_palette"] == [[0, 0, 0, 0], [200, 100, 40, 255]]
    assert threads == [4]


@pytest.mark.parametrize("name", ["pixel_art_fixer", "proper_pixel_art", "pixeloe"])
def test_real_user_runtime(name, image):
    adapter = importlib.import_module("cybersprite.pipeline.external." + name)
    available, reason = adapter.available()
    if not available:
        pytest.skip(reason)
    params = {"target_w": 4, "target_h": 4} if name == "pixeloe" else {}
    first, metrics = adapter.run(image, params)
    second, _ = adapter.run(image, params)
    assert np.array_equal(first, second)
    assert first.dtype == np.uint8 and first.shape[2] == 4
    assert metrics["level_a"] is False
