"""Portable fixed grid/signal vectors and hand-calculated small cases."""

import json
from pathlib import Path

import numpy as np
import pytest

from cybersprite.pipeline.grid import _signals, detect_grid

VECTORS = Path(__file__).resolve().parents[1] / "vectors/grid"


@pytest.mark.parametrize("path", sorted(VECTORS.glob("*.json")), ids=lambda p: p.stem)
def test_grid_vector(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    frames = [
        np.dstack([gray, gray, gray, np.full_like(gray, value["alpha"])])
        for gray in np.asarray(value["grayscale_frames"], dtype=np.uint8)
    ]
    actual = detect_grid(frames, **value["settings"])
    assert json.loads(json.dumps(actual)) == value["expected"]
    for axis in (0, 1):
        assert [s.tolist() for s in _signals(frames, axis)] == value["signals"][str(axis)]


def test_hand_calculated_plateau_and_period():
    # Three channels: [10,20,0,10,10,0,20] => significant raw energy * 3.
    gray = np.tile(np.array([0, 10, 30, 30, 20, 10, 10, 30], dtype=np.uint8), (8, 1))
    frame = np.dstack([gray, gray, gray, np.full_like(gray, 255)])
    raw, energy, peaks = _signals([frame], 1)
    assert raw.tolist() == energy.tolist() == [0, 240, 480, 0, 240, 240, 0, 480]
    # Equal 10,10 plateau takes its trailing position; the ends are circular.
    assert peaks.tolist() == [0, 0, 480, 0, 0, 240, 0, 480]
    fixture = json.loads((VECTORS / "checker-x3.json").read_text())
    grid = fixture["expected"]
    assert grid["x_cells"] == grid["y_cells"] == [[0, 3], [3, 6]]
    assert grid["peak"] == 5000 and grid["grid_score"] == 1000
    assert fixture["signals"]["1"][0] == [0, 0, 0, 4590, 0, 0]


def test_min_peak_compares_score_and_exact_branch_bypasses_it():
    value = json.loads((VECTORS / "slope-knots-2d.json").read_text())
    gray = np.asarray(value["grayscale_frames"][0], dtype=np.uint8)
    frame = np.dstack([gray, gray, gray, np.full_like(gray, 255)])
    grid = detect_grid(frame, max_cell=4)
    assert grid["detected"] and grid["peak"] == 1000
    assert grid["normalized_score"] == 8436
    assert not detect_grid(frame, max_cell=4, min_peak=8437)["detected"]
    checker = np.array([[0, 255], [255, 0]], dtype=np.uint8).repeat(3, 0).repeat(3, 1)
    frame = np.dstack([checker, checker, checker, np.full_like(checker, 255)])
    assert detect_grid(frame, max_cell=4, min_peak=100000)["detected"]
