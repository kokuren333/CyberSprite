"""Snap cells to binary-alpha pixels and remove border-connected backgrounds."""

from collections import Counter, deque

import numpy as np

from ._common import PipelineError, integer, interior, lower_median, neighbors, require, rgba_frames
from .grid import regular_cells


def _representative(pixels, center, method):
    if method == "center":
        return center[:3]
    if method == "median":
        return lower_median(pixels)[:3]
    if method == "mode":
        packed = pixels.astype(np.int64) >> 3
        keys = (packed[:, 0] << 15) | (packed[:, 1] << 10) | (packed[:, 2] << 5) | packed[:, 3]
        counts = Counter(int(v) for v in keys)
        winner = min(counts, key=lambda v: (-counts[v], v))
        return lower_median(pixels[keys == winner])[:3]
    rgb = pixels[:, :3].astype(np.int64)
    order = sorted(
        range(len(rgb)), key=lambda i: (int(rgb[i].sum()), tuple(int(v) for v in rgb[i]))
    )
    reps = np.stack((rgb[order[0]], rgb[order[-1]]))
    for _ in range(4):
        distances = np.abs(rgb[:, None, :] - reps[None, :, :]).sum(axis=2, dtype=np.int64)
        assignments = np.argmin(distances, axis=1)
        center_group = int(np.argmin(np.abs(reps - center[:3].astype(np.int64)).sum(axis=1)))
        for group in range(2):
            members = rgb[assignments == group]
            if len(members):
                reps[group] = lower_median(members)
    counts = [int(np.count_nonzero(assignments == k)) for k in range(2)]
    group = center_group if counts[0] == counts[1] else int(counts[1] > counts[0])
    return reps[group]


def remove_background(image, mode="keep", *, color=None, tolerance=0):
    rgba_frames(image)
    require(mode in ("keep", "key", "auto"), "Unknown background mode.")
    integer(tolerance, "background tolerance", 0, 255)
    result, warnings = image.copy(), []
    if mode == "keep":
        return result, {"mode": mode, "removed_pixels": 0, "warnings": warnings}
    h, w = image.shape[:2]
    border = [
        (x, y) for y in range(h) for x in range(w) if x == 0 or y == 0 or x == w - 1 or y == h - 1
    ]
    if mode == "auto":
        counts = Counter(tuple(int(c) for c in image[y, x]) for x, y in border)
        color = min(counts, key=lambda c: (-counts[c], c))
        if counts[color] * 100 < len(border) * 60:
            warnings.append(
                "No background color occupies at least 60% of the border; kept all pixels."
            )
            return result, {"mode": mode, "removed_pixels": 0, "warnings": warnings}
    require(color is not None and len(color) in (3, 4), "Background key needs RGB or RGBA color.")
    color = [integer(c, "background channel", 0, 255) for c in color]
    match = np.all(np.abs(image[:, :, : len(color)].astype(np.int64) - color) <= tolerance, axis=2)
    queue, seen = deque((x, y) for x, y in border if match[y, x]), set()
    removed = 0
    while queue:
        x, y = queue.popleft()
        if (x, y) in seen:
            continue
        seen.add((x, y))
        removed += int(result[y, x, 3] != 0)
        result[y, x] = 0
        queue.extend(
            (xx, yy)
            for xx, yy in neighbors(x, y, w, h, 4)
            if match[yy, xx] and (xx, yy) not in seen
        )
    return result, {"mode": mode, "color": color, "removed_pixels": removed, "warnings": warnings}


def downsample(images, grid, *, method="auto", alpha_threshold=128, background=None, pixeloe=None):
    """Return (frames, report); a plugin is an explicit callback, never auto-discovered."""
    frames = rgba_frames(images)
    integer(alpha_threshold, "alpha_threshold", 0, 255)
    require(
        grid["detected"] and grid["columns"] > 0 and grid["rows"] > 0,
        "Downsampling requires a detected or specified grid.",
        "Inspect grid candidates, then supply fixed or target grid settings.",
    )
    requested = method
    if method == "auto":
        if grid["mode"] == "target":
            method = "pixeloe" if pixeloe is not None else "kcentroid"
        else:
            method = "center" if grid["grid_score"] >= 990 else "mode"
    require(
        method in ("center", "median", "mode", "kcentroid", "pixeloe"), "Unknown downsample method."
    )
    if method == "pixeloe" and pixeloe is None:
        raise PipelineError(
            "E_PLUGIN",
            "PixelOE downsampling was requested but no plugin was supplied.",
            "Install and configure a PixelOE adapter, or select kcentroid.",
            plugin="pixeloe",
        )
    outputs, reports = [], []
    for frame in frames:
        out = np.zeros((grid["rows"], grid["columns"], 4), dtype=np.uint8)
        uniform = regular_cells(frame.shape, grid["x_cells"], grid["y_cells"])
        if method == "center" and uniform is not None:
            ch, cw = uniform
            dx, dy = (max(1, cw // 5) if cw >= 4 else 0), (max(1, ch // 5) if ch >= 4 else 0)
            blocks = frame.reshape(grid["rows"], ch, grid["columns"], cw, 4).transpose(
                0, 2, 1, 3, 4
            )
            alpha = blocks[:, :, dy : ch - dy, dx : cw - dx, 3] >= alpha_threshold
            opaque = alpha.sum(axis=(2, 3)) * 2 >= alpha.shape[2] * alpha.shape[3]
            out = frame[ch // 2 :: ch, cw // 2 :: cw].copy()
            out[~opaque] = 0
            out[opaque, 3] = 255
            out, report = remove_background(out, **(background or {}))
            outputs.append(out)
            reports.append(report)
            continue
        if method == "pixeloe":
            out = pixeloe(frame.copy(), grid)
            rgba_frames(out)
            require(
                out.shape == (grid["rows"], grid["columns"], 4),
                "PixelOE output dimensions must match the grid.",
            )
            out = out.copy()
        for y, (top, bottom) in enumerate(grid["y_cells"]):
            for x, (left, right) in enumerate(grid["x_cells"]):
                cell = frame[top:bottom, left:right]
                pixels = interior(cell).reshape(-1, 4)
                opaque = pixels[pixels[:, 3] >= alpha_threshold]
                if 2 * len(opaque) < len(pixels) or not len(opaque):
                    out[y, x] = 0
                else:
                    if method != "pixeloe":
                        center = cell[cell.shape[0] // 2, cell.shape[1] // 2]
                        out[y, x, :3] = _representative(opaque, center, method)
                    out[y, x, 3] = 255
        out, report = remove_background(out, **(background or {}))
        outputs.append(out)
        reports.append(report)
    return outputs, {"requested_method": requested, "method": method, "background": reports}
