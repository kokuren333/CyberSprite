"""Simultaneous connected-component replacement, shared with cleanup_pixels."""

from collections import Counter

import numpy as np

from ._common import integer, neighbors, require
from .oklab import dist2, rgb_to_oklab_fixed


def indexed_image(image, palette, transparent_index):
    require(
        isinstance(image, np.ndarray)
        and image.ndim == 2
        and image.dtype == np.uint8
        and min(image.shape) > 0,
        "Expected a nonempty H x W uint8 index image.",
    )
    require(1 <= len(palette) <= 256, "Palette must have 1..256 entries.")
    integer(transparent_index, "transparent_index", 0, len(palette) - 1)
    require(int(image.max()) < len(palette), "Index image contains an out-of-palette index.")


def components(image, *, transparent_index=0, connectivity=8):
    """Yield (index, [(x,y),...]) in stable row-major discovery order."""
    integer(connectivity, "connectivity", 4, 8)
    require(connectivity in (4, 8), "Connectivity must be 4 or 8.")
    h, w = image.shape
    seen = np.zeros((h, w), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            color = int(image[y, x])
            if seen[y, x] or color == transparent_index:
                continue
            stack, cluster = [(x, y)], []
            seen[y, x] = 1
            while stack:
                xx, yy = stack.pop()
                cluster.append((xx, yy))
                for nx, ny in neighbors(xx, yy, w, h, connectivity):
                    if not seen[ny, nx] and int(image[ny, nx]) == color:
                        seen[ny, nx] = 1
                        stack.append((nx, ny))
            yield color, cluster


def cleanup_pixels(
    image, palette, *, transparent_index=0, min_cluster=2, connectivity=8, max_passes=2, protect=()
):
    indexed_image(image, palette, transparent_index)
    integer(min_cluster, "min_cluster", 1)
    integer(max_passes, "max_passes", 0)
    integer(connectivity, "connectivity", 4, 8)
    require(connectivity in (4, 8), "Connectivity must be 4 or 8.")
    for color in protect:
        integer(color, "protected index", 0, len(palette) - 1)
    out, changed_positions, replacements, passes = image.copy(), set(), 0, 0
    labs = [rgb_to_oklab_fixed(c[:3]) for c in palette]
    if min_cluster > 1:
        for _ in range(max_passes):
            original, changed = out.copy(), False
            h, w = original.shape
            passes += 1
            for color, cluster in components(
                original, transparent_index=transparent_index, connectivity=connectivity
            ):
                if len(cluster) >= min_cluster or color in protect:
                    continue
                members = set(cluster)
                adjacent = set()
                for x, y in cluster:
                    adjacent.update(
                        (xx, yy) for xx, yy in neighbors(x, y, w, h) if (xx, yy) not in members
                    )
                counts = Counter(
                    int(original[y, x]) for x, y in sorted(adjacent, key=lambda p: (p[1], p[0]))
                )
                if not counts:
                    continue
                replacement = min(
                    counts,
                    key=lambda i: (
                        -counts[i],
                        i == transparent_index,
                        dist2(labs[color], labs[i]),
                        i,
                    ),
                )
                for x, y in cluster:
                    if replacement != color:
                        out[y, x] = replacement
                        replacements += 1
                        changed_positions.add((x, y))
                        changed = True
            if not changed:
                break
    return out, {
        "replaced_pixels": replacements,
        "unique_replaced_pixels": len(changed_positions),
        "positions": [list(p) for p in sorted(changed_positions, key=lambda p: (p[1], p[0]))[:256]],
        "positions_truncated": len(changed_positions) > 256,
        "passes": passes,
    }
