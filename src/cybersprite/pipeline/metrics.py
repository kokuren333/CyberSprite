"""Pure metric and gate computations (§11.8); no manifest or placement I/O."""

import hashlib
import struct
from copy import deepcopy

import numpy as np

from ._common import integer, require, rgba_frames
from .defaults import load_defaults
from .oklab import rgb_to_oklab_fixed_numpy


def orphan_count(frame, transparent_index=0):
    connected = np.zeros(frame.shape, dtype=bool)
    h, w = frame.shape
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx or dy:
                a = (slice(max(0, dy), min(h, h + dy)), slice(max(0, dx), min(w, w + dx)))
                b = (slice(max(0, -dy), min(h, h - dy)), slice(max(0, -dx), min(w, w - dx)))
                connected[a] |= frame[a] == frame[b]
    return int(np.count_nonzero(~connected & (frame != transparent_index)))


def pixel_sha256(image):
    require(image.dtype == np.uint8 and image.ndim in (2, 3), "Pixel hashes require uint8 pixels.")
    require(image.ndim == 2 or image.shape[2] == 4, "RGBA pixel hashes require four channels.")
    h, w = image.shape[:2]
    return hashlib.sha256(
        b"CSPX1" + struct.pack("<IIB", w, h, int(image.ndim == 3)) + image.tobytes(order="C")
    ).hexdigest()


def compute_metrics(source_frames, index_frames, palette, *, transparent_index=0):
    source = (
        [source_frames]
        if isinstance(source_frames, np.ndarray) and source_frames.ndim == 3
        else list(source_frames)
    )
    for frame in source:
        rgba_frames(frame)
    if isinstance(index_frames, np.ndarray):
        index_frames = [index_frames]
    frames = list(index_frames)
    require(
        bool(frames) and len(source) == len(frames), "Source and index frame counts must match."
    )
    integer(transparent_index, "transparent_index", 0, len(palette) - 1)
    palette_labs = rgb_to_oklab_fixed_numpy(np.asarray([c[:3] for c in palette], dtype=np.int64))
    off_palette = fidelity_sum = fidelity_count = 0
    colors, orphans, sizes = [], [], []
    for original, frame in zip(source, frames, strict=True):
        require(
            frame.ndim == 2 and frame.dtype == np.uint8 and min(frame.shape) > 0,
            "Metrics require nonempty H x W uint8 index frames.",
        )
        require(
            frame.shape == original.shape[:2], "Fidelity source and result dimensions must match."
        )
        off_palette += int(np.count_nonzero(frame >= len(palette)))
        sizes.append([int(frame.shape[1]), int(frame.shape[0])])
        colors.append(len(np.unique(frame[frame != transparent_index])))
        orphans.append(orphan_count(frame, transparent_index))
        # Alpha has no colour distance; source-transparent pixels are excluded.
        mask = (original[:, :, 3] >= 128) & (frame < len(palette))
        source_colors, inverse = np.unique(original[mask, :3], axis=0, return_inverse=True)
        original_labs = rgb_to_oklab_fixed_numpy(source_colors)
        delta = original_labs[inverse] - palette_labs[frame[mask]]
        fidelity_sum += int((delta * delta).sum(dtype=np.int64))
        fidelity_count += int(np.count_nonzero(mask))
    return {
        "off_palette": off_palette,
        "orphans": sum(orphans),
        "orphans_per_frame": orphans,
        "colors_per_frame": max(colors),
        "frame_color_counts": colors,
        "fidelity": fidelity_sum // fidelity_count if fidelity_count else 0,
        "fidelity_sum": fidelity_sum,
        "fidelity_pixels": fidelity_count,
        "sizes": sizes,
        "frame_consistency": all(s == sizes[0] for s in sizes),
        "palette_size": len(palette),
        "pixel_sha256": [pixel_sha256(frame) for frame in frames],
    }


