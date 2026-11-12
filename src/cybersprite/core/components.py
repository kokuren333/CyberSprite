"""Integer array connected components with bounded, legacy-order diagnostic points."""

from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Components:
    # Labels are zero-based in row-major seed order; transparent pixels have -1.
    labels: np.ndarray
    sizes: np.ndarray
    first: np.ndarray

    @property
    def nbytes(self):
        return self.labels.nbytes + self.sizes.nbytes + self.first.nbytes

    def mask(self, selected):
        # Padding gives transparent (-1) pixels an always-false entry.
        return np.append(selected, False)[self.labels]

    def points(self, selected, limit=64):
        """Only enumerate the report prefix, preserving the original BFS order."""
        height, width = self.labels.shape
        points: list[list[int]] = []
        for component in np.flatnonzero(selected):
            start = int(self.first[component])
            queue = deque([start])
            seen = {start}
            while queue and len(points) < limit:
                position = queue.popleft()
                y, x = divmod(position, width)
                points.append([x, y])
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        nx, ny = x + dx, y + dy
                        neighbor = ny * width + nx
                        if (
                            0 <= nx < width
                            and 0 <= ny < height
                            and neighbor not in seen
                            and self.labels[ny, nx] == component
                        ):
                            seen.add(neighbor)
                            queue.append(neighbor)
            if len(points) == limit:
                break
        return points


def clusters(image, ti):
    """Label equal-index 8-connected runs using vectorized union and pointer jumping.

    Horizontal runs are already connected. Only equal-color pairs in neighboring
    rows need union. Roots always decrease, so termination and seed identity do
    not depend on processing order. Work arrays contain integers only.
    """
    height, width = image.shape
    starts = np.ones(image.shape, dtype=bool)
    starts[:, 1:] = image[:, 1:] != image[:, :-1]
    offsets = np.flatnonzero(starts).astype(np.int64)
    runs = np.cumsum(starts, dtype=np.int32).reshape(image.shape)
    runs -= 1
    del starts
    count = len(offsets)
    parents = np.arange(count, dtype=np.int32)
    edges = []
    for shift in (-1, 0, 1):
        left = slice(max(0, shift), min(width, width + shift))
        right = slice(max(0, -shift), min(width, width - shift))
        lower, upper = image[1:, left], image[:-1, right]
        equal = (lower == upper) & (lower != ti)
        a, b = runs[1:, left][equal], runs[:-1, right][equal]
        # Pack pairs into int64 to deduplicate repeated edges across a long run.
        edges.append(np.unique(a.astype(np.int64) * count + b))
    pairs = np.unique(np.concatenate(edges))
    a, b = (pairs // count).astype(np.int32), (pairs % count).astype(np.int32)
    while len(a):
        ra, rb = parents[a], parents[b]
        different = ra != rb
        if not np.any(different):
            break
        ra, rb = ra[different], rb[different]
        np.minimum.at(parents, np.maximum(ra, rb), np.minimum(ra, rb))
        while True:
            ancestors = parents[parents]
            if np.array_equal(ancestors, parents):
                break
            parents = ancestors
    active = image.ravel()[offsets] != ti
    roots = np.unique(parents[active])
    ids = np.full(count, -1, dtype=np.int32)
    ids[roots] = np.arange(len(roots), dtype=np.int32)
    run_ids = ids[parents]
    sizes = np.zeros(len(roots), dtype=np.int64)
    lengths = np.diff(np.append(offsets, image.size))
    np.add.at(sizes, run_ids[active], lengths[active])
    labels = run_ids[runs]
    first = offsets[roots]
    for array in (labels, sizes, first):
        array.flags.writeable = False
    return Components(labels, sizes, first)
