import ast
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from cybersprite.pipeline.decode import decode_raster
from cybersprite.pipeline.grid import detect_grid
from cybersprite.pipeline.metrics import (
    build_pipeline_report,
    compute_metrics,
    evaluate_gates,
    pixel_sha256,
    stage_report,
)
from cybersprite.pipeline.presets import resolve_preset

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_ast_has_no_float_division_clock_or_random():
    paths = sorted((ROOT / "src/cybersprite/pipeline").glob("*.py"))
    assert len(paths) >= 10
    forbidden = {"random", "time", "datetime", "math"}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            assert not (
                isinstance(node, ast.Constant) and isinstance(node.value, (float, complex))
            ), (path, node.lineno)
            assert not isinstance(node, ast.Div), path
            if isinstance(node, ast.Import):
                assert not any(alias.name.split(".")[0] in forbidden for alias in node.names), path
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in forbidden, path
                if node.module and node.module.startswith("PIL"):
                    assert path.name == "decode.py", path
            if isinstance(node, ast.Name):
                assert node.id not in forbidden | {"float", "float32", "float64"}, path
    for path in (ROOT / "src/cybersprite/data").rglob("*.json"):

        def no_float(value, path=path):
            raise AssertionError(f"Floating data in {path}: {value}")

        json.loads(path.read_bytes(), parse_float=no_float)


def test_color_import_does_not_load_pillow():
    result = subprocess.check_output(
        [
            sys.executable,
            "-c",
            "from cybersprite.pipeline.oklab import rgb_to_oklab_fixed; import sys; "
            "assert not any(n == 'PIL' or n.startswith('PIL.') for n in sys.modules); "
            "print(rgb_to_oklab_fixed((0,0,0)))",
        ]
    )
    assert result.strip() == b"(0, 0, 0)"


def test_metrics_and_all_gates():
    palette = [(0, 0, 0, 0), (255, 255, 255, 255)]
    indices = np.array([[0, 1]], dtype=np.uint8)
    source = np.asarray(palette, dtype=np.uint8)[indices]
    metrics = compute_metrics(source, indices, palette)
    assert metrics["off_palette"] == metrics["fidelity"] == 0
    assert metrics["orphans"] == 1 and metrics["colors_per_frame"] == 1
    grid = detect_grid(source, "none")
    report = evaluate_gates(
        metrics, grid, cleanup={"min_cluster": 1}, fidelity_thresholds=(0, 0), canvas_size=(1, 1)
    )
    assert report["accepted"]
    assert [g["outcome"] for g in report["gates"] if g["name"] == "fits_canvas"] == ["warn"]
    failed = evaluate_gates(
        metrics,
        grid,
        palette_frozen=True,
        palette_added=1,
        palette_max=1,
        colors_per_frame_max=0,
        target_size=(2, 2),
    )
    assert not failed["accepted"]
    assert {g["name"] for g in failed["gates"] if g["outcome"] == "fail"} == {
        "palette_budget",
        "orphans",
        "colors_per_frame",
        "size",
    }
    invalid = compute_metrics(source, np.array([[0, 2]], dtype=np.uint8), palette)
    assert invalid["off_palette"] == 1
    assert not evaluate_gates(invalid, grid)["accepted"]
    bad_grid = {**grid, "mode": "auto", "detected": False, "grid_score": 800}
    assert not evaluate_gates(metrics, bad_grid, grid_thresholds=(900, 950))["accepted"]
    warn = evaluate_gates(
        {**metrics, "fidelity": 5},
        grid,
        grid_thresholds=(900, 1001),
        fidelity_thresholds=(10, 1),
        cleanup={"protect": [1]},
    )
    assert warn["accepted"] and sum(g["outcome"] == "warn" for g in warn["gates"]) == 2
    assert not evaluate_gates({**metrics, "frame_consistency": False}, grid)["accepted"]


def test_pixel_hash_header_vector():
    indices = np.array([[0, 1]], dtype=np.uint8)
    data = b"CSPX1" + struct.pack("<IIB", 2, 1, 0) + b"\x00\x01"
    assert pixel_sha256(indices) == hashlib.sha256(data).hexdigest()
    source = np.zeros((1, 2, 4), dtype=np.uint8)
    assert (
        pixel_sha256(source)
        == hashlib.sha256(b"CSPX1" + struct.pack("<IIB", 2, 1, 1) + bytes(8)).hexdigest()
    )


def test_metrics_detect_inconsistent_frame_sizes():
    palette = [(0, 0, 0, 0), (255, 255, 255, 255)]
    frames = [np.ones((1, 2), dtype=np.uint8), np.ones((2, 3), dtype=np.uint8)]
    sources = [np.array(palette, dtype=np.uint8)[f] for f in frames]
    metrics = compute_metrics(sources, frames, palette)
    assert metrics["sizes"] == [[2, 1], [3, 2]]
    assert metrics["frame_consistency"] is False and metrics["fidelity"] == 0


