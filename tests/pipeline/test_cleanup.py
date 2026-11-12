import numpy as np
import pytest

from cybersprite.pipeline.cleanup import cleanup_pixels
from cybersprite.pipeline.decisions import outline_and_dither

P = [(0, 0, 0, 0), (0, 0, 0, 255), (255, 255, 255, 255), (127, 127, 127, 255)]


def test_isolated_points_and_protect_disable():
    image = np.array([[0, 0, 0], [0, 2, 0], [0, 0, 0]], dtype=np.uint8)
    cleaned, report = cleanup_pixels(image, P)
    assert not cleaned.any()
    assert report["replaced_pixels"] == 1 and report["positions"] == [[1, 1]]
    for settings in ({"protect": [2]}, {"min_cluster": 1}):
        cleaned, report = cleanup_pixels(image, P, **settings)
        np.testing.assert_array_equal(cleaned, image)
        assert report["replaced_pixels"] == 0


def test_simultaneous_replacement_and_nontransparent_tie():
    image = np.array([[1, 2]], dtype=np.uint8)
    cleaned, report = cleanup_pixels(image, P, max_passes=1)
    assert cleaned.tolist() == [[2, 1]]
    assert report["replaced_pixels"] == 2
    # Transparent is last among equal counts, even though RGB black is nearer.
    image = np.array([[0, 1, 2]], dtype=np.uint8)
    cleaned, _ = cleanup_pixels(image, P, max_passes=1, protect=[2])
    assert cleaned.tolist() == [[0, 2, 2]]


def test_unique_neighbor_count_and_connectivity():
    # Center border pixel touches two component members but counts only once.
    image = np.array([[2, 1, 2], [0, 1, 0]], dtype=np.uint8)
    cleaned, _ = cleanup_pixels(image, P, min_cluster=3, max_passes=1, protect=[0, 2])
    assert cleaned.tolist() == [[2, 2, 2], [0, 2, 0]]
    diagonal = np.array([[2, 0], [0, 2]], dtype=np.uint8)
    assert np.array_equal(cleanup_pixels(diagonal, P, connectivity=8)[0], diagonal)
    assert not cleanup_pixels(diagonal, P, connectivity=4)[0].any()


def test_cleanup_report_limit_and_no_input_mutation():
    image = np.zeros((35, 35), dtype=np.uint8)
    image[::2, ::2] = 2
    original = image.copy()
    _, report = cleanup_pixels(image, P)
    assert report["unique_replaced_pixels"] == 324
    assert len(report["positions"]) == 256 and report["positions_truncated"]
    np.testing.assert_array_equal(image, original)


def test_outline_outside_and_choice_provenance():
    image = np.zeros((3, 3), dtype=np.uint8)
    image[1, 1] = 2
    out, palette, report = outline_and_dither(image, P, outline={"mode": "add", "color": [12, 34, 56, 255], "connectivity": 4},
                                             chosen_by={"outline": "caller"})
    assert out[0].tolist() == [[0, 4, 0], [4, 2, 4], [0, 4, 0]]
    assert palette[-1] == (12, 34, 56, 255)
    assert report["chosen_by"] == {"outline": "caller", "dither": "preset"}
    assert report["palette_added"] == [(12, 34, 56, 255)]
    kept, _, report = outline_and_dither(image, P, dither={"type": "bayer2"})
    np.testing.assert_array_equal(kept[0], image)
    assert report["dither"]["type"] == "bayer2"


def test_outline_rgb_matching_opaque_transparent_entry_adds_usable_copy():
    image = np.array([[0, 1, 0]], dtype=np.uint8)
    palette = [(255, 255, 255, 255), (0, 0, 0, 255)]
    out, palette, _ = outline_and_dither(image, palette, outline={"mode": "add", "color": [255, 255, 255]})
    assert out[0].tolist() == [[2, 1, 2]] and len(palette) == 3


def test_outline_budget_error_is_adaptable_to_palette_gate():
    palette = [(0, 0, 0, 0)] + [(i, 0, 0, 255) for i in range(255)]
    with pytest.raises(ValueError, match="E_LIMIT_EXCEEDED") as exc:
        outline_and_dither(np.array([[0, 1, 0]], dtype=np.uint8), palette,
                           outline={"mode": "add", "color": [255, 255, 255]})
    assert exc.value.details["gate"] == "palette_budget" and exc.value.details["palette_size"] == 257
