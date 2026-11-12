"""Source-only generation orchestration, called exclusively by registered Ops."""

import hashlib
import tempfile
from pathlib import Path

from pydantic import ValidationError

from cybersprite.config import reject_tool_configuration
from cybersprite.core import history, sources
from cybersprite.core.canonical import load_project, metadata_bytes, project_path
from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.journal_clock import now
from cybersprite.core.models import Source, SourceFile, SourceModel
from cybersprite.pipeline.decode import decode_raster

from .contracts import GeneratedImage
from .licenses import all_models, fingerprint, identities, require_license
from .models import term_badges
from .registry import BackendRegistry


def accept_license(name, **_kwargs):
    registry = BackendRegistry()
    if name.startswith("comfyui:"):
        backend, alias = registry.get("comfyui"), name.removeprefix("comfyui:")
    elif name in registry.settings.generators.diffusers.models:
        backend, alias = registry.get("diffusers"), name
    elif name.startswith("command:"):
        backend, alias = registry.get(name), None
    elif name in registry.settings.generators.command:
        backend, alias = registry.get("command:" + name), name
    else:
        raise invalid("Unknown configured model alias.", model=name)
    model = backend.selected_model(alias)
    require_license(model, accept=True)
    return {"accepted": identities(model)}


def _select(backend, request):
    if hasattr(backend, "checked"):
        return backend.checked(request)[0]
    models = sorted(backend.list_models(), key=lambda m: m.id)
    selected = (
        next((m for m in models if m.id == request.model), None)
        if request.model
        else (models[0] if models else None)
    )
    if selected is None:
        raise invalid("Select a model advertised by the configured generator.")
    model = selected.model_copy(deep=True)
    for info in all_models(model):
        info.sha256 = fingerprint(info.local_path)
    require_license(model, accept=request.accept_model_license)
    try:
        backend.params_schema.model_validate(request.params)
    except ValidationError as error:
        raise invalid("Invalid plugin generation parameters.") from error
    return model


def generate_top(project, request, tx, actor):
    if tx.dry_run or tx.expect_revision is not None:
        raise invalid(
            "Generation only writes sources; dry_run and expect_revision are unsupported."
        )
    reject_tool_configuration(request.params)
    root = project_path(project).parent.resolve()
    with history.ProjectLock(root, actor):
        try:
            return _generate(root, request, tx, actor)
        except OSError as error:
            raise CyberSpriteError(
                "E_IO",
                f"Cannot save generated sources: {error}",
                "Check model and source directory permissions, then retry.",
            ) from error