def test_presets_defaults_and_overrides():
    for name in ("exact", "upscaled", "ai", "photo"):
        settings, report = resolve_preset(name)
        assert settings["dither"]["type"] == "none"
        assert report["calibration"]["version"] == 0
    existing, _ = resolve_preset("ai", existing_project=True)
    assert existing["palette"]["mode"] == "project"
    overrides = {"grid": {"mode": "fixed", "cell_w": 4}, "cleanup": {"protect": [1]}}
    settings, report = resolve_preset("upscaled", overrides=overrides)
    assert settings["grid"]["max_cell"] == 64 and settings["grid"]["mode"] == "fixed"
    settings["cleanup"]["protect"].append(2)
    assert overrides["cleanup"]["protect"] == [1]
    assert report["overrides"] == overrides
    with pytest.raises(ValueError):
        resolve_preset("invalid")


def chunk(kind, payload):
    import zlib

    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload))
    )


def test_decode_png_and_profiles_without_using_pillow_writer(tmp_path):
    import zlib

    path = tmp_path / "original.png"
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 1, 8, 6, 0, 0, 0))
        + chunk(b"iCCP", b"synthetic\x00\x00" + zlib.compress(b"Synthetic non-ICC test bytes"))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\xff\x00\xff\x00\xff"))
        + chunk(b"IEND", b"")
    )
    frames, report = decode_raster(path)
    assert frames[0].tolist() == [[[255, 0, 0, 255], [0, 255, 0, 255]]]
    assert report["warnings"] and report["durations_ms"] == [100]
    with pytest.raises(ValueError, match="E_IO"):
        decode_raster(tmp_path / "missing.png")


def test_decode_original_bmp_and_animated_gif(tmp_path):
    # Construct original minimal files directly from their byte layouts.
    bmp = tmp_path / "synthetic.bmp"
    bmp.write_bytes(
        b"BM"
        + struct.pack("<IHHI", 62, 0, 0, 54)
        + struct.pack("<IiiHHIIiiII", 40, 2, 1, 1, 24, 0, 8, 0, 0, 0, 0)
        + b"\x00\x00\xff\x00\xff\x00\x00\x00"
    )
    frames, report = decode_raster(bmp)
    assert frames[0].tolist() == [[[255, 0, 0, 255], [0, 255, 0, 255]]]
    assert report["format"] == "BMP"
    gif = tmp_path / "synthetic.gif"
    header = b"GIF89a" + struct.pack("<HHBBB", 1, 1, 128, 0, 0) + b"\x00\x00\x00\xff\xff\xff"
    data = header
    for pixel, delay in ((0, 3), (1, 4)):
        # LZW code stream (clear=4, literal pixel, end=5), three bits/code.
        codes = (4 | pixel << 3 | 5 << 6).to_bytes(2, "little")
        data += b"\x21\xf9\x04\x09" + struct.pack("<H", delay) + b"\x00\x00"
        data += b"," + struct.pack("<HHHHB", 0, 0, 1, 1, 0) + b"\x02\x02" + codes + b"\x00"
    gif.write_bytes(data + b";")
    frames, report = decode_raster(gif)
    assert len(frames) == 2 and report["durations_ms"] == [30, 40]
    assert frames[0][0, 0, 3] == 0 and frames[1][0, 0].tolist() == [255, 255, 255, 255]


def test_decode_reports_16bit_rgb_reduction(tmp_path):
    import zlib

    path = tmp_path / "synthetic16.png"
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 16, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\x80\x00\x00\x00"))
        + chunk(b"IEND", b"")
    )
    frames, report = decode_raster(path)
    assert frames[0].dtype == np.uint8 and frames[0].shape == (1, 1, 4)
    assert "16-bit" in report["warnings"][0]["detail"]


def test_report_assembly_is_plain_serializable_data_without_mutation():
    pixels = np.zeros((2, 3), dtype=np.uint8)
    stage = stage_report(
        "quantize", "exact", pixels, metrics={"fidelity": 0}, image="stage3_quantized.png"
    )
    report = build_pipeline_report(
        source_id="SRC1",
        preset="exact",
        settings={"grid": {"mode": "none"}},
        environment={"python": "3.12"},
        plugins=[],
        steps=[stage],
        grid={"detected": True},
        gates=[{"name": "size", "outcome": "pass"}],
        result_frames=pixels,
        palette_added=[],
    )
    assert report["accepted"] and report["result"]["width"] == 3
    assert report["result"]["pixel_sha256"] == stage["pixel_sha256"]
    assert json.loads(json.dumps(report)) == report
    report["steps"][0]["metrics"]["fidelity"] = 99
    assert stage["metrics"]["fidelity"] == 0
