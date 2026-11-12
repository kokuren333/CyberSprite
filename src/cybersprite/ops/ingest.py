"""Source ingestion, conversion and registered transactional placement."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
from pydantic import Field

from cybersprite.core import history, sources
from cybersprite.core.canonical import load_project, metadata_bytes, project_path
from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.journal_clock import now
from cybersprite.core.models import (
    Frame,
    ImageCel,
    ImageLayer,
    Model,
    Placement,
    Source,
    SourceFile,
    SourceModel,
    SourcePipeline,
)
from cybersprite.core.pixels import pixels_to_rows
from cybersprite.core.projects import new_project
from cybersprite.core.transactions import transact
from cybersprite.pipeline._common import PipelineError
from cybersprite.pipeline.args import PipelineSettings
from cybersprite.pipeline.decode import decode_raster, split_sheet
from cybersprite.pipeline.runner import color_strings, run_pipeline

from .common import fail, image_layer, write_points
from .previews import transaction_previews

Nonnegative = Annotated[int, Field(ge=0)]
Positive = Annotated[int, Field(ge=1)]


class Provenance(Model):
    license: Annotated[str, Field(min_length=1)] = Field(
        description="Usage license identifier; use unknown when usage terms are unknown."
    )
    kind: Literal["imported", "generated"] = Field(
        "imported", description="Source origin: imported or generated."
    )
    provider: str = Field("file", description="Input provider name, for example file.")
    prompt: str = Field(
        "", description="Original generation prompt; empty for non-generated input."
    )
    negative_prompt: str = Field("", description="Original negative generation prompt, if any.")
    model: SourceModel | None = Field(
        None, description="Generator model identifier and version, if any."
    )
    url: str = Field("", description="Source attribution URL, if available.")
    rights_note: str = Field("", description="Additional usage-rights or attribution notes.")
    seed: int | None = Field(None, description="Original generation seed, if known.")
    params: dict = Field(
        default_factory=dict, description="Original generation parameters retained as provenance."
    )


class Target(Model):
    mode: Literal["new_layer", "layer"] = Field(
        "new_layer",
        description="Place in a new image layer or an explicitly referenced existing layer.",
    )
    layer: str | None = Field(None, description="Target layer ID, unique name, or group path.")
    name: Annotated[str, Field(min_length=1, max_length=255)] | None = Field(
        None, description="Human-readable resource name, at most 255 characters."
    )
    frame: Nonnegative = Field(0, description="Zero-based placement starting frame.")
    x: int = Field(0, description="Horizontal pixel coordinate from the canvas left edge.")
    y: int = Field(0, description="Vertical pixel coordinate from the canvas top edge.")
    add_frames: bool = Field(
        True, description="Extend the timeline when imported frames exceed its current length."
    )


class Sheet(Model):
    cell_w: Positive = Field(description="Sheet cell width in integer pixels.")
    cell_h: Positive = Field(description="Sheet cell height in integer pixels.")
    offset_x: Nonnegative = Field(0, description="Horizontal sheet margin before the first cell.")
    offset_y: Nonnegative = Field(0, description="Vertical sheet margin before the first cell.")
    spacing: Nonnegative = Field(0, description="Integer gap between neighboring sheet items.")


class ImportArgs(Model):
    files: str | Annotated[list[str], Field(min_length=1, max_length=4096)] | None = Field(
        None,
        description="One input raster path or a list of paths; mutually exclusive with source.",
    )
    sheet: Sheet | None = Field(
        None,
        description=(
            "Split one static input into complete cells using integer sizes, offsets, and spacing."
        ),
    )
    preset: Literal["ai", "exact", "upscaled", "photo"] = Field(
        "ai", description="Pipeline preset: ai, exact (lossless), upscaled, or photo."
    )
    pipeline: PipelineSettings = Field(
        default_factory=PipelineSettings,
        description="Documented section overrides; unspecified fields inherit preset values.",
    )
    target: Target = Field(
        default_factory=lambda: Target.model_validate({}),
        description=(
            "Placement layer, zero-based starting frame, integer position, and "
            "frame-extension policy."
        ),
    )
    provenance: Provenance | None = Field(
        None,
        description=(
            "Input origin and usage terms; license is required for new files (use "
            "unknown when unknown)."
        ),
    )
    on_gate_fail: Literal["reject", "accept"] = Field(
        "reject",
        description=(
            "Reject failed gates or explicitly accept and record overridden gates; "
            "capacity/freeze limits remain enforced."
        ),
    )
    source: str | None = Field(
        None,
        description=(
            "Existing source ID to reconvert with its original provenance; mutually "
            "exclusive with files."
        ),
    )


class ImportResult(Model):
    source: str | None
    accepted: bool
    report_path: str
    stage_paths: list[str]
    gates: list[dict]
    placed: dict | None


class ListSourcesArgs(Model):
    pass


class ListSourcesResult(Model):
    sources: list[dict]


class GetSourceArgs(Model):
    id: str = Field(description="Stored source ID, such as SRC1.")
    include_report: bool = Field(
        False, description="Include the saved pipeline report in the source response."
    )


class GetSourceResult(Source):
    report: dict | None = None


def source_query(ctx, args, name):
    manifest = sources.read_manifest(ctx.root)
    if name == "list_sources":
        return {
            "sources": [
                {
                    "id": s.id,
                    "kind": s.kind,
                    "provider": s.provider,
                    "license": s.license,
                    "accepted": s.pipeline.accepted if s.pipeline else False,
                    "placements": [p.model_dump() for p in s.placements],
                }
                for s in manifest.sources
            ]
        }
    source = sources.find_source(manifest, args.id)
    value = source.model_dump()
    if args.include_report and source.pipeline:
        path = sources.source_path(ctx.root, f"{source.id}/pipeline_report.json")
        import json

        try:
            value["report"] = json.loads(path.read_bytes())
        except (OSError, ValueError) as error:
            raise CyberSpriteError(
                "E_IO",
                "Cannot read pipeline report.",
                "Reconvert the source to recreate its report.",
            ) from error
    return value


def decode_files(paths, sheet=None):
    frames, durations, warnings, dimensions = [], [], [], []
    try:
        for path in paths:
            images, decoded = decode_raster(path)
            dimensions.append((int(images[0].shape[1]), int(images[0].shape[0])))
            frames.extend(images)
            durations.extend(decoded["durations_ms"])
            warnings.extend(decoded["warnings"])
    except PipelineError as error:
        raise CyberSpriteError(error.code, error.message, error.hint, error.details) from error
    if not frames or any(f.shape != frames[0].shape for f in frames):
        raise invalid("All imported frames must have the same width and height.")
    if sheet:
        try:
            frames = split_sheet(frames, sheet.model_dump())
        except PipelineError as error:
            raise CyberSpriteError(error.code, error.message, error.hint, error.details) from error
        durations = [100] * len(frames)
    if len(frames) > 4096:
        fail("E_LIMIT_EXCEEDED", "Imported animation exceeds 4096 frames.", limit=4096)
    return frames, durations, warnings, dimensions


def _capture(root, args, manifest):
    if (args.files is None) == (args.source is None):
        raise invalid("Specify exactly one of files or source.")
    if args.source:
        if args.provenance is not None:
            raise invalid("Reusing source preserves its provenance; omit provenance.")
        source = sources.find_source(manifest, args.source)
        paths = [sources.source_path(root, f.path) for f in source.files]
        for path, file in zip(paths, source.files, strict=True):
            if not path.is_file() or sha256(path.read_bytes()).hexdigest() != file.sha256:
                fail(
                    "E_IO",
                    "Stored original is missing or changed; restore it before reconverting.",
                    source=source.id,
                )
        frames, durations, warnings, _ = decode_files(paths, args.sheet)
        return source, frames, durations, warnings
    if args.provenance is None or not args.provenance.license.strip():
        raise invalid("provenance.license is required; use unknown when usage terms are unknown.")
    paths = [Path(p) for p in ([args.files] if isinstance(args.files, str) else args.files)]
    # Decode the captured bytes, never a separately re-opened mutable input.
    source_id = f"SRC{manifest.next_id}"
    directory = Path(root) / "source" / source_id
    while directory.exists():
        manifest.next_id += 1
        source_id = f"SRC{manifest.next_id}"
        directory = Path(root) / "source" / source_id
    directory.mkdir(parents=True)
    captured = []
    for i, path in enumerate(paths):
        name = "original" if len(paths) == 1 else f"original_{i:04d}"
        suffix = path.suffix.lower()
        destination = directory / (name + suffix)
        data = path.read_bytes()
        history.atomic_write(destination, data)
        captured.append(destination)
    frames, durations, warnings, dimensions = decode_files(captured, args.sheet)
    files = [
        SourceFile(
            path=path.relative_to(root).as_posix(),
            sha256=sha256(path.read_bytes()).hexdigest(),
            width=size[0],
            height=size[1],
            bytes=path.stat().st_size,
        )
        for path, size in zip(captured, dimensions, strict=True)
    ]
    stamp = now()
    source = Source(
        id=source_id,
        files=files,
        created_at=stamp,
        imported_at=stamp,
        pipeline=None,
        placements=[],
        **args.provenance.model_dump(),
    )
    manifest.next_id += 1
    manifest.sources.append(source)
    sources.save_manifest(root, manifest)
    return source, frames, durations, warnings


def import_top(registry, path, args, tx, actor):
    try:
        used = []
        if project_path(path).exists() and not ({"preset", "pipeline"} & args.model_fields_set):
            p = load_project(path)
            if p.platform:
                from cybersprite.platforms import merge

                defaults = p.platform.defaults.pipeline
                if defaults.preset:
                    args.preset = defaults.preset
                    used.append("defaults.pipeline.preset")
                nested: dict = {}
                for key, value in sorted(defaults.overrides.items()):
                    target = nested
                    parts = key.split(".")
                    for part in parts[:-1]:
                        target = target.setdefault(part, {})
                    target[parts[-1]] = value
                if nested:
                    args.pipeline = PipelineSettings.model_validate(merge({}, nested))
                    used.append("defaults.pipeline.overrides")
        result = _import_top(registry, path, args, tx, actor)
        if used:
            result["defaults_from_platform"] = used
        return result
    except OSError as error:
        raise CyberSpriteError(
            "E_IO",
            f"Cannot capture or save source: {error}",
            "Check input paths and project directory permissions.",
        ) from error


def _import_top(registry, path, args, tx, actor):
    root = project_path(path).parent
    if tx.dry_run:
        existing = load_project(root) if project_path(root).exists() else None
        if tx.expect_revision is not None and tx.expect_revision != (
            existing.revision if existing else 0
        ):
            fail("E_REVISION_CONFLICT", "Import revision does not match the current project.")
        if (args.files is None) == (args.source is None):
            raise invalid("Specify exactly one of files or source.")
        if args.source:
            manifest = sources.read_manifest(root)
            # _capture does not write when reusing an existing source.
            source, images, _, warnings = _capture(root, args, manifest)
            source_id = source.id
        else:
            paths = [Path(p) for p in ([args.files] if isinstance(args.files, str) else args.files)]
            images, _, warnings, _ = decode_files(paths, args.sheet)
            source_id = "dry"
        directory = root / ".cybersprite/previews/dry"
        _, _, report = run_pipeline(
            images,
            directory,
            source_id=source_id,
            preset=args.preset,
            overrides=args.pipeline.model_dump(exclude_unset=True),
            project=existing,
            position=(args.target.x, args.target.y),
        )
        return {
            "ok": True,
            "op": "import_image",
            "project": root.as_posix(),
            "dry_run": True,
            "revision": existing.revision if existing else 0,
            "would_commit": report["accepted"],
            "result": {
                "source": None,
                "accepted": report["accepted"],
                "report_path": ".cybersprite/previews/dry/pipeline_report.json",
                "stage_paths": [f".cybersprite/previews/dry/{s}" for s in report["stage_paths"]],
                "gates": report["gates"],
                "placed": None,
            },
            "warnings": warnings + report.get("warnings", []),
        }
    with history.ProjectLock(root, actor) as lock:
        existing = load_project(root) if project_path(root).exists() else None
        if tx.expect_revision is not None and tx.expect_revision != (
            existing.revision if existing else 0
        ):
            fail(
                "E_REVISION_CONFLICT",
                "Import revision does not match the current project.",
                current_revision=existing.revision if existing else 0,
            )
        if tx.idempotency_key:
            for entry in reversed(history.read_journal(root)[-1000:]):
                if entry.get("idempotency_key") == tx.idempotency_key and entry.get("result"):
                    result = entry["result"]
                    result["replayed"] = True
                    return result
        manifest = sources.read_manifest(root)
        previous_manifest = deepcopy(manifest)
        source, images, durations, warnings = _capture(root, args, manifest)
        directory = root / "source" / source.id
        overrides = args.pipeline.model_dump(exclude_unset=True) if args.pipeline else {}
        if existing is not None and not any(
            i != existing.palette.transparent_index and color[7:9].lower() == "ff"
            for i, color in enumerate(existing.palette.colors)
        ):
            # Undo of the first import retains a transparent-only baseline.
            # Preserve explicit palette modes; only replace the unusable default.
            overrides.setdefault("palette", {}).setdefault("mode", "extract")
        indices, palette, report = run_pipeline(
            images,
            directory,
            source_id=source.id,
            preset=args.preset,
            overrides=overrides,
            project=existing,
            position=(args.target.x, args.target.y),
        )
        warnings.extend(report.get("warnings", []))
        failed = [g["name"] for g in report["gates"] if g["outcome"] == "fail"]
        requires_unfreeze = (
            existing is not None
            and existing.palette.frozen
            and bool(report["result"]["palette_added"])
        )
        accepted = (
            (not failed or args.on_gate_fail == "accept")
            and not report.get("capacity_failure")
            and not requires_unfreeze
        )
        overridden = sorted(
            set(
                (source.pipeline.gates_overridden if source.pipeline else [])
                + (failed if accepted else [])
            )
        )
        source.pipeline = SourcePipeline(
            preset=args.preset,
            params=report["settings"],
            report={
                "path": f"source/{source.id}/pipeline_report.json",
                "grid_score": report["grid"]["grid_score"],
                "warnings": report.get("warnings", []),
            },
            result_sha256=sha256((directory / "result.png").read_bytes()).hexdigest(),
            accepted=accepted,
            gates_overridden=list(source.pipeline.gates_overridden) if source.pipeline else [],
        )
        sources.save_manifest(root, manifest)
        value = {
            "source": source.id,
            "accepted": accepted,
            "report_path": f"source/{source.id}/pipeline_report.json",
            "stage_paths": [f"source/{source.id}/{s}" for s in report["stage_paths"]],
            "gates": report["gates"],
            "placed": None,
        }
        report["accepted"] = accepted
        report["gates_overridden"] = failed if accepted else []
        history.atomic_write(directory / "pipeline_report.json", metadata_bytes(report))
        if report.get("capacity_failure") and args.on_gate_fail == "accept":
            fail(
                "E_LIMIT_EXCEEDED",
                "Palette capacity cannot be overridden; use palette.mode=project or fewer colors.",
                **report["capacity_failure"],
            )
        if requires_unfreeze and args.on_gate_fail == "accept":
            fail(
                "E_PALETTE_FROZEN",
                "Unfreeze the palette or choose palette.mode=project before placement.",
            )
        if not accepted:
            return {
                "ok": True,
                "op": "import_image",
                "project": root.as_posix(),
                "revision": existing.revision if existing else 0,
                "result": value,
                "warnings": warnings,
            }
        initial = None
        if existing is None:
            initial = new_project(
                width=indices[0].shape[1],
                height=indices[0].shape[0],
                name=root.stem,
                palette=["#00000000"],
            )
        prepared = {
            "indices": indices,
            "palette": palette,
            "durations": durations,
            "source": source,
            "manifest": manifest,
            "previous_manifest": previous_manifest,
            "overridden": overridden,
            "value": value,
            "new_project": initial is not None,
            "warnings": warnings
            + ([{"code": "W_GATE_OVERRIDDEN", "gates": failed}] if failed else []),
        }
        result = transact(
            registry,
            root,
            [{"op": "import_image", "args": args.model_dump()}],
            tx,
            op="import_image",
            actor=actor,
            previewer=transaction_previews,
            initial_project=initial,
            prepared=prepared,
            held_lock=lock,
        )
        return result


def place(ctx, args):
    if ctx.prepared is None:
        raise invalid("import_image must be invoked as a top-level ingest operation.")
    data, p = ctx.prepared, ctx.project
    ctx.warnings.extend(data["warnings"])
    target = args.target
    if target.mode == "new_layer" or data["new_project"]:
        original = args.files[0] if isinstance(args.files, list) else args.files
        name = target.name or Path(original or data["source"].files[0].path).stem
        layer = ImageLayer(id=p.id_counters.issue("layer"), name=name)
        p.layers.append(layer)
    else:
        if not target.layer:
            raise invalid("target.layer is required for target.mode=layer.")
        layer = image_layer(p, target.layer)
    end = target.frame + len(data["indices"])
    if end > 4096:
        fail("E_LIMIT_EXCEEDED", "Placement exceeds 4096 frames.", limit=4096)
    if end > len(p.frames) and not target.add_frames:
        fail("E_FRAME_OUT_OF_RANGE", "Placement needs more frames; set target.add_frames=true.")
    while len(p.frames) < end:
        relative = len(p.frames) - target.frame
        duration = data["durations"][relative] if 0 <= relative < len(data["durations"]) else 100
        p.frames.append(Frame(duration_ms=max(1, min(65535, duration))))
    if data["new_project"] and target.frame == 0:
        p.frames[0].duration_ms = max(1, min(65535, data["durations"][0]))
    p.palette.colors = color_strings(data["palette"])
    placed = list(range(target.frame, end))
    for f, indices in zip(placed, data["indices"], strict=True):
        if target.mode == "new_layer" or data["new_project"]:
            layer.cels.append(
                ImageCel(
                    frame=f,
                    x=target.x,
                    y=target.y,
                    w=indices.shape[1],
                    h=indices.shape[0],
                    pixels=pixels_to_rows(indices),
                )
            )
        else:
            write_points(
                ctx,
                layer,
                f,
                (
                    (target.x + int(x), target.y + int(y), int(indices[y, x]))
                    for y, x in np.argwhere(indices != p.palette.transparent_index)
                ),
            )
    data["source"].placements.append(
        Placement(revision=p.revision + 1, layer=layer.id, frames=placed)
    )
    data["source"].pipeline.gates_overridden = data["overridden"]
    ctx.source_manifest = data["manifest"]
    ctx.previous_source_manifest = data["previous_manifest"]
    ctx.side_writes.append(
        (sources.manifest_path(ctx.root), sources.manifest_bytes(data["manifest"]))
    )
    return {**data["value"], "placed": {"layer": layer.id, "frames": placed}}
