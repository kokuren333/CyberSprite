"""Validated source manifests and confined immutable-original paths (§5.10)."""

from pathlib import Path

from pydantic import ValidationError

from .canonical import metadata_bytes
from .errors import CyberSpriteError
from .history import atomic_write
from .models import Sources


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
