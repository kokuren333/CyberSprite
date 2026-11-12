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


@pytest.mark.parametrize("name", ["pixel_art_fixer", "proper_pixel_art", "pixeloe"])
def test_real_registered_pipeline(enabled, tmp_path, name):
    from importlib import import_module

    adapter = import_module("cybersprite.pipeline.external." + name)
    ok, reason = adapter.available()
    if not ok:
        pytest.skip(reason)
    image = np.zeros((64, 64, 4), dtype=np.uint8)
    image[16:48, 16:48] = (200, 100, 40, 255)
    params = {"target_w": 8, "target_h": 8} if name == "pixeloe" else {}
    frames, palette, report = run_pipeline(
        image,
        tmp_path / name,
        preset="ai",
        overrides={"reconstruct": {"method": name, "params": params}},
    )
    assert frames[0].size and palette
    record = report["plugins"][0]
    assert record["implementation"]["version"] != "uninstalled"
    assert record["method"] == name and record["level_a"] is False
    assert report["verified"]
