import numpy as np
import pytest

from cybersprite.pipeline.grid import axis_candidates, cell_purity, detect_grid


def rgba(values):
    values = np.asarray(values, dtype=np.uint8)
    return np.concatenate(
        (
            np.repeat(values[:, :, None], 3, axis=2),
            np.full((*values.shape, 1), 255, dtype=np.uint8),
        ),
        axis=2,
    )


def test_candidate_scores_and_harmonics():
    candidates = axis_candidates([0, 0, 30, 0, 30, 0, 30, 0], 2, 4)
    period2 = next(
        c for c in candidates if c["family"] == "B" and c["cell"] == 2 and c["offset"] == 0
    )
    assert period2["boundaries"] == [2, 4, 6]
    assert period2["peak"] == 2333
    image = rgba([[0, 255] * 4, [255, 0] * 4] * 4).repeat(4, 0).repeat(4, 1)
    grid = detect_grid(image, max_cell=16)
    assert (grid["cell_w"], grid["cell_h"], grid["offset_x"], grid["offset_y"]) == (4, 4, 0, 0)
    assert grid["x"]["family"] == "B" and grid["grid_score"] == 1000


def test_no_grid_and_multi_frame_signal_sum():
    flat = rgba([[4] * 8] * 8)
    assert not detect_grid(flat)["detected"]
    assert len(detect_grid(flat)["candidates"]["x"]) == 5
    horizontal = rgba([[0, 0, 255, 255] * 2] * 8)
    vertical = horizontal.transpose(1, 0, 2).copy()
    assert not detect_grid(horizontal)["detected"]
    assert detect_grid([horizontal, vertical])["detected"]


def test_fixed_target_none_and_partial_cells():
    image = rgba([[0] * 11] * 9)
    fixed = detect_grid(image, "fixed", cell_w=4, cell_h=3, offset_x=1, offset_y=2)
    assert fixed["x_cells"] == [(1, 5), (5, 9), (9, 11)]
    assert fixed["y_cells"] == [(0, 2), (2, 5), (5, 8)]
    target = detect_grid(image, "target", target_w=4, target_h=3)
    assert target["x_cells"] == [(0, 3), (3, 6), (6, 8), (8, 11)]
    assert len(detect_grid(image, "none")["x_cells"]) == 11
    tiny = detect_grid(image[:1, :1], "fixed", cell_w=2, cell_h=2)
    assert tiny["detected"] and tiny["x_cells"] == tiny["y_cells"] == [(0, 1)]
    with pytest.raises(ValueError):
        detect_grid(image, "target", target_w=12, target_h=3)


def test_purity_uses_trimmed_lower_median_and_all_channels():
    image = np.zeros((5, 5, 4), dtype=np.uint8)
    image[1:4, 1:4] = (50, 50, 50, 255)
    image[2, 2, 3] = 200
    assert cell_purity(image, [(0, 5)], [(0, 5)])["grid_score"] == 888
    image = np.array([[[0, 0, 0, 255], [100, 100, 100, 255]]], dtype=np.uint8)
    assert cell_purity(image, [(0, 2)], [(0, 1)], 0)["grid_score"] == 500


def test_noninteger_system_a_and_force_square():
    # Rounded equal division produces widths 3,2,3,2.
    row = np.repeat([0, 255, 0, 255], [3, 2, 3, 2])
    im = rgba(np.tile(row, (10, 1)))
    im[5:] = 255 - im[5:]
    im[:, :, 3] = 255
    grid = detect_grid(im, force_square=False, min_cell=2, max_cell=5)
    assert grid["x"]["family"] == "A"
    assert grid["x"]["boundaries"] == [3, 5, 8]
    image = rgba([[0, 255] * 4, [255, 0] * 4] * 4).repeat(4, 0).repeat(3, 1)
    square = detect_grid(image, max_cell=8)
    assert square["cell_w"] == square["cell_h"]
