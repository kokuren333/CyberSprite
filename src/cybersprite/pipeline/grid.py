"""Integer grid candidates, harmonic selection and cell-purity scoring (§11.3)."""

from functools import cmp_to_key

import numpy as np

from ._common import integer, interior, lower_median, require, rgba_frames


def _size_compare(a, b):
    delta = a["numerator"] * b["denominator"] - b["numerator"] * a["denominator"]
    if delta:
        return -1 if delta < 0 else 1
    ka, kb = (a["family"] != "B", a["offset"]), (b["family"] != "B", b["offset"])
    return (ka > kb) - (ka < kb)


def _rank_compare(a, b):
    return ((b["peak"] > a["peak"]) - (b["peak"] < a["peak"])) or _size_compare(a, b)


def axis_candidates(signal, min_cell=2, max_cell=64):
    """Signal includes e[0]=0. Rational A cell sizes stay numerator/denominator."""
    n, total = len(signal), sum(int(v) for v in signal)
    result = []

    def append(family, numerator, denominator, offset, boundaries):
        peak = (sum(int(signal[b]) for b in boundaries) * (n - 1) * 1000 //
                (total * len(boundaries))) if total and boundaries else 0
        result.append({"family": family, "numerator": numerator, "denominator": denominator,
                       "cell": (numerator + denominator // 2) // denominator,
                       "offset": offset, "boundaries": boundaries, "peak": peak})

    for count in range(max(1, (n + max_cell - 1) // max_cell), n // min_cell + 1):
        append("A", n, count, 0, [(k * n + count // 2) // count for k in range(1, count)])
    for size in range(min_cell, max_cell + 1):
        for offset in range(size):
            append("B", size, 1, offset, list(range(offset or size, n, size)))
    return result


def _select(candidates, min_peak, harmonic_tolerance):
    best = max((c["peak"] for c in candidates), default=0)
    if best < min_peak:
        return None
    return min((c for c in candidates if c["peak"] * 1000 >= best * harmonic_tolerance),
               key=cmp_to_key(_size_compare))


def _intervals(candidate, length):
    boundaries = [0] + candidate["boundaries"] + [length]
    pairs = list(zip(boundaries, boundaries[1:]))
    if candidate["family"] == "B":
        pairs = [(a, b) for a, b in pairs if 2 * (b - a) >= candidate["cell"]]
    return pairs


def cell_purity(images, x_cells, y_cells, tolerance=16):
    frames = rgba_frames(images)
    integer(tolerance, "purity_tolerance", 0, 255)
    matched, total = 0, 0
    for frame in frames:
        for top, bottom in y_cells:
            for left, right in x_cells:
                pixels = interior(frame[top:bottom, left:right]).reshape(-1, 4).astype(np.int64)
                med = lower_median(pixels)
                matched += int(np.count_nonzero(np.all(np.abs(pixels - med) <= tolerance, axis=1)))
                total += len(pixels)
    return {"grid_score": matched * 1000 // total if total else 0,
            "matched_pixels": matched, "interior_pixels": total}


def detect_grid(images, mode="auto", *, min_cell=2, max_cell=64, force_square=True,
                harmonic_tolerance=850, min_peak=1500, purity_tolerance=16,
                cell_w=None, cell_h=None, offset_x=0, offset_y=0, target_w=None, target_h=None):
    frames = rgba_frames(images)
    h, w = frames[0].shape[:2]
    require(mode in ("auto", "fixed", "target", "none"), "Unknown grid mode.")
    integer(min_cell, "min_cell", 1)
    integer(max_cell, "max_cell", min_cell)
    integer(harmonic_tolerance, "harmonic_tolerance", 0, 1000)
    integer(min_peak, "min_peak", 1)
    tops = {"x": [], "y": []}
    if mode == "auto":
        ex, ey = np.zeros(w, dtype=np.int64), np.zeros(h, dtype=np.int64)
        for image in frames:
            wide = image.astype(np.int64)
            ex[1:] += np.abs(wide[:, 1:] - wide[:, :-1]).sum(axis=(0, 2), dtype=np.int64)
            ey[1:] += np.abs(wide[1:] - wide[:-1]).sum(axis=(1, 2), dtype=np.int64)
        cx, cy = axis_candidates(ex, min_cell, max_cell), axis_candidates(ey, min_cell, max_cell)
        tops = {"x": sorted(cx, key=cmp_to_key(_rank_compare))[:5],
                "y": sorted(cy, key=cmp_to_key(_rank_compare))[:5]}
        ax, ay = _select(cx, min_peak, harmonic_tolerance), _select(cy, min_peak, harmonic_tolerance)
        if ax is not None and ay is not None and force_square and _different_size(ax, ay):
            winner = ax if ax["peak"] >= ay["peak"] else ay
            choices = cy if winner is ax else cx
            choices = [c for c in choices if not _different_size(c, winner)]
            # For a rational A period unavailable on the other axis, use its
            # rounded nominal integer period and reselect only the B phase.
            if not choices:
                choices = [c for c in (cy if winner is ax else cx)
                           if c["family"] == "B" and c["cell"] == winner["cell"]]
            selected = sorted(choices, key=cmp_to_key(_rank_compare))[0] if choices else None
            if winner is ax:
                ay = selected
            else:
                ax = selected
    elif mode == "target":
        integer(target_w, "target_w", 1, w)
        integer(target_h, "target_h", 1, h)
        ax, ay = (_target_axis(n, count) for n, count in ((w, target_w), (h, target_h)))
    else:
        if mode == "none":
            cell_w = cell_h = 1
            offset_x = offset_y = 0
        integer(cell_w, "cell_w", 1)
        integer(cell_h, "cell_h", 1)
        integer(offset_x, "offset_x", 0, cell_w - 1)
        integer(offset_y, "offset_y", 0, cell_h - 1)
        ax, ay = (_fixed_axis(n, size, offset) for n, size, offset in
                  ((w, cell_w, offset_x), (h, cell_h, offset_y)))
    detected = ax is not None and ay is not None
    xs, ys = (_intervals(ax, w), _intervals(ay, h)) if detected else ([], [])
    detected = detected and bool(xs) and bool(ys)
    purity = cell_purity(frames, xs, ys, purity_tolerance)
    return {"mode": mode, "detected": detected, "x": ax, "y": ay,
            "cell_w": ax["cell"] if ax else None, "cell_h": ay["cell"] if ay else None,
            "offset_x": ax["offset"] if ax else None, "offset_y": ay["offset"] if ay else None,
            "x_cells": xs, "y_cells": ys, "columns": len(xs), "rows": len(ys),
            "peak": min(ax["peak"], ay["peak"]) if detected else 0,
            "candidates": tops, **purity}


def _different_size(a, b):
    return a["numerator"] * b["denominator"] != b["numerator"] * a["denominator"]


def _target_axis(n, count):
    return {"family": "A", "numerator": n, "denominator": count,
            "cell": (n + count // 2) // count, "offset": 0, "peak": 0,
            "boundaries": [(k * n + count // 2) // count for k in range(1, count)]}


def _fixed_axis(n, size, offset):
    return {"family": "B", "numerator": size, "denominator": 1,
            "cell": size, "offset": offset, "peak": 0,
            "boundaries": list(range(offset or size, n, size))}
