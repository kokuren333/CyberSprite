import random

import numpy as np
import pytest

from cybersprite.pipeline.quantize import BAYER, assign_palette, extract_palette, quantize

P = [(0, 0, 0, 0), (0, 0, 0, 255), (255, 255, 255, 255)]


def frame(colors):
    return np.array([[(*c, 255) if len(c) == 3 else c for c in colors]], dtype=np.uint8)


def test_exact_and_project_lock_transparency_and_sort():
    im = frame([(255, 255, 255), (0, 0, 0), (13, 24, 35, 0)])
    indices, palette, report = quantize(im, mode="exact")
    assert palette == P
    assert indices[0].tolist() == [[2, 1, 0]]
    assert report["palette_size"] == 3
    locked = [P[2], P[0], P[1], (127, 127, 127, 127)]
    indices, palette, report = quantize(
        im, mode="project", project_palette=locked, transparent_index=1
    )
    assert palette == locked and indices[0].tolist() == [[0, 2, 1]]
    assert report["palette_added"] == []
    with pytest.raises(ValueError, match="E_NEEDS_QUANTIZE"):
        quantize(im, mode="exact", max_colors=1)


def test_fixed_preserves_existing_and_adds_only_used_colors():
    im = frame([(255, 255, 255), (0, 0, 0)])
    out, palette, report = quantize(
        im, mode="fixed", source=P + [(255, 0, 0, 255)], project_palette=P[:2]
    )
    assert palette == P and report["palette_added"] == [P[2]]
    assert out[0].tolist() == [[2, 1]]
    # Duplicate/identical distances choose the lower palette index, and
    # translucent entries (even an exact RGB match) cannot be selected.
    fixed = [P[0], P[2], P[2], (127, 127, 127, 127)]
    assert assign_palette(frame([(255, 255, 255), (127, 127, 127)]), fixed)[0].tolist() == [[1, 1]]


def test_opaque_transparent_index_is_never_selected_on_palette_append():
    existing = [(255, 255, 255, 255), (0, 0, 0, 255)]
    out, palette, report = quantize(
        frame([(255, 255, 255)]), mode="exact", project_palette=existing
    )
    assert out[0].tolist() == [[2]] and palette == existing + [existing[0]]
    assert report["palette_added"] == [existing[0]]


def test_median_cut_weighted_split_and_real_representatives():
    im = frame([(0, 0, 0)] * 4 + [(80, 80, 80)] * 2 + [(160, 160, 160)] + [(255, 255, 255)])
    assert extract_palette(im, max_colors=2, refine_iterations=0) == [
        (0, 0, 0, 255),
        (160, 160, 160, 255),
    ]
    assert extract_palette(im, max_colors=2, refine_iterations=8) == [
        (0, 0, 0, 255),
        (160, 160, 160, 255),
    ]
    palette = extract_palette(im, max_colors=4, min_color_pixels=2)
    assert palette == [(0, 0, 0, 255), (80, 80, 80, 255)]
    all_colors = [tuple(c) for c in im.reshape(-1, 4).tolist()]
    assert all(color in all_colors for color in palette)


def test_all_frames_share_histogram_and_empty_opaque_palette():
    first, second = frame([(0, 0, 0)]), frame([(255, 255, 255)])
    indices, palette, _ = quantize([first, second], mode="extract")
    assert palette == P and [f.tolist() for f in indices] == [[[1]], [[2]]]
    empty = np.zeros((3, 4, 4), dtype=np.uint8)
    indices, palette, _ = quantize(empty)
    assert palette == [P[0]] and not indices[0].any()


@pytest.mark.parametrize("kind,size", [("bayer2", 2), ("bayer4", 4), ("bayer8", 8)])
def test_normative_bayer_formula_vector(kind, size):
    matrix = np.array(BAYER[kind])
    assert sorted(matrix.ravel().tolist()) == list(range(size * size))
    if size == 4:
        assert matrix.tolist() == [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
    # Grey 100: Lab=(32979,0,1), dblack=1087614442,
    # dwhite=1059893136. White is nearest; the 2x2 threshold is 1.
    im = np.full((size, size, 4), (100, 100, 100, 255), dtype=np.uint8)
    out = assign_palette(im, P, dither_type=kind)[0]
    if size == 2:
        assert out.tolist() == [[1, 2], [2, 2]]
    assert assign_palette(im, P, dither_type=kind, strength=0)[0].tolist() == [[2] * size] * size
    exact = np.full((size, size, 4), P[2], dtype=np.uint8)
    assert np.all(assign_palette(exact, P, dither_type=kind)[0] == 2)


def test_budget_cannot_wrap_and_duplicate_source_colors():
    existing = [(0, 0, 0, 0)] + [(i, 0, 0, 255) for i in range(255)]
    with pytest.raises(ValueError, match="E_LIMIT_EXCEEDED"):
        quantize(frame([(255, 255, 255)]), mode="exact", project_palette=existing)
    with pytest.raises(ValueError, match="opaque palette"):
        assign_palette(frame([(0, 0, 0)]), [P[0]])


def test_fixed_full_source_can_select_entry_255_without_overflow():
    source = [(i, i, i, 255) for i in range(256)]
    out, palette, _ = quantize(frame([(255, 255, 255)]), mode="fixed", source=source)
    assert out[0].tolist() == [[1]] and palette == [P[0], P[2]]


def test_seeded_extraction_order_independence_and_real_color_property():
    rng = random.Random(451)
    for _ in range(20):
        image = np.array(
            [
                [
                    [rng.randrange(256), rng.randrange(256), rng.randrange(256), 255]
                    for _ in range(8)
                ]
                for _ in range(8)
            ],
            dtype=np.uint8,
        )
        palette = extract_palette(image, max_colors=8)
        assert palette == extract_palette(image[::-1, ::-1], max_colors=8)
        actual = {tuple(c) for c in image.reshape(-1, 4).tolist()}
        assert len(palette) <= 8 and set(palette) <= actual
        first, locked, _ = quantize(image, max_colors=8, dither_type="bayer4")
        second, same_locked, _ = quantize(image, max_colors=8, dither_type="bayer4")
        assert first[0].tobytes() == second[0].tobytes() and locked == same_locked
