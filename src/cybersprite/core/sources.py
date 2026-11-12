"""Validated source manifests and confined immutable-original paths (§5.10)."""

import hashlib
from pathlib import Path

from pydantic import ValidationError

from .canonical import metadata_bytes
from .errors import CyberSpriteError
from .history import atomic_write
from .journal_clock import now
from .models import Source, SourceFile, Sources


def manifest_path(root):
    return Path(root) / "source/manifest.json"


def read_manifest(root):
    path = manifest_path(root)
    try:
        return Sources.model_validate_json(path.read_bytes()) if path.exists() else Sources()
    except (OSError, ValidationError) as error:
        raise CyberSpriteError(
            "E_IO",
            f"Cannot read source manifest: {error}",
            "Restore source/manifest.json from a trusted copy.",
        ) from error


def manifest_bytes(manifest):
    return metadata_bytes(manifest)


def save_manifest(root, manifest):
    atomic_write(manifest_path(root), manifest_bytes(manifest))


def find_source(manifest, source_id):
    for source in manifest.sources:
        if source.id == source_id:
            return source
    raise CyberSpriteError(
        "E_SOURCE_NOT_FOUND",
        f"Source {source_id!r} was not found.",
        "Use list_sources and retry with an existing source ID.",
        {"candidates": [source.id for source in manifest.sources]},
    )


def source_path(root, relative):
    base = Path(root).resolve()
    path = Path(relative)
    target = base / path if path.parts and path.parts[0] == "source" else base / "source" / path
    if path.is_absolute() or not target.resolve().is_relative_to(base / "source"):
        raise CyberSpriteError(
            "E_PATH_NOT_ALLOWED",
            "Source path escapes source/.",
            "Use a project-relative path inside source/.",
            {"path": relative},
        )
    return target


def record_import(root, file, width, height, *, placements=()):
    """Called only by registered ingest Ops, under the new-project lock."""
    root, file = Path(root), Path(file)
    manifest = read_manifest(root)
    source_id = f"SRC{manifest.next_id}"
    relative = Path("source") / source_id / file.name
    destination = root / relative
    data = file.read_bytes()
    timestamp = now()
    source = Source(
        id=source_id,
        kind="imported",
        files=[
            SourceFile(
                path=relative.as_posix(),
                sha256=hashlib.sha256(data).hexdigest(),
                width=width,
                height=height,
                bytes=len(data),
            )
        ],
        provider="file",
        model=None,
        prompt="",
        negative_prompt="",
        seed=None,
        params={},
        license="unknown",
        rights_note="",
        url="",
        created_at=timestamp,
        imported_at=timestamp,
        pipeline=None,
        placements=list(placements),
    )
    manifest.sources.append(source)
    manifest.next_id += 1
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(data)
        save_manifest(root, manifest)
    except OSError as error:
        raise CyberSpriteError(
            "E_IO",
            f"Cannot record imported source: {error}",
            "Check source directory permissions and retry in a new project.",
        ) from error
    return source_id


def stage_history(ctx, before_revision, after_revision, restored=None):
    """Stage placement/metric history atomically, retaining immutable source captures."""
    from copy import deepcopy

    from .history import paths, read_journal

    current = read_manifest(ctx.root)
    previous = ctx.previous_source_manifest if ctx.previous_source_manifest is not None else current
    active = ctx.source_manifest if ctx.source_manifest is not None else deepcopy(current)
    folder = paths(ctx.root) / "sources"

    def snapshot(revision):
        return folder / f"r{revision:06d}.json"

    if restored is not None:
        target = snapshot(restored)
        if target.exists():
            saved = Sources.model_validate_json(target.read_bytes())
            records = {source.id: source for source in saved.sources}
            for source in active.sources:
                old = records.get(source.id)
                source.placements = deepcopy(old.placements) if old else []
                source.pipeline = deepcopy(old.pipeline) if old else None
            ctx.side_writes.append((manifest_path(ctx.root), manifest_bytes(active)))
        else:
            # Legacy journals can identify active placements even though their
            # previous conversion metrics were never snapshotted.
            states: dict[int, set[int]] = {}
            revisions: set[int] = set()
            for entry in read_journal(ctx.root):
                revision = entry["revision"]
                if entry["kind"] in ("create", "external"):
                    revisions = {
                        p.revision
                        for s in active.sources
                        for p in s.placements
                        if p.revision <= revision
                    }
                elif entry["kind"] in ("undo", "redo"):
                    prior = (entry.get("result") or {}).get("result", {}).get("restored_revision")
                    revisions = set(states.get(prior, ()))
                elif any(call["op"] == "import_image" for call in entry.get("ops", [])):
                    revisions = revisions | {revision}
                states[revision] = set(revisions)
            allowed = states.get(restored, set())
            for source in active.sources:
                original_count = len(source.placements)
                source.placements = [p for p in source.placements if p.revision in allowed]
                if not source.placements:
                    source.pipeline = None
                elif len(source.placements) != original_count and source.pipeline:
                    source.pipeline.report.pop("grid_score", None)
                    source.pipeline.report["history_status"] = "undone_conversion_metrics"
                    source.pipeline.report["warnings"] = [
                        {
                            "code": "W_SOURCE_HISTORY_UNAVAILABLE",
                            "message": "Legacy conversion metrics were not retained "
                            "for this revision.",
                            "hint": "Reconvert the source to recreate metrics "
                            "for its current placement.",
                        }
                    ]
                    source.pipeline.accepted = True
                    source.pipeline.gates_overridden = []
            ctx.side_writes.append((manifest_path(ctx.root), manifest_bytes(active)))
    if current.sources or active.sources:
        ctx.previous_source_manifest = previous
        ctx.source_manifest = active
        if not snapshot(before_revision).exists():
            ctx.side_writes.append((snapshot(before_revision), manifest_bytes(previous)))
        ctx.side_writes.append((snapshot(after_revision), manifest_bytes(active)))


def retain_history(root):
    """Source sidecars expire with their corresponding project snapshots."""
    from .history import paths, snapshot_path

    for path in sorted((paths(root) / "sources").glob("r*.json")):
        revision = path.stem[1:]
        if revision.isdigit() and not snapshot_path(root, int(revision)).exists():
            path.unlink()
