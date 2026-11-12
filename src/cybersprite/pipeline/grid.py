"""Integer grid candidates, harmonic selection and cell-purity scoring (§11.3)."""

from functools import cmp_to_key
from typing import Any

import numpy as np

from ._common import integer, interior, lower_median, require, rgba_frames


def _size_compare(a, b):
    delta = a["numerator"] * b["denominator"] - b["numerator"] * a["denominator"]
    if delta:
        return -1 if delta < 0 else 1
    ka, kb = (a["family"] != "B", a["offset"]), (b["family"] != "B", b["offset"])
    return (ka > kb) - (ka < kb)


def axis_candidates(signal, min_cell=2, max_cell=64):
    """Signal includes e[0]=0. Rational A cell sizes stay numerator/denominator."""
    n, total = len(signal), sum(int(v) for v in signal)
    result = []

    def append(family, numerator, denominator, offset, boundaries):
        peak = (
            (sum(int(signal[b]) for b in boundaries) * (n - 1) * 1000 // (total * len(boundaries)))
            if total and boundaries
            else 0
        )
        result.append(
            {
                "family": family,
                "numerator": numerator,
                "denominator": denominator,
                "cell": (numerator + denominator // 2) // denominator,
                "offset": offset,
                "boundaries": boundaries,
                "peak": peak,
            }
        )

    for count in range(max(1, (n + max_cell - 1) // max_cell), n // min_cell + 1):
        append("A", n, count, 0, [(k * n + count // 2) // count for k in range(1, count)])
    for size in range(min_cell, max_cell + 1):
        for offset in range(size):
            append("B", size, 1, offset, list(range(offset or size, n, size)))
    return result


def _normalized_candidates(candidates, energy, peaks):
    """Integer phase correlation, with a separate local-edge alignment measure."""
    n = len(energy)
    positions = np.arange(n, dtype=np.int64)
    total, peak_total = int(energy.sum()), int(peaks.sum())
    for c in candidates:
        period, count = c["numerator"], c["denominator"]
        phase = ((positions - c["offset"]) * count) % period
        distance = np.minimum(phase, period - phase)
        triangle = np.maximum(period - 6 * distance, 0)
        alignment = int((peaks * triangle).sum()) * 1000 // max(1, peak_total * period)
        alignment = alignment * (period - count) // period
        # 1 - 6*u**2 + 4*u**3, u=2*distance/period: symmetric, smooth,
        # cosine-like signed contrast, evaluated entirely with integers.
        weights = (
            1000
            - 24000 * distance * distance // (period * period)
            + 32000 * distance * distance * distance // (period * period * period)
        )
        coherence = max(0, int((energy * weights).sum())) // max(1, total)
        c["alignment"] = alignment
        c["coherence"] = coherence
        c["score"] = (coherence + 20) * alignment // 10


def _knot_candidates(candidates, frames, axis):
    """Bilinear/cubic interpolation changes slope at source-pixel centers."""
    n = frames[0].shape[axis]
    if n < 3:
        return
    knots = np.zeros(n, dtype=np.int64)
    for image in frames:
        delta = np.abs(np.diff(image.astype(np.int64), n=2, axis=axis)).sum(axis=2)
        if axis == 0:
            delta = delta.T
        knots[1:-1] += np.where(delta * 4 >= int(delta.max(initial=0)), delta, 0).sum(
            axis=0, dtype=np.int64
        )
    total = max(1, int(knots.sum()))
    positions = np.arange(n, dtype=np.int64)
    for c in candidates:
        if c["family"] != "A":
            continue
        count = c["denominator"]
        phase = (positions * count + n // 2) % n
        distance = np.minimum(phase, n - phase)
        weights = (
            1000
            - 24000 * distance * distance // (n * n)
            + 32000 * distance * distance * distance // (n * n * n)
        )
        coherence = max(0, int((knots * weights).sum())) // total
        alignment = int((knots * np.maximum(n - 6 * distance, 0)).sum()) * 1000 // (total * n)
        score = (coherence + 20) * alignment // 40
        c["knot_score"] = score
        if score > c["score"]:
            c["score"], c["alignment"] = score, alignment


def _signals(frames, axis):
    n = frames[0].shape[axis]
    raw = np.zeros(n, dtype=np.int64)
    energy, peaks = raw.copy(), raw.copy()
    for image in frames:
        gradient = np.abs(np.diff(image.astype(np.int64), axis=axis)).sum(axis=2)
        if axis == 0:
            gradient = gradient.T
        raw[1:] += gradient.sum(axis=0, dtype=np.int64)
        significant = gradient * 4 >= int(gradient.max(initial=0))
        local = (gradient >= np.roll(gradient, 1, axis=1)) & (
            gradient > np.roll(gradient, -1, axis=1)
        )
        energy[1:] += np.where(significant, gradient, 0).sum(axis=0, dtype=np.int64)
        peaks[1:] += np.where(significant & local, gradient, 0).sum(axis=0, dtype=np.int64)
    return raw, energy, peaks


def _normalized_select(
    cx: list[dict[str, Any]], cy: list[dict[str, Any]], w, h, force_square, min_peak
):
    if not force_square:
        winners = [max(cs, key=lambda c: c["score"]) if cs else None for cs in (cx, cy)]
        return tuple(c if c and c["score"] >= min_peak else None for c in winners)
    # Equal-division candidates cover all neighboring integer cell counts.
    # A one-pixel span rounding difference is allowed between rectangular axes.
    ys = {c["denominator"]: c for c in cy if c["family"] == "A"}
    pairs = []
    for x in cx:
        if x["family"] != "A":
            continue
        nx = x["denominator"]
        ny = (nx * h + w // 2) // w
        if ny in ys and abs(nx * h - ny * w) * 4 <= max(w, h):
            pairs.append((x, ys[ny]))
    span_pair = max(pairs, key=lambda pair: pair[0]["score"] + pair[1]["score"], default=None)
    best_span_score = sum(c["score"] for c in span_pair) if span_pair else 0
    # A cropped integer grid needs substantially stronger evidence to replace
    # a full-span rational explanation; this rejects JPEG's 2/8-pixel aliases.
    # Retain integer phase candidates for cropped/offset grids as well.
    for size in sorted({c["cell"] for c in cx if c["family"] == "B"}):
        xs = [c for c in cx if c["family"] == "B" and c["cell"] == size]
        yy = [c for c in cy if c["family"] == "B" and c["cell"] == size]
        if xs and yy:
            pair = (max(xs, key=lambda c: c["score"]), max(yy, key=lambda c: c["score"]))
            near_span = span_pair is not None and all(
                abs(c["numerator"] * ref["denominator"] - ref["numerator"] * c["denominator"]) * 10
                <= ref["numerator"] * c["denominator"]
                for c, ref in zip(pair, span_pair, strict=True)
            )
            if near_span and pair[0]["score"] + pair[1]["score"] >= best_span_score * 2:
                pairs.append(pair)
    if not pairs:
        return None, None
    ax, ay = max(
        pairs,
        key=lambda pair: (
            (pair[0]["score"] + pair[1]["score"])
            * min(
                4,
                (w * pair[0]["denominator"] + pair[0]["numerator"] // 2) // pair[0]["numerator"],
                (h * pair[1]["denominator"] + pair[1]["numerator"] // 2) // pair[1]["numerator"],
            ),
            -pair[0]["cell"],
            pair[0]["family"] == "B",
            -pair[0]["offset"],
            -pair[1]["offset"],
        ),
    )
    if min(ax["score"], ay["score"]) < min_peak:
        return None, None
    return ax, ay


def _intervals(candidate, length):
    boundaries = [0] + candidate["boundaries"] + [length]
    pairs = list(zip(boundaries, boundaries[1:], strict=False))
    if candidate["family"] == "B":
        pairs = [(a, b) for a, b in pairs if 2 * (b - a) >= candidate["cell"]]
    return pairs


def cell_purity(images, x_cells, y_cells, tolerance=16):
    frames = rgba_frames(images)
    integer(tolerance, "purity_tolerance", 0, 255)
    matched, total = 0, 0
    uniform = regular_cells(frames[0].shape, x_cells, y_cells)
    if uniform is not None:
        ch, cw = uniform
        dx, dy = (max(1, cw // 5) if cw >= 4 else 0), (max(1, ch // 5) if ch >= 4 else 0)
        for frame in frames:
            blocks = frame.reshape(len(y_cells), ch, len(x_cells), cw, 4).transpose(0, 2, 1, 3, 4)
            pixels = blocks[:, :, dy : ch - dy, dx : cw - dx].reshape(
                -1, (ch - 2 * dy) * (cw - 2 * dx), 4
            )
            med = np.partition(pixels, (pixels.shape[1] - 1) // 2, axis=1)[
                :, (pixels.shape[1] - 1) // 2
            ]
            matched += int(
                np.count_nonzero(
                    np.all(np.abs(pixels.astype(np.int32) - med[:, None]) <= tolerance, axis=2)
                )
            )
            total += pixels.shape[0] * pixels.shape[1]
        return {
            "grid_score": matched * 1000 // total,
            "matched_pixels": matched,
            "interior_pixels": total,
        }
    for frame in frames:
        for top, bottom in y_cells:
            for left, right in x_cells:
                pixels = interior(frame[top:bottom, left:right]).reshape(-1, 4).astype(np.int64)
                med = lower_median(pixels)
                matched += int(np.count_nonzero(np.all(np.abs(pixels - med) <= tolerance, axis=1)))
                total += len(pixels)
    return {
        "grid_score": matched * 1000 // total if total else 0,
        "matched_pixels": matched,
        "interior_pixels": total,
    }


def regular_cells(shape, xs, ys):
    """Return uniform full-image cell height/width, or None for partial cells."""
    if not xs or not ys:
        return None
    cw, ch = xs[0][1], ys[0][1]
    if (
        xs == [(i * cw, (i + 1) * cw) for i in range(len(xs))]
        and ys == [(i * ch, (i + 1) * ch) for i in range(len(ys))]
        and xs[-1][1] == shape[1]
        and ys[-1][1] == shape[0]
    ):
        return ch, cw
    return None


def detect_grid(
    images,
    mode="auto",
    *,
    min_cell=2,
    max_cell=64,
    force_square=True,
    harmonic_tolerance=850,
    min_peak=1500,
    purity_tolerance=16,
    candidate_agreement=None,
    cell_w=None,
    cell_h=None,
    offset_x=0,
    offset_y=0,
    target_w=None,
    target_h=None,
):
    frames = rgba_frames(images)
    if candidate_agreement is None:
        from .defaults import load_defaults

        candidate_agreement = load_defaults()["common"]["grid"]["candidate_agreement"]
    integer(candidate_agreement, "candidate_agreement", 0, 1000)
    h, w = frames[0].shape[:2]
    require(mode in ("auto", "fixed", "target", "none"), "Unknown grid mode.")
    integer(min_cell, "min_cell", 1)
    integer(max_cell, "max_cell", min_cell)
    integer(harmonic_tolerance, "harmonic_tolerance", 0, 1000)
    integer(min_peak, "min_peak", 1)
    tops: dict[str, list[dict[str, Any]]] = {"x": [], "y": []}
    exact = False
    if mode == "auto":
        ex, energy_x, peaks_x = _signals(frames, 1)
        ey, energy_y, peaks_y = _signals(frames, 0)
        cx, cy = axis_candidates(ex, min_cell, max_cell), axis_candidates(ey, min_cell, max_cell)
        ax = ay = None

        # A sparse drawing can concentrate all energy at a few boundaries.
        # Explain every observed edge before comparing average peak heights.
        def exact_candidates(candidates, signal):
            events = set(int(i) for i in np.flatnonzero(signal))
            return [
                c
                for c in candidates
                if events
                and events.issubset(c["boundaries"])
                and sum(b - a for a, b in _intervals(c, len(signal))) == len(signal)
            ]

        exact_x, exact_y = exact_candidates(cx, ex), exact_candidates(cy, ey)
        if force_square:
            sizes = sorted(
                {c["cell"] for c in exact_x if c["family"] == "B"}
                & {c["cell"] for c in exact_y if c["family"] == "B"}
            )
            if sizes:
                exact = True
                size = sizes[-1]
                ax = min(
                    (c for c in exact_x if c["family"] == "B" and c["cell"] == size),
                    key=lambda c: c["offset"],
                )
                ay = min(
                    (c for c in exact_y if c["family"] == "B" and c["cell"] == size),
                    key=lambda c: c["offset"],
                )
        else:
            if exact_x:
                ax = sorted(exact_x, key=cmp_to_key(_size_compare))[-1]
            if exact_y:
                ay = sorted(exact_y, key=cmp_to_key(_size_compare))[-1]
        if not force_square and ax is not None and ay is not None:
            exact = True
        if not exact:
            _normalized_candidates(cx, energy_x, peaks_x)
            _normalized_candidates(cy, energy_y, peaks_y)
            _knot_candidates(cx, frames, 1)
            _knot_candidates(cy, frames, 0)
            ax, ay = _normalized_select(cx, cy, w, h, force_square, min_peak)
        else:
            for c in cx + cy:
                c["score"] = c["peak"]
                c["alignment"] = 1000
                c["coherence"] = 1000
        tops = {
            "x": sorted(cx, key=lambda c: (-c["score"], -c["peak"], c["cell"], c["offset"]))[:5],
            "y": sorted(cy, key=lambda c: (-c["score"], -c["peak"], c["cell"], c["offset"]))[:5],
        }
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
        ax, ay = (
            _fixed_axis(n, size, offset)
            for n, size, offset in ((w, cell_w, offset_x), (h, cell_h, offset_y))
        )
    detected = ax is not None and ay is not None
    xs, ys = (_intervals(ax, w), _intervals(ay, h)) if detected else ([], [])
    detected = detected and bool(xs) and bool(ys)
    purity = cell_purity(frames, xs, ys, purity_tolerance)
    return {
        "mode": mode,
        "detected": detected,
        "x": ax,
        "y": ay,
        "cell_w": ax["cell"] if ax else None,
        "cell_h": ay["cell"] if ay else None,
        "offset_x": ax["offset"] if ax else None,
        "offset_y": ay["offset"] if ay else None,
        "x_cells": xs,
        "y_cells": ys,
        "columns": len(xs),
        "rows": len(ys),
        "peak": min(ax["peak"], ay["peak"]) if ax is not None and ay is not None else 0,
        "candidates": tops,
        "alignment": min(ax.get("alignment", 1000), ay.get("alignment", 1000))
        if ax is not None and ay is not None
        else 0,
        "normalized_score": min(ax.get("score", 0), ay.get("score", 0))
        if ax is not None and ay is not None
        else 0,
        "ambiguous": bool(
            mode == "auto"
            and detected
            and not exact
            and any(
                len(tops[k]) > 1
                and tops[k][1]["score"] * 1000 >= tops[k][0]["score"] * candidate_agreement
                and _different_size(tops[k][0], tops[k][1])
                for k in ("x", "y")
            )
        ),
        **purity,
    }


def _different_size(a, b):
    return a["numerator"] * b["denominator"] != b["numerator"] * a["denominator"]


def _target_axis(n, count):
    return {
        "family": "A",
        "numerator": n,
        "denominator": count,
        "cell": (n + count // 2) // count,
        "offset": 0,
        "peak": 0,
        "boundaries": [(k * n + count // 2) // count for k in range(1, count)],
    }


def _fixed_axis(n, size, offset):
    return {
        "family": "B",
        "numerator": size,
        "denominator": 1,
        "cell": size,
        "offset": offset,
        "peak": 0,
        "boundaries": list(range(offset or size, n, size)),
    }
