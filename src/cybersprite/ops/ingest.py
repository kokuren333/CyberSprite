"""Source ingestion, conversion and registered transactional placement."""

from contextlib import nullcontext
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import numpy as np

from cybersprite.core import history, sources
from cybersprite.core.canonical import load_project, metadata_bytes, project_path
from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.journal_clock import now
from cybersprite.core.models import (
    Frame,
    ImageCel,
    ImageLayer,
    Placement,
    Source,
    SourceFile,
    SourcePipeline,
)
from cybersprite.core.pixels import pixels_to_rows
from cybersprite.core.projects import new_project
from cybersprite.core.transactions import transact
from cybersprite.pipeline._common import PipelineError
from cybersprite.pipeline.decode import decode_raster, split_sheet
from cybersprite.pipeline.runner import color_strings, run_pipeline

from .common import fail, image_layer, write_points
from .ingest_args import (
    GetSourceArgs as GetSourceArgs,
)
from .ingest_args import (
    GetSourceResult as GetSourceResult,
)
from .ingest_args import (
    ImportArgs as ImportArgs,
)
from .ingest_args import (
    ImportResult as ImportResult,
)
from .ingest_args import (
    ListSourcesArgs as ListSourcesArgs,
)
from .ingest_args import (
    ListSourcesResult as ListSourcesResult,
)
from .ingest_args import (
    Provenance as Provenance,
)
from .ingest_args import (
    Sheet as Sheet,
)
from .ingest_args import (
    Target as Target,
)
from .previews import transaction_previews
from .queries import source_query as source_query


def decode_files(paths, sheet=None):
    from cybersprite.core.limits import DecodeBudget

    budget = DecodeBudget()
    frames, durations, warnings, dimensions = [], [], [], []
    try:
        for path in paths:
            images, decoded = decode_raster(path, budget=budget)
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


def _capture(root, args, manifest, *, dry_run=False):
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
    provenance = args.provenance
    if provenance is None and args.pipeline_only:
        provenance = Provenance.model_validate({"license": "unknown"})
    if provenance is None or not provenance.license.strip():
        raise invalid("provenance.license is required; use unknown when usage terms are unknown.")
    paths = [Path(p) for p in ([args.files] if isinstance(args.files, str) else args.files)]
    # Decode the captured bytes, never a separately re-opened mutable input.
    source_id = f"SRC{manifest.next_id}"
    directory = Path(root) / "source" / source_id
    while directory.exists():
        manifest.next_id += 1
        source_id = f"SRC{manifest.next_id}"
        directory = Path(root) / "source" / source_id
    if dry_run:
        directory = Path(root) / ".cybersprite/previews/dry"
    directory.mkdir(parents=True, exist_ok=dry_run)
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
            path=(path.resolve().as_posix() if dry_run else path.relative_to(root).as_posix()),
            sha256=sha256(path.read_bytes()).hexdigest(),
            width=size[0],
            height=size[1],
            bytes=path.stat().st_size,
        )
        for path, size in zip(captured, dimensions, strict=True)
    ]
    stamp = "1970-01-01T00:00:00+00:00" if dry_run else now()
    source = Source(
        id=source_id,
        files=files,
        created_at=stamp,
        imported_at=stamp,
        pipeline=None,
        placements=[],
        **provenance.model_dump(),
    )
    manifest.next_id += 1
    manifest.sources.append(source)
    if not dry_run:
        sources.save_manifest(root, manifest)
    return source, frames, durations, warnings


def import_top(registry, path, args, tx, actor):
    try:
        return _import_top(registry, path, args, tx, actor)
    except OSError as error:
        raise CyberSpriteError(
            "E_IO",
            f"Cannot capture or save source: {error}",
            "Check input paths and project directory permissions.",
        ) from error


def _import_top(registry, path, args, tx, actor):
    root = project_path(path).parent
    if args.pipeline_only and not tx.dry_run:
        raise invalid("pipeline_only requires dry_run=true; omit it to commit placement.")
    with nullcontext() if tx.dry_run else history.project_lock(root, actor) as lock:
        existing = load_project(root) if project_path(root).exists() else None
        replayed = (
            history.replay(root, tx.idempotency_key)
            if tx.idempotency_key and not args.pipeline_only
            else None
        )
        if replayed is not None:
            if tx.dry_run:
                replayed.update(dry_run=True, would_commit=False, checked=["idempotency"])
            return replayed
        if tx.expect_revision is not None and tx.expect_revision != (
            existing.revision if existing else 0
        ):
            fail(
                "E_REVISION_CONFLICT",
                "Import revision does not match the current project.",
                current_revision=existing.revision if existing else 0,
            )
        manifest = sources.read_manifest(root)
        previous_manifest = deepcopy(manifest)
        source, images, durations, warnings = _capture(root, args, manifest, dry_run=tx.dry_run)
        directory = root / (".cybersprite/previews/dry" if tx.dry_run else f"source/{source.id}")
        relative = directory.relative_to(root).as_posix()
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
                "path": f"{relative}/pipeline_report.json",
                "grid_score": report["grid"]["grid_score"],
                "warnings": report.get("warnings", []),
                **(
                    {"plugins": report["plugins"], "determinism": report["determinism"]}
                    if report.get("plugins")
                    else {}
                ),
            },
            result_sha256=sha256((directory / "result.png").read_bytes()).hexdigest(),
            accepted=accepted,
            gates_overridden=list(source.pipeline.gates_overridden) if source.pipeline else [],
        )
        if not tx.dry_run:
            sources.save_manifest(root, manifest)
        value = {
            "source": None if tx.dry_run else source.id,
            "accepted": accepted,
            "report_path": f"{relative}/pipeline_report.json",
            "stage_paths": [f"{relative}/{s}" for s in report["stage_paths"]],
            "gates": report["gates"],
            "placed": None,
        }
        report["accepted"] = accepted
        report["gates_overridden"] = failed if accepted else []
        history.atomic_write(directory / "pipeline_report.json", metadata_bytes(report))
        if args.pipeline_only:
            return {
                "ok": True,
                "op": "import_image",
                "project": root.as_posix(),
                "revision": existing.revision if existing else 0,
                "dry_run": True,
                "checked": ["pipeline"],
                "pipeline_accepted": accepted,
                "result": value,
                "warnings": warnings,
            }
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
            result = {
                "ok": True,
                "op": "import_image",
                "project": root.as_posix(),
                "revision": existing.revision if existing else 0,
                "result": value,
                "warnings": warnings,
            }
            if tx.dry_run:
                result.update(dry_run=True, would_commit=False, checked=["pipeline"])
            return result
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
        if tx.dry_run:
            result["checked"] = ["pipeline", "placement", "structure"]
            # Preserve the dry-run result contract; planned changes remain in changed/preview.
            result["result"]["placed"] = None
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
        if data["new_project"]:
            layer = p.layers[0]
            layer.name = name
        else:
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
