"""Deterministic six-step integration and self-verified stage artifacts."""

from pathlib import Path

import numpy as np

from cybersprite.core.canonical import metadata_bytes
from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.history import atomic_write
from cybersprite.core.pixels import rgba
from cybersprite.formats.palette_files import read_palette
from cybersprite.formats.png import decode_png, encode_png, environment_fingerprint
from cybersprite.plugins import plugin_error
from cybersprite.plugins.contracts import IndexedImage

from ._common import PipelineError, require, rgba_frames
from .cleanup import cleanup_pixels
from .decisions import outline_and_dither
from .downsample import downsample, remove_background
from .grid import detect_grid
from .metrics import build_pipeline_report, compute_metrics, evaluate_gates, stage_report
from .plugin_steps import StepRunner
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
    if settings.get("reconstruct") is None:
        settings.pop("reconstruct", None)
    allowed = {
        "grid",
        "downsample",
        "background",
        "palette",
        "cleanup",
        "dither",
        "outline",
        "gates",
        "reconstruct",
    }
    require(not (set(settings) - allowed), "Unknown pipeline settings section.")
    for key in settings:
        require(isinstance(settings[key], dict), f"Pipeline section {key} must be an object.")
    plugins = StepRunner()
    grid_settings = dict(settings["grid"])
    grid_method = grid_settings.pop("method", None)
    grid_settings.pop("params", None)
    if "reconstruct" in settings:
        grid = detect_grid(images, mode="none")
    elif plugins.resolve("grid", grid_method) is not None:
        images, _ = plugins.run("grid", grid_method, images, settings["grid"])
        grid = detect_grid(images, **grid_settings)
    else:
        require(not settings["grid"].get("params"), "grid.params requires a plugin method.")
        if grid_method is not None:
            grid_settings["mode"] = grid_method
        grid = detect_grid(images, **grid_settings)
    # Preserve a diagnostic conversion when auto fails, without calling it a detected grid.
    working_grid = grid if grid["detected"] else detect_grid(images, mode="none")
    down_settings = dict(settings["downsample"])
    down_method = down_settings["method"]
    down_settings.pop("params", None)
    if (
        down_method == "auto"
        and grid["mode"] == "target"
        and any(
            d.name in ("downsample.pixeloe", "pixeloe")
            for d in plugins.manager.descriptors("cybersprite.pipeline_steps")
        )
    ):
        down_method = "pixeloe"
    if "reconstruct" in settings:
        reconstruct = settings["reconstruct"]
        plugins.resolve("reconstruct", reconstruct["method"])
        downs, down_report = plugins.run(
            "reconstruct",
            reconstruct["method"],
            images,
            reconstruct,
            grid=working_grid,
            grid_settings=grid_settings,
        )
        grid = detect_grid(downs, mode="none")
        working_grid = grid
    elif plugins.resolve("downsample", down_method) is not None:
        downs, down_report = plugins.run(
            "downsample", down_method, images, settings["downsample"], grid=working_grid
        )
        if any(im.shape[:2] != (grid["rows"], grid["columns"]) for im in downs):
            raise plugin_error(down_method, "downsample dimensions must match the detected grid.")
    else:
        require(
            not settings["downsample"].get("params"),
            "downsample.params requires a plugin method.",
        )
        downs, down_report = downsample(
            images, working_grid, **down_settings, background=settings["background"]
        )
    if "background" not in down_report:
        backgrounds, normalized = [], []
        for image in downs:
            image = image.copy()
            opaque = image[..., 3] >= down_settings.get("alpha_threshold", 128)
            image[~opaque] = 0
            image[opaque, 3] = 255
            image, background = remove_background(image, **settings["background"])
            normalized.append(image)
            backgrounds.append(background)
        downs = normalized
        down_report["background"] = backgrounds
    # Measure error before background removal or palette quantization can hide a bad grid.
    variance_sum = variance_pixels = 0
    if grid["detected"] and grid["mode"] != "none":
        for image in images:
            for top, bottom in grid["y_cells"]:
                for left, right in grid["x_cells"]:
                    cell = image[top:bottom, left:right, :3].astype(np.int64)
                    center = cell[cell.shape[0] // 2, cell.shape[1] // 2]
                    delta = cell - center
                    variance_sum += int((delta * delta).sum(dtype=np.int64))
                    variance_pixels += cell.shape[0] * cell.shape[1] * 3
    grid["snap_variance"] = variance_sum // max(1, variance_pixels)
    ti = project.palette.transparent_index if project else 0
    existing = [rgba(c) for c in project.palette.colors] if project else None
    pal_settings = dict(settings["palette"])
    quant_method = pal_settings.pop("method", None)
    pal_settings.pop("params", None)
    quant_plugin = plugins.resolve("quantize", quant_method)
    if quant_method is not None and quant_plugin is None:
        pal_settings["mode"] = quant_method
    if pal_settings.get("mode") == "fixed":
        src = pal_settings.get("source")
        if isinstance(src, str):
            pal_settings["source"] = [rgba(c) for c in read_palette(src)]
    capacity_failure = None
    try:
        if quant_plugin is None:
            require(
                not settings["palette"].get("params"), "palette.params requires a plugin method."
            )
            indices, palette, quant_report = quantize(
                downs,
                **pal_settings,
                project_palette=existing,
                transparent_index=ti,
                dither_type=settings["dither"]["type"],
                strength=settings["dither"]["strength"],
            )
        else:
            quantized, quant_report = plugins.run(
                "quantize",
                quant_method,
                downs,
                settings["palette"],
                project_palette=existing,
                transparent_index=ti,
                dither_type=settings["dither"]["type"],
                strength=settings["dither"]["strength"],
            )
            palette = quantized[0].palette
            if (
                any(
                    im.pixels.shape != src.shape[:2]
                    for im, src in zip(quantized, downs, strict=True)
                )
                or ti >= len(palette)
                or existing is None
                and palette[ti][3] != 0
                or any(c[3] != 255 for c in palette[len(existing) if existing else 1 :])
                or existing is not None
                and palette[: len(existing)] != existing
                or pal_settings["mode"] == "project"
                and palette != existing
            ):
                raise plugin_error(
                    quant_method, "quantizer must preserve dimensions and the locked palette."
                )
            indices = [im.pixels for im in quantized]
            quant_report["palette_added"] = palette[len(existing) if existing else 1 :]
            quant_report["palette_size"] = len(palette)
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
    protected_indices = []
    from ._common import color_channels
    from .oklab import dist2, rgb_to_oklab_fixed

    for color in pal_settings.get("protect", []):
        lab = rgb_to_oklab_fixed(color_channels(color)[:3])
        choices = [i for i, c in enumerate(palette) if i != ti and c[3] == 255]
        if choices:
            protected_indices.append(
                min(choices, key=lambda i: (dist2(lab, rgb_to_oklab_fixed(palette[i][:3])), i))
            )
    cleanup_settings = dict(settings["cleanup"])
    cleanup_method = cleanup_settings.pop("method", None)
    cleanup_settings.pop("params", None)
    cleanup_plugin = plugins.resolve("cleanup", cleanup_method)
    cleanup_settings["protect"] = sorted(set(cleanup_settings["protect"] + protected_indices))
    cleaned, clean_reports = [], []
    if cleanup_plugin is not None:
        outputs, clean_report = plugins.run(
            "cleanup",
            cleanup_method,
            [IndexedImage(im, palette) for im in indices],
            settings["cleanup"],
            transparent_index=ti,
        )
        cleaned = [im.pixels for im in outputs]
        clean_reports = clean_report["frames"]
    else:
        require(not settings["cleanup"].get("params"), "cleanup.params requires a plugin method.")
        for frame in indices:
            frame, clean_report = cleanup_pixels(
                frame, palette, transparent_index=ti, **cleanup_settings
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
        cleanup=cleanup_settings,
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
        plugins=plugins.records,
        steps=steps,
        grid=grid,
        gates=judged["gates"],
        result_frames=final,
        palette_added=color_strings(added),
    )
    report["warnings"] = [
        {
            "code": "W_PIPELINE_GATE",
            "gate": g["name"],
            "message": f"Pipeline gate {g['name']} passed with warnings.",
            "hint": "Inspect stage images and gate values; supply "
            "fixed/target grid or adjust the relevant settings.",
        }
        for g in judged["gates"]
        if g["outcome"] == "warn"
    ]
    if plugins.records:
        report["determinism"] = (
            "level-a" if all(p["level_a"] for p in plugins.records) else "same-platform"
        )
        report["warnings"].extend(
            {
                "code": "W_PLUGIN_DETERMINISM",
                "plugin": p["name"],
                "message": "Plugin step declares same-platform determinism only.",
                "hint": "Retain the recorded plugin version, parameters and platform to reproduce.",
            }
            for p in plugins.records
            if not p["level_a"]
        )
    report["warnings"].extend(
        {
            "code": "W_BACKGROUND_KEPT",
            "message": message,
            "hint": "Set background.color with mode=key, increase "
            "auto_tolerance, or use keep intentionally.",
        }
        for background in down_report["background"]
        for message in background["warnings"]
    )
    if (
        project
        and pal_settings["mode"] == "project"
        and "mode" not in (overrides or {}).get("palette", {})
    ):
        from cybersprite.core.projects import DEFAULT_PALETTE

        default = read_palette("cs-circuit-16")
        if project.palette.colors in (default, DEFAULT_PALETTE):
            report["warnings"].append(
                {
                    "code": "W_DEFAULT_PALETTE",
                    "message": "Import implicitly maps colors to the unchanged "
                    "default project palette.",
                    "hint": (
                        'Use pipeline.palette.mode="extract" or set the project '
                        "palette before importing."
                    ),
                }
            )
    report["configuration"] = origin
    report["stage_paths"] = stage_paths
    report["verified"] = True
    if capacity_failure:
        report["capacity_failure"] = capacity_failure
    atomic_write(directory.joinpath("pipeline_report.json"), metadata_bytes(report))
    return final, palette, report
