"""Manual reference images: register a local file or GUI upload with provenance.

References are images someone found and saved by hand (a browser, a book scan,
the user's own notes) to *measure*, never to trace or place (SPEC §3.6). The
bytes stay in the project's git-ignored ``.cybersprite/references/<id>/``;
``source/manifest.json`` records only the ID, SHA-256, size, who placed it and
the rights note, so a published project carries no third-party pixels.

Every surface uses this one Op: the CLI (``source reference``), MCP
(``register_reference``) and the GUI (Sources tab, ``op.apply``). The surface
decides ``placed_by``: the GUI is always ``human-gui``, MCP is always
``agent``, and the CLI defaults to ``human-cli`` unless ``--placed-by agent``.
"""

import base64
import binascii
from contextlib import nullcontext
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from cybersprite.core import history, sources
from cybersprite.core.canonical import load_project, project_path
from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.journal_clock import now
from cybersprite.core.limits import REFERENCE_BYTES, DecodeBudget
from cybersprite.core.models import Model, Source, SourceFile

from .common import fail

PlacedBy = Literal["human-gui", "human-cli", "agent"]
# Image signatures accepted by decode_design, mapped to the stored suffix.
SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"\xff\xd8\xff", ".jpg"),
    (b"BM", ".bmp"),
)
# base64 length of REFERENCE_BYTES, rounded up to whole quads.
DATA_CHARS = (REFERENCE_BYTES + 2) // 3 * 4


class RegisterReferenceArgs(Model):
    file: str | None = Field(
        None,
        description="Local image file to register as a measuring reference (CLI and MCP). "
        "Give exactly one of file or data.",
        json_schema_extra={"x-cybersprite-path": "input"},
    )
    data: Annotated[str, Field(max_length=DATA_CHARS)] | None = Field(
        None,
        description="Base64 image bytes for uploads (the GUI's file picker). "
        "Give exactly one of file or data; at most 5 MiB decoded.",
    )
    license: Annotated[str, Field(min_length=1, max_length=200)] = Field(
        "unknown", description="Usage terms of the image; use unknown when unknown."
    )
    rights_note: Annotated[str, Field(min_length=1, max_length=2000)] = Field(
        description="Who owns the image and how it may be used, for example "
        "'third-party game sprite, measure only'. Do not write titles or URLs "
        "if the project may be published."
    )
    placed_by: PlacedBy | None = Field(
        None,
        description="Who chose this image. Set by the surface: GUI uploads are human-gui "
        "and MCP calls are agent; the CLI defaults to human-cli and accepts agent.",
    )


class RegisterReferenceResult(Model):
    source: str | None = Field(description="Reference source ID, or null for dry runs.")
    files: list[str] = Field(description="Project-relative stored file paths.")
    sha256: str = Field(description="SHA-256 of the registered bytes.")
    width: int
    height: int
    placed_by: PlacedBy
    duplicate: bool = Field(
        description="True when the same bytes were already registered; no file was written."
    )


def surface_placed_by(actor, requested):
    """The surface, not the caller, decides human versus agent placement."""
    actor = actor or ""
    if actor == "gui" or actor.startswith("gui:"):
        forced, allowed = "human-gui", {None, "human-gui"}
    elif actor.startswith("agent:"):
        forced, allowed = "agent", {None, "agent"}
    else:
        forced, allowed = requested or "human-cli", {None, "human-cli", "agent"}
    if requested not in allowed:
        raise invalid(
            "placed_by is decided by the calling surface.",
            requested=requested,
            allowed=sorted(value for value in allowed if value),
        )
    return forced


def _too_large(size):
    raise CyberSpriteError(
        "E_LIMIT_EXCEEDED",
        "Reference image exceeds the 5 MiB file limit.",
        "Crop the part you want to measure or save it as PNG, then register that file.",
        {"limit_name": "reference_bytes", "requested": size, "limit": REFERENCE_BYTES},
    )