def _generate(root, request, tx, actor):
    revision = load_project(root).revision if project_path(root).exists() else 0
    manifest = sources.read_manifest(root)
    signature = hashlib.sha256(
        metadata_bytes(request.model_dump(exclude={"accept_model_license"}))
    ).hexdigest()
    if tx.idempotency_key:
        previous = [
            s
            for s in manifest.sources
            if s.params.get("_generation", {}).get("key") == tx.idempotency_key
        ]
        if previous:
            if any(s.params["_generation"]["request_sha256"] != signature for s in previous):
                raise invalid("Generation idempotency key was used with different arguments.")
            for source in previous:
                for file in source.files:
                    path = sources.source_path(root, file.path)
                    if not path.is_file() or fingerprint(path) != file.sha256:
                        raise CyberSpriteError(
                            "E_IO",
                            "Replayed generation source is missing or changed.",
                            "Restore its original file before retrying this key.",
                        )
                workflow = source.params.get("workflow")
                if workflow:
                    path = sources.source_path(root, workflow["path"])
                    if not path.is_file() or fingerprint(path) != workflow["sha256"]:
                        raise CyberSpriteError(
                            "E_IO",
                            "Replayed generation workflow is missing or changed.",
                            "Restore workflow.json before retrying this key.",
                        )
            return envelope(root, revision, previous)
    backend = BackendRegistry().get(request.backend)
    model = _select(backend, request)
    availability = backend.availability()
    if not availability.available:
        raise CyberSpriteError(
            "E_BACKEND_UNAVAILABLE",
            availability.reason,
            "Use gen backends and repair the named backend configuration.",
        )
    # Backend files are isolated until every result and provenance record has been checked.
    source_root = sources.source_path(root, "staging").parent
    source_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".generate-", dir=source_root) as temporary:
        directory = Path(temporary).resolve()
        try:
            generated = backend.generate(request, directory, lambda _fraction, _message: None)
            images = [GeneratedImage.model_validate(i) for i in generated]
        except CyberSpriteError:
            raise
        except Exception as error:
            raise CyberSpriteError(
                "E_GENERATION_FAILED",
                f"Generator failed: {error}",
                "Repair the selected backend and retry.",
            ) from error
        if len(images) != request.count:
            raise CyberSpriteError(
                "E_GENERATION_FAILED",
                "Backend returned the wrong image count.",
                "Configure the backend to honor count.",
            )
        captured = []
        snapshot_dir = directory / "_captured"
        snapshot_dir.mkdir()
        for index, image in enumerate(images):
            path = image.path.resolve()
            if not path.is_relative_to(directory) or not path.is_file():
                raise CyberSpriteError(
                    "E_PATH_NOT_ALLOWED",
                    "Generated file escapes output directory.",
                    "Configure the backend to write files under out_dir.",
                )
            if identities(image.model) != identities(model):
                raise CyberSpriteError(
                    "E_GENERATION_FAILED",
                    "Backend changed the accepted model identity.",
                    "Return provenance for the configured, accepted model.",
                )
            data = path.read_bytes()
            snapshot = snapshot_dir / f"{index:04d}{path.suffix.lower()}"
            history.atomic_write(snapshot, data)
            try:
                frames, _ = decode_raster(snapshot)
            except Exception as error:
                raise CyberSpriteError(
                    "E_GENERATION_FAILED",
                    "Backend output is not a readable raster.",
                    "Configure the backend to write valid PNG or raster files.",
                ) from error
            if len(frames) != 1 or frames[0].shape[:2] != (request.height, request.width):
                raise CyberSpriteError(
                    "E_GENERATION_FAILED",
                    "Generated dimensions or frame count differ.",
                    "Make the backend honor width and height and output still images.",
                )
            captured.append((image, data, path.suffix.lower()))
        # Detect weights changed while generation was running before accepting their provenance.
        for info in all_models(model):
            if fingerprint(info.local_path) != info.sha256:
                raise CyberSpriteError(
                    "E_GENERATION_FAILED",
                    "Model files changed during generation.",
                    "Keep model and adapter files unchanged while generating.",
                )
        new_sources, writes = [], []
        for image, data, suffix in captured:
            while sources.source_path(root, f"SRC{manifest.next_id}").exists():
                manifest.next_id += 1
            source_id = f"SRC{manifest.next_id}"
            manifest.next_id += 1
            relative = f"source/{source_id}/original{suffix}"
            file = SourceFile(
                path=relative,
                sha256=hashlib.sha256(data).hexdigest(),
                width=request.width,
                height=request.height,
                bytes=len(data),
            )
            stamp = now()
            params = {
                **image.params,
                "width": request.width,
                "height": request.height,
                "adapters": [
                    {"id": a.id, "license": a.license, "sha256": a.sha256} for a in model.adapters
                ],
                "use": request.use,
                "model_registry": model.model_dump(),
                "_generation": {
                    "key": tx.idempotency_key,
                    "request_sha256": signature,
                    "actor": actor,
                },
            }
            if image.workflow is not None:
                workflow_data = metadata_bytes(image.workflow)
                workflow_path = f"source/{source_id}/workflow.json"
                params["workflow"] = {
                    "path": workflow_path,
                    "sha256": hashlib.sha256(workflow_data).hexdigest(),
                }
                writes.append((sources.source_path(root, workflow_path), workflow_data))
            source = Source(
                id=source_id,
                kind="generated",
                files=[file],
                provider=backend.name,
                model=SourceModel(
                    id=model.id,
                    license=model.license,
                    sha256=model.sha256,
                    adapters=[{"id": a.id, "license": a.license} for a in model.adapters],
                ),
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                seed=image.seed,
                params=params,
                license=(backend.command.license if hasattr(backend, "command") else model.license),
                rights_note=request.rights_note,
                url=model.source_url,
                created_at=stamp,
                imported_at=stamp,
                pipeline=None,
                placements=[],
            )
            new_sources.append(source)
            writes.append((sources.source_path(root, relative), data))
        for path, data in writes:
            history.atomic_write(path, data)
        manifest.sources.extend(new_sources)
        sources.save_manifest(root, manifest)
    return envelope(root, revision, new_sources)


def envelope(root, revision, stored):
    terms = [
        entry for source in stored for entry in term_badges(source.params.get("model_registry"))
    ]
    warnings = [
        {"code": "W_MODEL_TERMS", **entry}
        for entry in terms
        if entry["commercial_use"] != "yes" or entry["badge"] != "commercial OK"
    ]
    return {
        "ok": True,
        "op": "generate_image",
        "project": root.as_posix(),
        "revision": revision,
        "result": {
            "sources": [s.id for s in stored],
            "files": [f.path for s in stored for f in s.files],
            "use": stored[0].params.get("use", "canvas") if stored else "canvas",
            "model_terms": terms,
            "message": " ".join(entry["message"] for entry in terms),
        },
        "warnings": warnings,
    }
