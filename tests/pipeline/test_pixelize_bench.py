"""Fixed engineering vectors for offline recipes, metrics, and benchmark smoke."""

import numpy as np

from cybersprite.pipeline.defaults import load_defaults
from cybersprite.pipeline.grid import detect_grid
from cybersprite.pipeline.metrics import evaluate_gates
from cybersprite.pipeline.presets import resolve_preset
from tools.calibrate_pixelize_gates import calibrate
from tools.pixelize_bench import benchmark, blur, cases, compare


def test_integer_blur_vector():
    pixels = np.zeros((1, 3, 4), dtype=np.uint8)
    pixels[0, 1] = 255
    assert blur(pixels)[0, :, 0].tolist() == [64, 128, 64]


def test_recipes_and_palette_mapping():
    truth = np.asarray(
        [[[0, 0, 0, 0], [200, 40, 10, 255]], [[20, 40, 180, 255], [200, 40, 10, 255]]],
        dtype=np.uint8,
    )
    first, second = list(cases(truth)), list(cases(truth))
    assert len(first) == 19
    assert all(np.array_equal(a[2], b[2]) for a, b in zip(first, second, strict=True))
    assert np.array_equal(first[0][2][::2, ::2], truth)
    shifted = truth.copy()
    shifted[shifted[:, :, 3] > 0, 0] += 1
    metrics = compare(shifted, truth, [2, 1], (4, 4, 4))
    assert metrics["size_exact"] and metrics["mask_iou"] == 1
    assert metrics["exact_rgba"] == 0.25 and metrics["mapped_exact_rgba"] == 1
    assert metrics["grid_step_error"] == 0
    swapped = truth.copy()
    swapped[1, 0, :3] = (200, 40, 10)
    swapped[0, 1, :3] = swapped[1, 1, :3] = (20, 40, 180)
    assert compare(swapped, truth, [2, 1], (4, 4, 4))["mapped_exact_rgba"] == 1
    wrong = compare(truth.repeat(2, 0), truth, [2, 1], (4, 4, 4))
    assert not wrong["size_exact"] and wrong["exact_rgba"] is None


def test_externalized_thresholds_affect_final_gate():
    settings, _ = resolve_preset(
        "ai",
        overrides={
            "gates": {"boundary_alignment": [1001, 1001]},
            "grid": {"candidate_agreement": 800},
        },
    )
    assert settings["grid"]["candidate_agreement"] == 800
    assert settings["gates"]["snap_fidelity"] == load_defaults()["common"]["gates"]["snap_fidelity"]
    pixels = np.zeros((8, 8, 4), dtype=np.uint8)
    pixels[2:6, 2:6] = 255
    grid = detect_grid(pixels)
    assert grid["detected"]
    metrics = {
        "palette_size": 2,
        "off_palette": 0,
        "orphans": 0,
        "colors_per_frame": 1,
        "fidelity": 0,
        "sizes": [[4, 4]],
        "frame_consistency": True,
    }
    assert evaluate_gates(metrics, grid)["accepted"]
    assert not evaluate_gates(metrics, grid, boundary_alignment=[1001, 1001])["accepted"]
    grid["snap_variance"] = 501
    gates = evaluate_gates(metrics, grid, snap_fidelity=[500, 0])["gates"]
    assert next(g for g in gates if g["name"] == "snap_fidelity")["outcome"] == "fail"
    grid["mode"] = "fixed"
    assert evaluate_gates(metrics, grid, snap_fidelity=[500, 0])["accepted"]


def test_bench_three_cases(tmp_path):
    report = benchmark(tmp_path, limit=1, smoke=True, repeats=1, generated=False)
    builtin = [r for r in report["records"] if r["method"] == "builtin"]
    assert len(builtin) == 3 and all("metrics" in row for row in builtin)
    assert (tmp_path / "results.json").is_file()


def test_calibration_timeouts_are_not_gate_rejections(tmp_path, monkeypatch):
    import json
    import subprocess

    def timed_out(command, **options):
        raise subprocess.TimeoutExpired(command, options["timeout"])

    monkeypatch.setattr(subprocess, "run", timed_out)
    calibrate(tmp_path, repeats=1, categories=["e"], timeout=1)
    result = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert result["summary"]["e"] == {"n": 12, "accepted": 0, "rejected": 0, "errors": 12}
    assert all(row["accepted"] is None for row in result["records"])
