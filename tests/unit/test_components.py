"""R1-B2 equivalence against the pre-optimization Python BFS oracle."""

from collections import deque
from random import Random

import numpy as np
import pytest

from cybersprite.core.components import clusters


def reference_clusters(image, ti):
    # The original quality.clusters implementation, retained as an independent oracle.
    values = image.tolist()
    h, w = image.shape
    seen = [bytearray(w) for _ in range(h)]
    result = []
    for y in range(h):
        for x in range(w):
            if seen[y][x] or values[y][x] == ti:
                continue
            value = values[y][x]
            seen[y][x] = 1
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
                            and not seen[ny][nx]
                            and values[ny][nx] == value
                        ):
                            seen[ny][nx] = 1
                            queue.append((nx, ny))
            result.append(points)
    return result


def assert_equivalent(image, ti):
    expected = reference_clusters(image, ti)
    actual = clusters(image, ti)
    assert actual.sizes.tolist() == [len(part) for part in expected]
    assert actual.first.tolist() == [part[0][1] * image.shape[1] + part[0][0] for part in expected]
    for minimum in (0, 1, 2, 4, 17, 65, image.size + 1):
        selected = actual.sizes < minimum
        points = [point for part in expected if len(part) < minimum for point in part]
        assert actual.points(selected) == points[:64]
        mask = np.zeros(image.shape, dtype=bool)
        for x, y in points:
            mask[y, x] = True
        np.testing.assert_array_equal(actual.mask(selected), mask)
    for index, part in enumerate(expected):
        assert actual.points(np.arange(len(expected)) == index) == part[:64]
        for x, y in part:
            assert actual.labels[y, x] == index


@pytest.mark.parametrize("seed", range(40))
def test_seeded_components_match_every_legacy_observable(seed):
    rng = Random(seed)
    h, w = rng.randrange(1, 24), rng.randrange(1, 28)
    image = np.array([[rng.randrange(5) for _ in range(w)] for _ in range(h)], dtype=np.uint8)
    for ti in (0, 2, -1):
        assert_equivalent(image, ti)


def test_dense_diagonal_transparent_and_late_bridging_vectors():
    vectors = [
        np.ones((32, 35), dtype=np.uint8),
        np.zeros((4, 7), dtype=np.uint8),
        np.eye(19, dtype=np.uint8),
        np.array([[1, 0, 1, 0, 1], [1, 0, 1, 0, 1], [1, 1, 1, 1, 1]], dtype=np.uint8),
    ]
    for image in vectors:
        for ti in (0, 1, -1):
            assert_equivalent(image, ti)


def test_dense_components_store_arrays_without_all_coordinate_objects():
    actual = clusters(np.ones((1024, 1024), dtype=np.uint8), 0)
    assert actual.sizes.tolist() == [1024 * 1024]
    assert actual.nbytes == 1024 * 1024 * 4 + 16
    assert len(actual.points(actual.sizes > 0)) == 64
    assert not actual.labels.flags.writeable
