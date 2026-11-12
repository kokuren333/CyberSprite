"""Deterministic six-step integration and self-verified stage artifacts."""

from pathlib import Path

import numpy as np

from cybersprite.core.canonical import metadata_bytes
from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.history import atomic_write
from cybersprite.core.pixels import rgba
from cybersprite.formats.palette_files import read_palette
from cybersprite.formats.png import decode_png, encode_png, environment_fingerprint

from ._common import PipelineError, require, rgba_frames
from .cleanup import cleanup_pixels
from .decisions import outline_and_dither
from .downsample import downsample
from .grid import detect_grid
from .metrics import build_pipeline_report, compute_metrics, evaluate_gates, stage_report
from .presets import resolve_preset
from .quantize import quantize

STAGES = ("stage1_grid", "stage2_downsampled", "stage3_quantized", "stage4_cleaned", "stage5_final")


def checked_png(pixels, palette=None):
    data = encode_png(pixels, palette, compression="stored")
    decoded = decode_png(data)
    if (
        not np.array_equal(decoded.pixels, pixels)
        or palette is not None
        and decoded.palette != palette
    ):
        raise CyberSpriteError(
            "E_INTERNAL",
            "Pipeline PNG self-verification failed.",
            "Report this input and settings to the pipeline maintainer.",
        )
    return data


def color_strings(palette, transparent_index=None):
    result = ["#" + bytes(color).hex() for color in palette]
    if transparent_index is not None:
        result[transparent_index] = "#00000000"
    return result


def run_pipeline(
    images,
    directory,
    *,
    source_id="SRC1",
    preset="ai",
    overrides=None,
    project=None,
    position=(0, 0),
):
    """Save reports/stages and return indexed frames, palette and report; never edit a project."""
    try:
        return _run(images, Path(directory), source_id, preset, overrides, project, position)
    except PipelineError as error:
        raise CyberSpriteError(error.code, error.message, error.hint, error.details) from error
    except TypeError as error:
        raise invalid("Unknown or invalid pipeline parameter.", reason=str(error)) from error


