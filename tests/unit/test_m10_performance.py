"""Optimization equivalence, including deterministic traversal and cache invalidation."""

from collections import deque
from copy import deepcopy
from random import Random

import numpy as np
import pytest

from cybersprite.core import quality
from cybersprite.core.models import GroupLayer, LinkCel
from cybersprite.core.render import frame_signature, render
from tools.bench import fixture
from tools.m5_cases import animated_project, tile_project


def reference_clusters(image, ti):
    seen = np.zeros(image.shape, dtype=bool)
    h, w = image.shape
    result = []
    for y in range(h):
        for x in range(w):
            if seen[y, x] or image[y, x] == ti:
                continue
            value = image[y, x]
            seen[y, x] = True
            queue = deque([(x, y)])
            points = []
            while queue:
                px, py = queue.popleft()
                points.append([px, py])
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        nx, ny = px + dx, py + dy
                        if (
                            0 <= nx < w
                            and 0 <= ny < h
                            and not seen[ny, nx]
                            and image[ny, nx] == value
                        ):
                            seen[ny, nx] = True
                            queue.append((nx, ny))
            result.append(points)
    return result


def test_cluster_traversal_matches_original_integer_vectors():
    rng = Random(801)
    for _ in range(50):
        image = np.array([[rng.randrange(4) for _ in range(17)] for _ in range(13)], dtype=np.uint8)
        for ti in (0, 2, -1):
            assert quality.clusters(image, ti) == reference_clusters(image, ti)


@pytest.mark.parametrize("factory", [lambda: fixture(16, 2, 4), animated_project, tile_project])
def test_report_reuse_matches_full_recalculation(monkeypatch, factory):
    p = factory()
    expected = quality.report(p)
    monkeypatch.setattr(quality, "frame_signature", lambda *_: object())
    assert quality.report(p) == expected


def test_identical_frames_and_links_have_identical_signature():
    p = fixture(16, 2, 3)
    p.layers[1].cels[1] = LinkCel(frame=1, link=0)
    assert frame_signature(p, 0) == frame_signature(p, 1)
    np.testing.assert_array_equal(render(p, 0), render(p, 1))
    p.layers[1].cels[1].z_index = -4
    assert frame_signature(p, 0) != frame_signature(p, 1)


@pytest.mark.parametrize(
    "change",
    [
        lambda p: setattr(p.canvas, "width", 17),
        lambda p: p.palette.colors.__setitem__(1, "#ff0000ff"),
        lambda p: setattr(p.palette, "transparent_index", 1),
        lambda p: setattr(p.layers[0], "visible", False),
        lambda p: setattr(p.layers[0], "opacity", 128),
        lambda p: setattr(p.layers[0], "background", True),
        lambda p: setattr(p.layers[0].cels[0], "x", -1),
        lambda p: setattr(p.layers[0].cels[0], "opacity", 128),
        lambda p: p.layers[0].cels[0].pixels.__setitem__(0, "02" * 16),
        lambda p: setattr(p.layers[0].cels[0], "z_index", 2),
        lambda p: setattr(p.layers[0], "blend_mode", "multiply"),
    ],
)
def test_render_signature_invalidates_each_compositing_input(change):
    p = fixture(16)
    q = deepcopy(p)
    change(q)
    assert frame_signature(p, 0) != frame_signature(q, 0)


def test_group_and_tile_inputs_invalidate_signature():
    p = fixture(16)
    p.layers = [GroupLayer(id="L2", name="Group", children=p.layers)]
    before = frame_signature(p, 0)
    p.layers[0].opacity = 128
    assert frame_signature(p, 0) != before
    p = tile_project()
    before = frame_signature(p, 0)
    p.tilesets[0].tiles[1].pixels[0] = "02" * p.tilesets[0].tile_w
    assert frame_signature(p, 0) != before