def evaluate_gates(
    metrics,
    grid,
    *,
    grid_thresholds=None,
    fidelity_thresholds=None,
    grid_cell_count=None,
    boundary_alignment=None,
    snap_fidelity=None,
    palette_max=256,
    palette_frozen=False,
    palette_added=0,
    colors_per_frame_max=None,
    cleanup=None,
    target_size=None,
    canvas_size=None,
    position=(0, 0),
):
    """Threshold pairs are (fail, warn); None means the gate is not judged."""
    defaults = load_defaults()["common"]["gates"]
    grid_cell_count = defaults["grid_cell_count"] if grid_cell_count is None else grid_cell_count
    boundary_alignment = (
        defaults["boundary_alignment"] if boundary_alignment is None else boundary_alignment
    )
    snap_fidelity = defaults["snap_fidelity"] if snap_fidelity is None else snap_fidelity
    for name, pair in (
        ("grid_cell_count", grid_cell_count),
        ("boundary_alignment", boundary_alignment),
        ("snap_fidelity", snap_fidelity),
    ):
        require(
            isinstance(pair, (list, tuple))
            and len(pair) == 2
            and all(type(value) is int and value >= 0 for value in pair),
            f"Gate {name} requires two nonnegative integers.",
        )
    gates = []

    def add(name, value, threshold, passed=True, warning=False):
        gates.append(
            {
                "name": name,
                "value": value,
                "threshold": threshold,
                "outcome": "fail" if not passed else "warn" if warning else "pass",
            }
        )

    add("grid_detected", grid["detected"], True, grid["mode"] != "auto" or grid["detected"])
    score = grid["grid_score"]
    add(
        "grid_score",
        score,
        grid_thresholds,
        grid_thresholds is None or score >= grid_thresholds[0],
        grid_thresholds is not None and score < grid_thresholds[1],
    )
    if grid["mode"] != "none" and grid["detected"]:
        short = min(grid["columns"], grid["rows"])
        span = min(grid["x_cells"][-1][1], grid["y_cells"][-1][1])
        auto = grid["mode"] == "auto"
        add(
            "grid_cell_count",
            short,
            {"warn_below": grid_cell_count[0], "input_min": grid_cell_count[1]},
            warning=short < grid_cell_count[0] and span >= grid_cell_count[1],
        )
        alignment = grid.get("alignment", 1000)
        add(
            "boundary_alignment",
            alignment,
            {"fail_below": boundary_alignment[0], "warn_below": boundary_alignment[1]},
            not auto or alignment >= boundary_alignment[0],
            auto and alignment < boundary_alignment[1],
        )
        add(
            "candidate_agreement",
            not grid.get("ambiguous", False),
            True,
            warning=auto and grid.get("ambiguous", False),
        )
        variance = grid.get("snap_variance", 0)
        add(
            "snap_fidelity",
            variance,
            {"fail_above": snap_fidelity[0], "warn_above": snap_fidelity[1]},
            not auto or variance <= snap_fidelity[0],
            variance > snap_fidelity[1],
        )
    budget = min(256, integer(palette_max, "palette_max", 1, 256))
    add(
        "palette_budget",
        metrics["palette_size"],
        {"max": budget, "frozen": palette_frozen},
        metrics["palette_size"] <= budget and not (palette_frozen and palette_added),
    )
    add("off_palette", metrics["off_palette"], 0, metrics["off_palette"] == 0)
    cleanup = {"min_cluster": 2, "protect": [], **(cleanup or {})}
    judge_orphans = cleanup["min_cluster"] > 1 and not cleanup["protect"]
    add(
        "orphans",
        metrics["orphans"],
        0 if judge_orphans else None,
        not judge_orphans or metrics["orphans"] == 0,
    )
    add(
        "colors_per_frame",
        metrics["colors_per_frame"],
        colors_per_frame_max,
        colors_per_frame_max is None or metrics["colors_per_frame"] <= colors_per_frame_max,
    )
    fidelity = metrics["fidelity"]
    add(
        "fidelity",
        fidelity,
        fidelity_thresholds,
        fidelity_thresholds is None or fidelity <= fidelity_thresholds[0],
        fidelity_thresholds is not None and fidelity > fidelity_thresholds[1],
    )
    add(
        "size",
        metrics["sizes"],
        target_size,
        target_size is None or all(s == list(target_size) for s in metrics["sizes"]),
    )
    fits = canvas_size is None or (
        position[0] >= 0
        and position[1] >= 0
        and all(
            position[0] + w <= canvas_size[0] and position[1] + h <= canvas_size[1]
            for w, h in metrics["sizes"]
        )
    )
    add("fits_canvas", fits, canvas_size, warning=not fits)
    add("frame_consistency", metrics["frame_consistency"], True, metrics["frame_consistency"])
    return {"gates": gates, "accepted": all(g["outcome"] != "fail" for g in gates)}


def stage_report(name, method, images, *, metrics=None, image=None):
    """Build stage metadata. The caller supplies any saved-preview reference."""
    if isinstance(images, np.ndarray):
        images = [images]
    images = list(images)
    require(bool(images), "Stage reports require at least one output frame.")
    hashes = [pixel_sha256(frame) for frame in images]
    return {
        "name": name,
        "method": method,
        "metrics": deepcopy(metrics or {}),
        "pixel_sha256": hashes[0],
        "frame_pixel_sha256": hashes,
        "image": image,
    }


def build_pipeline_report(
    *,
    source_id,
    preset,
    settings,
    environment,
    plugins,
    steps,
    grid,
    gates,
    result_frames,
    palette_added,
):
    """Assemble §11.8 report data, with all environment/I/O facts supplied.

    This function never probes the machine, saves an image, overrides a gate,
    or creates a manifest. Those responsibilities remain at the Op boundary.
    """
    if isinstance(result_frames, np.ndarray):
        result_frames = [result_frames]
    frames = list(result_frames)
    require(bool(frames), "A pipeline report requires at least one result frame.")
    require(
        all(f.ndim == 2 and f.dtype == np.uint8 for f in frames),
        "Pipeline result reports require uint8 index frames.",
    )
    hashes = [pixel_sha256(frame) for frame in frames]
    return {
        "source_id": source_id,
        "preset": preset,
        "settings": deepcopy(settings),
        "environment": deepcopy(environment),
        "plugins": deepcopy(plugins),
        "steps": deepcopy(steps),
        "grid": deepcopy(grid),
        "gates": deepcopy(gates),
        "accepted": all(g["outcome"] != "fail" for g in gates),
        "result": {
            "width": int(frames[0].shape[1]),
            "height": int(frames[0].shape[0]),
            "palette_added": deepcopy(palette_added),
            "pixel_sha256": hashes[0],
            "frame_pixel_sha256": hashes,
        },
    }
