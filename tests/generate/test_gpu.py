"""Manual GPU smoke test. Never downloads weights or accepts licenses on its own."""

import os
from pathlib import Path

import pytest

from tools.verify_generation_gpu import cli as gpu_cli

pytestmark = [
    pytest.mark.gpu,
    pytest.mark.skipif(
        os.environ.get("CYBERSPRITE_RUN_GPU") != "1",
        reason="Set CYBERSPRITE_RUN_GPU=1 with an accepted local SDXL+LoRA configuration.",
    ),
]


def test_real_sdxl_cli_generation():
    from cybersprite.formats.png import decode_png

    # Require an explicit external destination; generated images never enter test fixtures.
    output = Path(os.environ["CYBERSPRITE_GPU_CHECK_DIR"]).resolve()
    root = Path(__file__).resolve().parents[2]
    assert not output.is_relative_to(root)
    output.mkdir(parents=True, exist_ok=True)
    project = output / "pytest-gpu.csprite"
    response, measurement = gpu_cli(
        [
            "-p",
            str(project),
            "gen",
            "run",
            "--backend",
            "diffusers",
            "--model",
            os.environ.get("CYBERSPRITE_GPU_MODEL", "sdxl-pixel"),
            "--prompt",
            "pixel art, a small wooden chest, simple, flat colors, plain white background",
            "--width",
            "1024",
            "--height",
            "1024",
            "--seed",
            "42",
            "--params",
            '{"num_inference_steps":30,"guidance_scale":7,"deterministic":true}',
        ],
        output,
        "pytest-gpu",
    )
    assert measurement["returncode"] == 0, response
    assert response["ok"]
    source = response["result"]["sources"][0]
    from cybersprite.core.sources import find_source, read_manifest

    record = find_source(read_manifest(project), source)
    pixels = decode_png((project / record.files[0].path).read_bytes()).rgba()
    assert pixels.shape == (1024, 1024, 4)
    assert record.seed == 42 and record.params["deterministic"]
    assert record.model.adapters
    assert not (project / "project.json").exists()
