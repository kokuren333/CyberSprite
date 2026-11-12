"""File-oriented API used by the independently generated CLI (§9.4.3)."""

from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from cybersprite.core.canonical import metadata_bytes
from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.history import atomic_write

from ._common import PipelineError
from .decode import decode_raster, split_sheet
from .grid import detect_grid as _detect_grid
from .runner import checked_png, color_strings, run_pipeline


def detect_grid(path, **options):
    """Decode an input and return the common grid dictionary, without project writes."""
    try:
        images, decoded = decode_raster(path)
        result = _detect_grid(images, **options)
        result["warnings"] = decoded["warnings"]
        return result
    except PipelineError as error:
        raise CyberSpriteError(error.code, error.message, error.hint, error.details) from error
    except TypeError as error:
        raise invalid("Unknown grid detection option.", reason=str(error)) from error


def convert(input_path, output_path, *, guard=None, **options):
    """Convert to indexed PNG and <output>.report.json, optionally retaining stages.

    ``guard(path, directory=False)`` is called for every destination before the
    first write; the CLI passes the export preflight so convert refuses the same
    protected paths as export (R2-01).
    """
    try:
        return _convert(input_path, output_path, guard=guard, **options)
    except OSError as error:
        raise CyberSpriteError(
            "E_IO",
            f"Cannot save conversion artifacts: {error}",
            "Check output paths and directory permissions.",
        ) from error
    except TypeError as error:
        raise invalid("Invalid conversion path or option type.", reason=str(error)) from error


def _convert(input_path, output_path, *, guard=None, **options):
    preset = options.pop("preset", "ai")
    pipeline = deepcopy(options.pop("pipeline", None) or {})
    stages = options.pop("stages", None)
    sheet = options.pop("sheet", None)
    if stages is not None and not isinstance(stages, (str, Path)):
        raise invalid("stages must be a directory path.")
    if not isinstance(pipeline, dict):
        raise invalid("pipeline must be an object of section overrides.")
    policy = options.pop("on_gate_fail", "reject")
    if policy not in ("reject", "accept"):
        raise invalid("on_gate_fail must be reject or accept.")
    for name, value in options.items():
        if name in (
            "grid",
            "downsample",
            "background",
            "palette",
            "cleanup",
            "dither",
            "outline",
            "gates",
            "quantize",
            "reconstruct",
        ):
            pipeline[name] = value
        else:
            raise invalid("Unknown conversion option.", option=name)
    try:
        images, decoded = decode_raster(input_path)
        images = split_sheet(images, sheet)
    except PipelineError as error:
        raise CyberSpriteError(error.code, error.message, error.hint, error.details) from error
    output = Path(output_path)
    if output.suffix.lower() != ".png":
        raise invalid("convert output must use .png; use export operations for other formats.")
    report_path = Path(str(output) + ".report.json")
    frame_paths = [
        output if i == 0 else output.with_name(f"{output.stem}_f{i:04d}.png")
        for i in range(len(images))
    ]
    if guard is not None:
        for destination in (*frame_paths, report_path):
            guard(destination)
        if stages is not None:
            guard(Path(stages), directory=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    context = nullcontext(stages) if stages is not None else TemporaryDirectory(dir=output.parent)
    outputs = []
    with context as location:
        directory = Path(location)
        indices, palette, report = run_pipeline(
            images, directory, preset=preset, overrides=pipeline
        )
        accepted = (report["accepted"] or policy == "accept") and not report.get("capacity_failure")
        report["accepted"] = accepted
        report["gates_overridden"] = (
            [g["name"] for g in report["gates"] if g["outcome"] == "fail"] if accepted else []
        )
        if accepted:
            for i, frame in enumerate(indices):
                destination = output if i == 0 else output.with_name(f"{output.stem}_f{i:04d}.png")
                if guard is not None and destination not in frame_paths:
                    guard(destination)
                atomic_write(destination, checked_png(frame, color_strings(palette, 0)))
                outputs.append(destination.as_posix())
        stage_paths = (
            [directory.joinpath(p).as_posix() for p in report["stage_paths"]]
            if stages is not None
            else []
        )
        if stages is None:
            report["stage_paths"] = []
            for step in report["steps"]:
                step["image"] = None
                step.pop("images", None)
        else:
            atomic_write(directory.joinpath("pipeline_report.json"), metadata_bytes(report))
        atomic_write(report_path, metadata_bytes(report))
    return {
        "accepted": accepted,
        "output": output.as_posix() if accepted else None,
        "outputs": outputs,
        "report_path": report_path.as_posix(),
        "stage_paths": stage_paths,
        "gates": report["gates"],
        "verified": accepted,
        "warnings": decoded["warnings"] + report.get("warnings", []),
    }
