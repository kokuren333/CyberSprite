"""One-time palette extraction and locking using integer Oklab (§11.5)."""

from collections import Counter

import numpy as np

from ._common import PipelineError, color_channels, integer, require, rgba_frames
from .oklab import dist2, load_table, rgb_to_oklab_fixed, rgb_to_oklab_fixed_numpy

BAYER = {
    name: tuple(tuple(row) for row in matrix)
    for name, matrix in sorted(load_table("bayer_v1.json").items())
}


def _histogram(images):
    counts = Counter()
    for im in rgba_frames(images):
        rgb = im[im[:, :, 3] >= 128, :3].astype(np.int64)
        values, frequencies = np.unique(
            (rgb[:, 0] << 16) | (rgb[:, 1] << 8) | rgb[:, 2], return_counts=True
        )
        for value, frequency in zip(values, frequencies, strict=True):
            counts[(int(value) >> 16, (int(value) >> 8) & 255, int(value) & 255)] += int(frequency)
    colors = sorted(counts)
    return colors, [counts[c] for c in colors]


def _centroid(group, labs, weights):
    count = sum(weights[i] for i in group)
    return tuple(
        (sum(labs[i][axis] * weights[i] for i in group) + count // 2) // count for axis in range(3)
    )


def extract_palette(
    images,
    *,
    max_colors=32,
    refine_iterations=8,
    min_color_pixels=0,
    merge_distance=1800,
    salient_distance=7000,
    protect=None,
):
    integer(max_colors, "max_colors", 1, 255)
    integer(refine_iterations, "refine_iterations", 0)
    integer(min_color_pixels, "min_color_pixels", 0)
    colors, weights = _histogram(images)
    integer(merge_distance, "merge_distance", 0, 65535)
    integer(salient_distance, "salient_distance", 0, 65535)
    # Explicit colors reserve their nearest real input color; no invented RGB.
    original_labs = [rgb_to_oklab_fixed(c) for c in colors]
    reserved = set()
    for color in protect or []:
        channels = color_channels(color)
        require(
            len(channels) == 3 or channels[3] == 255, "Protected palette colors must be opaque."
        )
        require(bool(colors), "Cannot protect colors in a fully transparent input.")
        lab = rgb_to_oklab_fixed(channels[:3])
        reserved.add(
            colors[min(range(len(colors)), key=lambda i: (dist2(lab, original_labs[i]), colors[i]))]
        )
    if merge_distance and colors:
        representatives: list[tuple[int, ...]] = []
        merged_weights: list[int] = []
        representative_labs: list[tuple[int, ...]] = []
        for i in sorted(
            range(len(colors)), key=lambda i: (colors[i] not in reserved, -weights[i], colors[i])
        ):
            distances = [dist2(original_labs[i], lab) for lab in representative_labs]
            near = [j for j, d in enumerate(distances) if d <= merge_distance * merge_distance]
            if near and colors[i] not in reserved:
                j = min(near, key=lambda j: (distances[j], representatives[j]))
                merged_weights[j] += weights[i]
            else:
                representatives.append(colors[i])
                representative_labs.append(original_labs[i])
                merged_weights.append(weights[i])
        order = sorted(range(len(representatives)), key=lambda i: representatives[i])
        colors = [representatives[i] for i in order]
        weights = [merged_weights[i] for i in order]
    labs = [rgb_to_oklab_fixed(c) for c in colors]
    if salient_distance:
        total = sum(weights)
        for i, color in enumerate(colors):
            if (
                2 <= weights[i] <= 4
                and weights[i] * 64 <= total
                and all(
                    dist2(labs[i], other) >= salient_distance * salient_distance
                    for j, other in enumerate(labs)
                    if j != i
                )
            ):
                reserved.add(color)
    require(
        len(reserved) <= max_colors,
        "Protected colors exceed max_colors.",
        "Increase max_colors or reduce palette.protect / disable salient_distance.",
    )
    reserved_colors = sorted(reserved)
    # Reserved slots never participate in median cut or k-means updates.
    remaining = [i for i, color in enumerate(colors) if color not in reserved]
    colors, weights = [colors[i] for i in remaining], [weights[i] for i in remaining]
    labs = [rgb_to_oklab_fixed(c) for c in colors]
    budget = max_colors - len(reserved_colors)
    if budget == 0:
        colors, weights, labs = [], [], []
    if len(colors) <= budget:
        representatives = colors
    else:
        # Each entry carries creation order, independent of current list position.
        boxes, serial = [(0, list(range(len(colors))))], 1
        while len(boxes) < budget:
            eligible = [b for b in boxes if len(b[1]) > 1]
            chosen = min(eligible, key=lambda b: (-sum(weights[i] for i in b[1]), b[0]))
            group = chosen[1]
            ranges = [
                max(labs[i][k] for i in group) - min(labs[i][k] for i in group) for k in range(3)
            ]
            axis = max(range(3), key=lambda k: ranges[k])
            group = sorted(group, key=lambda i: (labs[i][axis], colors[i]))
            total, cumulative, split = sum(weights[i] for i in group), 0, 1
            for j, i in enumerate(group):
                cumulative += weights[i]
                if cumulative * 2 >= total:
                    split = min(j + 1, len(group) - 1)
                    break
            boxes.remove(chosen)
            boxes.extend(((serial, group[:split]), (serial + 1, group[split:])))
            serial += 2
        groups = [group for _, group in boxes]
        centroids = [_centroid(group, labs, weights) for group in groups]
        previous = None
        for _ in range(refine_iterations):
            assignments = [
                min(range(len(centroids)), key=lambda k: dist2(lab, centroids[k])) for lab in labs
            ]
            if assignments == previous:
                break
            previous = assignments
            groups = [
                [i for i, assigned in enumerate(assignments) if assigned == k]
                for k in range(len(centroids))
            ]
            groups = [g for g in groups if g]
            centroids = [_centroid(group, labs, weights) for group in groups]
        representatives = [
            colors[min(g, key=lambda i: (dist2(labs[i], centroid), -weights[i], colors[i]))]
            for g, centroid in zip(groups, centroids, strict=True)
        ]
    representatives = sorted(
        set(representatives + reserved_colors), key=lambda c: (*rgb_to_oklab_fixed(c), *c)
    )
    # Recompute usage after each deterministic merge; at least one colour survives.
    while min_color_pixels and len(representatives) > 1:
        usage = [0] * len(representatives)
        rlabs = [rgb_to_oklab_fixed(c) for c in representatives]
        for lab, weight in zip(labs, weights, strict=True):
            usage[min(range(len(rlabs)), key=lambda k: dist2(lab, rlabs[k]))] += weight
        rare = [
            k
            for k, count in enumerate(usage)
            if count < min_color_pixels and representatives[k] not in reserved
        ]
        if not rare:
            break
        # Removing the rarest colour merges its pixels into the nearest survivor
        # on the next assignment, without creating an approximate colour.
        del representatives[min(rare, key=lambda k: (usage[k], k))]
    return [(*c, 255) for c in representatives]


def _palette(source):
    require(
        source is not None,
        "This palette mode requires a resolved RGBA palette.",
        "Resolve preset or palette-file names before calling the pure quantizer.",
    )
    result = []
    for color in source:
        values = color_channels(color)
        result.append(values if len(values) == 4 else (*values, 255))
    require(1 <= len(result) <= 256, "Palette must contain 1..256 entries.")
    return result


def assign_palette(images, palette, *, transparent_index=0, dither_type="none", strength=255):
    frames, palette = rgba_frames(images), _palette(palette)
    integer(transparent_index, "transparent_index", 0, len(palette) - 1)
    return _assign_frames(frames, palette, transparent_index, dither_type, strength)


def _assign_frames(frames, palette, transparent_index, dither_type, strength, index_dtype=np.uint8):
    # A temporary extraction palette may contain 256 opaque source colors plus
    # transparency. int32 keeps all source indices intact until used-color
    # remapping and the final 256-entry budget check.
    integer(strength, "dither strength", 0, 255)
    require(dither_type == "none" or dither_type in BAYER, "Unknown Bayer dither type.")
    candidates = [
        i for i, color in enumerate(palette) if i != transparent_index and color[3] == 255
    ]
    require(
        bool(candidates) or not any(np.any(f[:, :, 3] >= 128) for f in frames),
        "No opaque palette color is available.",
        "Add an alpha-255 palette entry before quantizing.",
    )
    labs = [rgb_to_oklab_fixed(palette[i][:3]) for i in candidates]
    matrix = BAYER.get(dither_type)
    result = []
    for frame in frames:
        out = np.full(frame.shape[:2], transparent_index, dtype=index_dtype)
        mask = frame[:, :, 3] >= 128
        colors, inverse = np.unique(frame[mask, :3], axis=0, return_inverse=True)
        if len(colors):
            source_labs = rgb_to_oklab_fixed_numpy(colors)
            nearest = np.empty((len(colors), 2), dtype=np.int64)
            distances = np.empty((len(colors), 2), dtype=np.int64)
            for start in range(0, len(colors), 4096):
                delta = source_labs[start : start + 4096, None, :] - np.asarray(labs)[None, :, :]
                d = (delta * delta).sum(axis=2, dtype=np.int64)
                order = np.argsort(d, axis=1, kind="stable")[:, : min(2, len(candidates))]
                if len(candidates) == 1:
                    order = np.repeat(order, 2, axis=1)
                nearest[start : start + len(d)] = order
                distances[start : start + len(d)] = np.take_along_axis(d, order, axis=1)
            chosen = nearest[inverse, 0].copy()
            if matrix and len(candidates) > 1:
                d1, d2 = distances[inverse, 0], distances[inverse, 1]
                n = len(matrix)
                y, x = np.nonzero(mask)
                threshold = np.asarray(matrix)[y % n, x % n]
                numerator = d1 * n * n * strength
                denominator = (d1 + d2) * 255
                take_second = numerator // np.maximum(denominator, 1) > threshold
                chosen[take_second] = nearest[inverse[take_second], 1]
            out[mask] = np.asarray(candidates)[chosen]
        result.append(out)
    return result


def quantize(
    images,
    *,
    mode="extract",
    source=None,
    max_colors=32,
    refine_iterations=8,
    min_color_pixels=0,
    merge_distance=1800,
    salient_distance=7000,
    protect=None,
    project_palette=None,
    transparent_index=0,
    dither_type="none",
    strength=255,
    platform_color=None,
):
    """Return (index frames, locked palette, report), without touching a project.

    Budget/frozen-policy evaluation is separate; a palette beyond uint8 capacity
    is reported as an error with its required size before any cast can wrap.
    """
    frames = rgba_frames(images)
    require(mode in ("exact", "extract", "fixed", "project"), "Unknown palette mode.")
    integer(max_colors, "max_colors", 1, 255)
    existing = _palette(project_palette) if project_palette is not None else None
    if existing is not None:
        integer(transparent_index, "transparent_index", 0, len(existing) - 1)
    else:
        require(transparent_index == 0, "New palettes reserve transparent index 0.")
    if mode == "project":
        require(existing is not None, "Project palette mode requires project_palette.")
        indices = assign_palette(
            frames,
            existing,
            transparent_index=transparent_index,
            dither_type=dither_type,
            strength=strength,
        )
        return indices, existing, {"mode": mode, "palette_added": [], "palette_size": len(existing)}
    if mode == "fixed":
        extracted = [c for c in _palette(source) if c[3] == 255]
    elif mode == "exact":
        colors, _ = _histogram(frames)
        if len(colors) > max_colors:
            raise PipelineError(
                "E_NEEDS_QUANTIZE",
                f"Exact input has {len(colors)} opaque colors; limit is {max_colors}.",
                "Increase max_colors or select extract/fixed palette mode.",
                color_count=len(colors),
            )
        extracted = [(*c, 255) for c in colors]
    else:
        extracted = extract_palette(
            frames,
            max_colors=max_colors,
            refine_iterations=refine_iterations,
            min_color_pixels=min_color_pixels,
            merge_distance=merge_distance,
            salient_distance=salient_distance,
            protect=protect,
        )
    if platform_color is not None:
        from cybersprite.core.platform import nearest_rgb

        master = tuple(tuple(c) for c in platform_color.master_colors)
        extracted = [
            (*nearest_rgb(tuple(c[:3]), platform_color.model_dump_json(), master), c[3])
            for c in extracted
        ]
    # Quantize against source order first: fixed-source ties use source numbers.
    temporary = [(0, 0, 0, 0)] + extracted
    temp_indices = _assign_frames(frames, temporary, 0, dither_type, strength, np.int32)
    used = sorted({int(i) for frame in temp_indices for i in np.unique(frame) if i != 0})
    used_colors = sorted(
        {temporary[i] for i in used}, key=lambda c: (*rgb_to_oklab_fixed(c[:3]), *c[:3])
    )
    locked = list(existing) if existing is not None else [(0, 0, 0, 0)]
    added = []
    for color in used_colors:
        if not any(c == color and i != transparent_index for i, c in enumerate(locked)):
            locked.append(color)
            added.append(color)
    if len(locked) > 256:
        raise PipelineError(
            "E_LIMIT_EXCEEDED",
            "The locked palette exceeds uint8 capacity.",
            "Reduce source colors or use project palette mode; palette_budget must fail.",
            gate="palette_budget",
            palette_size=len(locked),
            palette_added=added,
        )
    mapping = [transparent_index] + [
        next(
            (i for i, c in enumerate(locked) if c == color and i != transparent_index),
            transparent_index,
        )
        for color in extracted
    ]
    lookup = np.asarray(mapping, dtype=np.uint8)
    return (
        [lookup[im] for im in temp_indices],
        locked,
        {
            "mode": mode,
            "palette_added": added,
            "palette_size": len(locked),
            "dither": {"type": dither_type, "strength": strength},
        },
    )
