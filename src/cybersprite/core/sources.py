"""Minimal source manifest persistence shared with the future M6 ingest wiring."""

import hashlib
from pathlib import Path

from .canonical import _ordered, json_bytes
from .errors import CyberSpriteError
from .history import atomic_write
from .journal_clock import now
from .models import Source, SourceFile, Sources


def load_sources(root):
    path = Path(root) / "source/manifest.json"
    return Sources.model_validate_json(path.read_bytes()) if path.exists() else Sources()


def record_import(root, file, width, height, *, placements=()):
    """Called only by registered ingest Ops, under the new-project lock."""
    root, file = Path(root), Path(file)
    manifest = load_sources(root)
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
        atomic_write(root / "source/manifest.json", json_bytes(_ordered(manifest)))
    except OSError as error:
        raise CyberSpriteError(
            "E_IO",
            f"Cannot record imported source: {error}",
            "Check source directory permissions and retry in a new project.",
        ) from error
    return source_id
