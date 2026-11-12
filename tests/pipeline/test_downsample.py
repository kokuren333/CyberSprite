import numpy as np
import pytest

from cybersprite.pipeline._common import PipelineError
from cybersprite.pipeline.downsample import downsample, remove_background
from cybersprite.pipeline.grid import detect_grid


@pytest.mark.parametrize("method", ["center", "median", "mode", "kcentroid", "auto"])
def test_uniform_cell_all_methods(method):
    im = np.full((4, 4, 4), (17, 29, 41, 255), dtype=np.uint8)
    grid = detect_grid(im, "fixed", cell_w=4, cell_h=4)
    out, report = downsample(im, grid, method=method)
    np.testing.assert_array_equal(out[0], [[[17, 29, 41, 255]]])
    assert report["method"] == ("center" if method == "auto" else method)


def test_binary_alpha_majority_and_zero_hidden_rgb():
    im = np.full((2, 4, 4), (9, 8, 7, 127), dtype=np.uint8)
    im[0, :2, 3] = 128
    grid = detect_grid(im, "fixed", cell_w=2, cell_h=2)
    out, _ = downsample(im, grid)
    np.testing.assert_array_equal(out[0], [[[9, 8, 7, 255], [0, 0, 0, 0]]])


def test_median_mode_kcentroid_ties_and_auto_target():
    im = np.array([[[8, 8, 8, 255], [200, 200, 200, 255]],
                   [[9, 9, 9, 255], [201, 201, 201, 255]]], dtype=np.uint8)
    grid = detect_grid(im, "target", target_w=1, target_h=1)
    expected = {"median": 9, "mode": 8, "kcentroid": 200, "auto": 200, "center": 201}
    for method, value in expected.items():
        out, report = downsample(im, grid, method=method)
        assert out[0][0, 0].tolist() == [value, value, value, 255]
        if method == "auto":
            assert report["method"] == "kcentroid"
    low_purity = {**grid, "mode": "fixed", "grid_score": 500}
    assert downsample(im, low_purity)[1]["method"] == "mode"


def test_plugin_required_and_explicit_adapter():
    image = np.full((2, 2, 4), 255, dtype=np.uint8)
    grid = detect_grid(image, "target", target_w=1, target_h=1)
    with pytest.raises(PipelineError, match="E_PLUGIN"):
        downsample(image, grid, method="pixeloe")
    out, report = downsample(image, grid, pixeloe=lambda f, g: f[:1, :1].copy())
    assert report["method"] == "pixeloe" and out[0].tolist() == [[[255] * 4]]


def test_background_flood_fill_leaves_enclosed_key():
    image = np.full((5, 5, 4), (255, 255, 255, 255), dtype=np.uint8)
    image[1:4, 1:4] = (0, 0, 0, 255)
    image[2, 2] = (255, 255, 255, 255)
    for mode in ("auto", "key"):
        result, report = remove_background(image, mode, color=[255, 255, 255], tolerance=0)
        assert report["removed_pixels"] == 16
        assert result[2, 2, 3] == 255 and np.all(result[0] == 0)
    unique = np.arange(3 * 3 * 4, dtype=np.uint8).reshape(3, 3, 4)
    out, report = remove_background(unique, "auto")
    assert report["warnings"] and np.array_equal(out, unique)
    single, report = remove_background(image[:1, :1], "auto")
    assert report["removed_pixels"] == 1 and not single.any()


def test_input_not_mutated_and_threshold_validation():
    image = np.full((4, 4, 4), 255, dtype=np.uint8)
    original = image.copy()
    downsample(image, detect_grid(image, "none"), background={"mode": "auto"})
    np.testing.assert_array_equal(image, original)
    with pytest.raises(ValueError):
        downsample(image.astype(np.float64), detect_grid(image, "none"))