def _read(args):
    if (args.file is None) == (args.data is None):
        raise invalid("Specify exactly one of file or data.")
    if args.file is not None:
        path = Path(args.file)
        try:
            size = path.stat().st_size
            if size > REFERENCE_BYTES:
                _too_large(size)
            raw = path.read_bytes()
        except OSError as error:
            raise CyberSpriteError(
                "E_IO",
                f"Cannot read reference image: {error}",
                "Check the file path; the CLI resolves it from the working directory.",
            ) from error
    else:
        try:
            raw = base64.b64decode(args.data, validate=True)
        except (binascii.Error, ValueError) as error:
            raise invalid("data must be standard base64 image bytes.") from error
    if len(raw) > REFERENCE_BYTES:
        _too_large(len(raw))
    suffix = next((suffix for magic, suffix in SIGNATURES if raw.startswith(magic)), None)
    if suffix is None and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        suffix = ".webp"
    if suffix is None:
        raise CyberSpriteError(
            "E_IO",
            "Reference image must be a PNG, GIF, JPEG, BMP, or WebP file.",
            "Save the image from the browser in one of these formats and retry.",
        )
    from cybersprite.formats.design_sources import decode_design

    image = decode_design(raw, budget=DecodeBudget())
    return raw, suffix, int(image.shape[1]), int(image.shape[0])


def register_reference_top(path, args, tx, actor):
    """Source-manifest-only registration under the project lock; never writes project.json."""
    root = project_path(path).parent
    if not project_path(root).exists():
        load_project(root)  # Raises the standard E_PROJECT_NOT_FOUND.
    placed_by = surface_placed_by(actor, args.placed_by)
    raw, suffix, width, height = _read(args)
    digest = sha256(raw).hexdigest()
    try:
        from cybersprite.core.execution import save_context

        with (
            nullcontext() if tx.dry_run else history.project_lock(root, actor) as lock,
            save_context(root, lock=lock, durable=not tx.dry_run),
        ):
            revision = load_project(root).revision
            if tx.expect_revision is not None and tx.expect_revision != revision:
                fail(
                    "E_REVISION_CONFLICT",
                    "Reference registration revision does not match.",
                    current_revision=revision,
                )
            manifest = sources.read_manifest(root)
            existing = next(
                (
                    s
                    for s in manifest.sources
                    if s.use == "reference" and any(f.sha256 == digest for f in s.files)
                ),
                None,
            )
            if existing is not None:
                # Content-addressed: registering the same bytes again is a no-op.
                result = {
                    "source": existing.id,
                    "files": [f.path for f in existing.files],
                    "sha256": digest,
                    "width": existing.files[0].width,
                    "height": existing.files[0].height,
                    "placed_by": existing.placed_by or placed_by,
                    "duplicate": True,
                }
            else:
                source_id = f"SRC{manifest.next_id}"
                while (
                    sources.source_path(root, source_id).exists()
                    or (root / sources.REFERENCE_DIR / source_id).exists()
                ):
                    manifest.next_id += 1
                    source_id = f"SRC{manifest.next_id}"
                relative = f"{sources.REFERENCE_DIR}/{source_id}/reference_0000{suffix}"
                result = {
                    "source": None if tx.dry_run else source_id,
                    "files": [] if tx.dry_run else [relative],
                    "sha256": digest,
                    "width": width,
                    "height": height,
                    "placed_by": placed_by,
                    "duplicate": False,
                }
                if not tx.dry_run:
                    stamp = now()
                    manifest.sources.append(
                        Source(
                            id=source_id,
                            kind="imported",
                            use="reference",
                            origin="manual",
                            placed_by=placed_by,
                            files=[
                                SourceFile(
                                    path=relative,
                                    sha256=digest,
                                    width=width,
                                    height=height,
                                    bytes=len(raw),
                                )
                            ],
                            provider="user",
                            model=None,
                            prompt="",
                            negative_prompt="",
                            seed=None,
                            params={},
                            license=args.license,
                            rights_note=args.rights_note,
                            url="",
                            created_at=stamp,
                            imported_at=stamp,
                            pipeline=None,
                            placements=[],
                        )
                    )
                    manifest.next_id += 1
                    history.atomic_write(sources.stored_path(root, relative), raw)
                    sources.save_manifest(root, manifest)
    except OSError as error:
        raise CyberSpriteError(
            "E_IO",
            f"Cannot register reference image: {error}",
            "Check the project directory permissions and retry.",
        ) from error
    return {
        "ok": True,
        "op": "register_reference",
        "project": root.as_posix(),
        "revision": revision,
        "dry_run": tx.dry_run,
        "replayed": False,
        "result": result,
        "warnings": [],
    }