def _run(images, directory, source_id, preset, overrides, project, position):
    images = rgba_frames(images)
    settings, origin = resolve_preset(
        preset, existing_project=project is not None, overrides=overrides
    )
    allowed = {
        "grid",
        "downsample",
        "background",
        "palette",
        "cleanup",
        "dither",
        "outline",
        "gates",
    }
    require(not (set(settings) - allowed), "Unknown pipeline settings section.")
    for key in settings:
        require(isinstance(settings[key], dict), f"Pipeline section {key} must be an object.")
    grid = detect_grid(images, **settings["grid"])
    # Preserve a diagnostic conversion when auto fails, without calling it a detected grid.
    working_grid = grid if grid["detected"] else detect_grid(images, mode="none")
    downs, down_report = downsample(
        images, working_grid, **settings["downsample"], background=settings["background"]
    )
    ti = project.palette.transparent_index if project else 0
    existing = [rgba(c) for c in project.palette.colors] if project else None
    pal_settings = dict(settings["palette"])
    if pal_settings.get("mode") == "fixed":
        src = pal_settings.get("source")
        if isinstance(src, str):
            pal_settings["source"] = [rgba(c) for c in read_palette(src)]
    capacity_failure = None
    try:
        indices, palette, quant_report = quantize(
            downs,
            **pal_settings,
            project_palette=existing,
            transparent_index=ti,
            dither_type=settings["dither"]["type"],
            strength=settings["dither"]["strength"],
        )
    except PipelineError as error:
        if error.details.get("gate") != "palette_budget":
            raise
        capacity_failure = error.details
        # Diagnostic images remain representable; they cannot be placed as an override.
        indices, palette, quant_report = quantize(
            downs,
            mode="project" if existing else "extract",
            max_colors=255,
            project_palette=existing,
            transparent_index=ti,
        )
        quant_report["diagnostic_fallback"] = capacity_failure
    cleaned, clean_reports = [], []
    for frame in indices:
        frame, clean_report = cleanup_pixels(
            frame, palette, transparent_index=ti, **settings["cleanup"]
        )
        cleaned.append(frame)
        clean_reports.append(clean_report)
    outline = dict(settings["outline"])
    if isinstance(outline.get("color"), str):
        outline["color"] = rgba(outline["color"])
    owners = {
        key: "caller" if key in (overrides or {}) else "preset" for key in ("outline", "dither")
    }
    try:
        final, palette, choice_report = outline_and_dither(
            cleaned,
            palette,
            transparent_index=ti,
            outline=outline,
            dither=settings["dither"],
            chosen_by=owners,
        )
    except PipelineError as error:
        if error.details.get("gate") != "palette_budget":
            raise
        capacity_failure = error.details
        final, palette, choice_report = outline_and_dither(
            cleaned,
            palette,
            transparent_index=ti,
            outline={"mode": "keep"},
            dither=settings["dither"],
            chosen_by=owners,
        )
        choice_report["diagnostic_fallback"] = capacity_failure
    added = quant_report["palette_added"] + choice_report["palette_added"]
    metrics = compute_metrics(downs, final, palette, transparent_index=ti)
    if capacity_failure:
        metrics["palette_size"] = capacity_failure["palette_size"]
    thresholds = settings.get("gates", {})
    require(not (set(thresholds) - {"grid_score", "fidelity"}), "Unknown pipeline gate override.")
    for value in thresholds.values():
        require(
            value is None
            or isinstance(value, (list, tuple))
            and len(value) == 2
            and all(type(v) is int and v >= 0 for v in value),
            "Gate thresholds must be null or two nonnegative integers.",
        )
    judged = evaluate_gates(
        metrics,
        grid,
        grid_thresholds=thresholds.get("grid_score"),
        fidelity_thresholds=thresholds.get("fidelity"),
        palette_max=project.validation.palette_max if project else 256,
        palette_frozen=project.palette.frozen if project else False,
        palette_added=len(added),
        colors_per_frame_max=project.validation.colors_per_frame_max if project else None,
        cleanup=settings["cleanup"],
        target_size=(settings["grid"]["target_w"], settings["grid"]["target_h"])
        if grid["mode"] == "target"
        else None,
        canvas_size=(project.canvas.width, project.canvas.height) if project else None,
        position=position,
    )
    stage_frames = [[], downs, indices, cleaned, final]
    for image in images:
        overlay = image.copy()
        # Functional diagnostic overlay; final visual styling belongs to Opus.
        if grid["mode"] != "none" and grid["detected"]:
            for left, _ in working_grid["x_cells"][1:]:
                overlay[:, left] = (255, 0, 255, 255)
            for top, _ in working_grid["y_cells"][1:]:
                overlay[top, :] = (255, 0, 255, 255)
        stage_frames[0].append(overlay)
    steps, stage_paths = [], []
    reports = [grid, down_report, quant_report, {"frames": clean_reports}, choice_report]
    methods = [
        grid["mode"],
        down_report["method"],
        pal_settings["mode"],
        "components",
        outline["mode"],
    ]
    strings = color_strings(palette, ti)
    directory.mkdir(parents=True, exist_ok=True)
    for stage, frames, detail, method in zip(STAGES, stage_frames, reports, methods, strict=True):
        paths = []
        for i, frame in enumerate(frames):
            suffix = "" if i == 0 else f"_f{i:04d}"
            name = stage + suffix + ".png"
            scale = max(1, min(8, 256 // max(frame.shape[:2])))
            preview = frame.repeat(scale, 0).repeat(scale, 1)
            atomic_write(
                directory.joinpath(name), checked_png(preview, strings if frame.ndim == 2 else None)
            )
            paths.append(name)
        step = stage_report(stage, method, frames, metrics=detail, image=paths[0])
        step["images"] = paths
        steps.append(step)
        stage_paths.extend(paths)
    steps.append(
        {
            "name": "validation",
            "method": "integer-metrics",
            "metrics": metrics,
            "pixel_sha256": metrics["pixel_sha256"][0],
            "image": "result.png",
        }
    )
    for i, frame in enumerate(final):
        name = "result.png" if i == 0 else f"result_f{i:04d}.png"
        atomic_write(directory.joinpath(name), checked_png(frame, strings))
    report = build_pipeline_report(
        source_id=source_id,
        preset=preset,
        settings=settings,
        environment=environment_fingerprint(),
        plugins=[],
        steps=steps,
        grid=grid,
        gates=judged["gates"],
        result_frames=final,
        palette_added=color_strings(added),
    )
    report["configuration"] = origin
    report["stage_paths"] = stage_paths
    report["verified"] = True
    if capacity_failure:
        report["capacity_failure"] = capacity_failure
    atomic_write(directory.joinpath("pipeline_report.json"), metadata_bytes(report))
    return final, palette, report
