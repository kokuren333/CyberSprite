"""Pure metric and gate computations (§11.8); no manifest or placement I/O."""

import hashlib
import struct
from copy import deepcopy

import numpy as np

from ._common import integer, require, rgba_frames
from .cleanup import components
from .oklab import dist2, rgb_to_oklab_fixed_numpy


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
        orphans.append(
            sum(
                len(cluster) == 1
                for _, cluster in components(frame, transparent_index=transparent_index)
            )
        )
        original_labs = rgb_to_oklab_fixed_numpy(original[:, :, :3])
        # Alpha has no colour distance; source-transparent pixels are excluded.
        for y, x in np.argwhere((original[:, :, 3] >= 128) & (frame < len(palette))):
            fidelity_sum += dist2(original_labs[y, x], palette_labs[int(frame[y, x])])
            fidelity_count += 1
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
