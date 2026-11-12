"""Bundled registration, batch boundaries, availability and upstream provenance."""

from types import SimpleNamespace

import numpy as np
import pytest

from cybersprite.core.errors import CyberSpriteError
from cybersprite.pipeline.external import pixel_art_fixer, proper_pixel_art
from cybersprite.pipeline.plugin_steps import StepRunner
from cybersprite.pipeline.runner import run_pipeline
from cybersprite.plugins.contracts import PipelineStep


@pytest.fixture
def enabled(monkeypatch, tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "config.toml").write_text(
        '[plugins]\nenabled = ["reconstruct.pixel_art_fixer", '
        '"reconstruct.proper_pixel_art", "reconstruct.pixeloe"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("CYBERSPRITE_CONFIG_DIR", str(config))


def test_bundled_unavailable_keeps_install_hint(enabled, monkeypatch):
    monkeypatch.setattr(pixel_art_fixer, "available", lambda: (False, pixel_art_fixer.INSTALL))
    with pytest.raises(CyberSpriteError) as caught:
        StepRunner().resolve("reconstruct", "pixel_art_fixer")
    assert caught.value.code == "E_PLUGIN"
    assert "PYTHONPATH" in caught.value.hint and "LGPL" in caught.value.hint


@pytest.mark.parametrize("surface", ["cli", "mcp"])
def test_unavailable_reaches_surface(enabled, tmp_path, monkeypatch, surface):
    import json

    from cybersprite.formats.png import encode_png

    monkeypatch.setattr(pixel_art_fixer, "available", lambda: (False, pixel_art_fixer.INSTALL))
    (tmp_path / "input.png").write_bytes(encode_png(np.full((4, 4, 4), 255, dtype=np.uint8)))
    pipeline = {"reconstruct": {"method": "pixel_art_fixer"}}
    if surface == "cli":
        from click.testing import CliRunner

        from cybersprite.cli import cli

        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(
            cli, ["convert", "input.png", "output.png", "--pipeline", json.dumps(pipeline)]
        )
        assert result.exit_code != 0
        value = json.loads(result.stdout)
    else:
        pytest.importorskip("mcp.server")
        from cybersprite.mcp.server import MCPService

        response = MCPService(root=tmp_path).call(
            "import_image",
            {
                "project": "p",
                "files": ["input.png"],
                "pipeline": pipeline,
                "provenance": {"license": "unknown"},
                "preview": "none",
            },
        )
        assert response.is_error
        value = response.structured_content
    assert value["error"]["code"] == "E_PLUGIN"
    assert "PYTHONPATH" in value["error"]["hint"] and "LGPL" in value["error"]["hint"]
    assert not (tmp_path / "p/project.json").exists()
    assert not (tmp_path / "output.png").exists()


def test_bundled_proper_batch_and_report(enabled, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(proper_pixel_art, "available", lambda: (True, "test runtime"))

    def run(images, params):
        calls.append((images, params))
        return [im[::2, ::2] for im in images], {
            "name": "proper-pixel-art",
            "version": "test-2.0.0",
            "license": "MIT",
            "level_a": False,
            "grid": {"selected_frame": 0},
        }

    monkeypatch.setattr(proper_pixel_art, "run", run)
    frames = [np.full((4, 4, 4), (30, 60, 90, 255), dtype=np.uint8)] * 2
    result, palette, report = run_pipeline(
        frames,
        tmp_path / "stages",
        preset="exact",
        overrides={"reconstruct": {"method": "proper_pixel_art", "params": {"pixel_width": 2}}},
    )
    assert len(calls) == 1 and len(calls[0][0]) == 2
    assert calls[0][1] == {"pixel_width": 2}
    assert all(im.shape == (2, 2) for im in result) and len(palette) == 2
    assert report["plugins"][0]["implementation"]["version"] == "test-2.0.0"
    assert report["plugins"][0]["level_a"] is False
    assert report["determinism"] == "same-platform"
    assert report["gate_scope"] == "reconstructed-output" and not report["input_grid_evaluated"]
    assert len(report["steps"][1]["metrics"]["frames"]) == 2


def test_batch_cannot_drop_frames():
    implementation = PipelineStep(
        "reconstruct",
        "bad",
        lambda im, params: (im, {}),
        run_frames=lambda ims, params: (ims[:1], [{}]),
    )
    manager = SimpleNamespace(find=lambda *args: SimpleNamespace(describe=lambda: {}))
    runner = StepRunner(manager)
    runner.methods[("reconstruct", "bad")] = ("bad", implementation)
    with pytest.raises(CyberSpriteError, match="one image and metrics"):
        runner.run("reconstruct", "bad", [np.zeros((2, 2, 4), dtype=np.uint8)] * 2, {})


def test_benchmark_preserves_indexed_pipeline_file(enabled, monkeypatch, tmp_path):
    from cybersprite.formats.png import decode_png
    from tools.pixelize_bench import benchmark

    monkeypatch.setattr(proper_pixel_art, "available", lambda: (True, "test runtime"))
    monkeypatch.setattr(
        proper_pixel_art,
        "run",
        lambda images, params: (
            [im[::2, ::2] for im in images],
            {
                "name": "proper-pixel-art",
                "version": "test-2.0.0",
                "license": "MIT",
                "level_a": False,
            },
        ),
    )
    result = benchmark(
        tmp_path / "bench",
        limit=1,
        smoke=True,
        repeats=1,
        generated=False,
        selected_methods=["proper_pixel_art"],
    )
    assert len(result["records"]) == 3
    for row in result["records"]:
        assert "error" not in row
        directory = (
            tmp_path / "bench" / row["source"].removesuffix(".png") / row["recipe"] / row["method"]
        )
        assert decode_png((directory / "result.png").read_bytes()).pixels.ndim == 2
        assert decode_png((directory / "comparison.png").read_bytes()).pixels.ndim == 3


@pytest.mark.parametrize("name", ["pixel_art_fixer", "proper_pixel_art", "pixeloe"])
def test_real_registered_pipeline(enabled, tmp_path, name):
    from importlib import import_module

    adapter = import_module("cybersprite.pipeline.external." + name)
    ok, reason = adapter.available()
    if not ok:
        pytest.skip(reason)
    image = np.zeros((64, 64, 4), dtype=np.uint8)
    image[16:48, 16:48] = (200, 100, 40, 255)
    images = image
    if name == "proper_pixel_art":
        second = image.copy()
        second[16:48, 16:48] = (40, 200, 100, 255)
        images = [image, second]
    params = {"target_w": 8, "target_h": 8} if name == "pixeloe" else {}
    frames, palette, report = run_pipeline(
        images,
        tmp_path / name,
        preset="ai",
        overrides={"reconstruct": {"method": name, "params": params}},
    )
    assert frames[0].size and palette
    record = report["plugins"][0]
    assert record["implementation"]["version"] != "uninstalled"
    assert (
        record["implementation"]["params"] == report["steps"][1]["metrics"]["frames"][0]["params"]
    )
    assert record["method"] == name and record["level_a"] is False
    assert report["verified"]
    if name == "proper_pixel_art":
        assert len(frames) == 2 and frames[0].shape == frames[1].shape
        metrics = report["steps"][1]["metrics"]["frames"]
        assert metrics[0]["grid"] == metrics[1]["grid"]
        assert metrics[0]["shared_palette"] == metrics[1]["shared_palette"]
