"""Export policy, deterministic selectors, and mandatory read-after-write verification."""

import hashlib
import os
import re
import struct
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from string import Formatter

import numpy as np

from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.hashing import pixel_sha256
from cybersprite.core.quality import report
from cybersprite.core.references import resolve_tag

from .png import environment_fingerprint

_POLICY = ContextVar("cybersprite_export_policy", default=None)
PLACEHOLDERS = {"name", "frame", "frame1", "layer", "tag", "tagframe", "slice"}


def fail(code, message, **details):
    hint = (
        "Run validate, fix the error-level issues, then retry; "
        "use allow_invalid=true only for an intentional override."
        if code == "E_VALIDATION_FAILED"
        else "Correct the indicated export option and retry."
    )
    raise CyberSpriteError(code, message, hint, details)


@contextmanager
def export_policy(root, allow_dirs=()):
    """Surfaces can bind their root/allow-dir policy once around an Op execution."""
    root = Path(root).resolve()
    token = _POLICY.set((root, [root, *(Path(p).resolve() for p in allow_dirs)]))
    try:
        yield
    finally:
        _POLICY.reset(token)


def output_path(value):
    root, allowed = _POLICY.get() or (Path.cwd().resolve(), [Path.cwd().resolve()])
    path = (root / value).resolve()
    if not any(path.is_relative_to(directory) for directory in allowed):
        raise CyberSpriteError(
            "E_PATH_NOT_ALLOWED",
            "Export path is outside allowed directories.",
            f"For CLI exports, run from a parent directory or use a path under {root.as_posix()}. "
            "For MCP, use its configured root or an allow-dir.",
            {"path": path.as_posix(), "allowed": [p.as_posix() for p in allowed]},
        )
    return path


def display_path(path):
    root = (_POLICY.get() or (Path.cwd().resolve(), []))[0]
    # Allowed directories outside root use a relative path containing '..'.
    import os

    try:
        return Path(os.path.relpath(path, root)).as_posix()
    except ValueError:
        return path.as_posix()


def frame_sequence(p, value=None):
    if value is None or value == "all":
        result = list(range(len(p.frames)))
    elif type(value) is int:
        result = [value]
    elif isinstance(value, list):
        result = list(value)
    elif isinstance(value, str):
        match = re.fullmatch(r"(\d+)-(\d+)", value)
        if match:
            start, end = int(match[1]), int(match[2])
            if start > end:
                raise invalid("Frame range start must not exceed its end.")
            if end >= len(p.frames):
                fail(
                    "E_FRAME_OUT_OF_RANGE",
                    "Export range end is outside the project.",
                    frame=end,
                    frame_count=len(p.frames),
                )
            result = list(range(start, end + 1))
        else:
            tag = resolve_tag(p, value.removeprefix("tag:"))
            result = list(range(tag.from_, tag.to + 1))
    else:
        raise invalid("frames must be a range, index list, or tag name.")
    if not result:
        raise invalid("Export requires at least one frame.")
    for index in result:
        if type(index) is not int or not 0 <= index < len(p.frames):
            fail(
                "E_FRAME_OUT_OF_RANGE",
                "Export frame is outside the project.",
                frame=index,
                frame_count=len(p.frames),
            )
    return result


def animation_sequence(p, frames=None, tag=None, loop=0, *, scale=1):
    from cybersprite.core.limits import FRAME_COUNT, check_limit, output_bytes

    if tag is not None and frames is not None:
        raise invalid("Specify either tag or frames for animation export.")
    if tag is None:
        result = frame_sequence(p, frames)
    else:
        t = resolve_tag(p, tag)
        count = t.to - t.from_ + 1
        if count > 1:
            count = (
                count * max(t.repeat, 1)
                if t.direction in ("forward", "reverse")
                else count + (count - 1) * ((t.repeat or 2) - 1)
            )
        # Check before repetition allocates the playback list, conservatively
        # including a possible duplicate closing frame.
        output_bytes(p.canvas.width * scale, p.canvas.height * scale, count)
        check_limit(
            "output_frames",
            count,
            FRAME_COUNT,
            "Reduce tag repeat or export a shorter frame range.",
        )
        forward = list(range(t.from_, t.to + 1))
        if len(forward) == 1:
            result = forward
        elif t.direction in ("forward", "reverse"):
            result = (forward if t.direction == "forward" else forward[::-1]) * max(t.repeat, 1)
        else:
            first = forward if t.direction == "pingpong" else forward[::-1]
            result = list(first)
            for leg in range(1, t.repeat or 2):
                result.extend((first if leg % 2 == 0 else first[::-1])[1:])
    if loop == 0 and len(result) > 2 and result[-1] == result[0]:
        result.pop()
    output_bytes(p.canvas.width * scale, p.canvas.height * scale, len(result))
    check_limit(
        "output_frames", len(result), FRAME_COUNT, "Export at most 4096 playback frames per call."
    )
    return result


def format_name(pattern, **values):
    try:
        for _literal, field, spec, conversion in Formatter().parse(pattern):
            if field is not None and (field not in PLACEHOLDERS or conversion is not None):
                raise ValueError("Unknown placeholder or conversion.")
            if spec and (
                field not in {"frame", "frame1", "tagframe"}
                or re.fullmatch(r"0?[1-9][0-9]?(?:d)?", spec) is None
            ):
                raise ValueError("Only integer frame widths from 1 through 99 are supported.")
        return pattern.format(**values)
    except (ValueError, KeyError, IndexError) as error:
        raise invalid(
            "Invalid export filename/item_name format.", pattern=pattern, reason=str(error)
        ) from error


def name_values(p, frame, *, layer=None, tag=None, slice=None):
    t = tag or next((t for t in p.tags if t.from_ <= frame <= t.to), None)
    return dict(
        name=p.name,
        frame=frame,
        frame1=frame + 1,
        layer=layer.name if layer else "",
        tag=t.name if t else "",
        tagframe=frame - t.from_ if t else frame,
        slice=slice.name if slice else "",
    )


def gate(p, args, root=None):
    validation = report(p, root=root)
    warnings = [dict(issue) for issue in validation["issues"] if issue["level"] == "warning"]
    if not validation["ok"]:
        if not args.allow_invalid:
            fail(
                "E_VALIDATION_FAILED",
                "Project validation failed; export was refused.",
                issues=[i for i in validation["issues"] if i["level"] == "error"],
            )
        warnings.append(
            {"code": "W_EXPORT_INVALID", "message": "Exported despite validation errors."}
        )
    return {
        "files": [],
        "fingerprint": environment_fingerprint(),
        "warnings": warnings,
        "validation_ok": validation["ok"],
        "verified": True,
    }


def _folded_parts(path):
    # Conservatively reserve case aliases even on a case-sensitive filesystem.
    return tuple(part.casefold() for part in path.parts)


def protect_project_output(path, project_root=None, *, original=None):
    """Reject final export destinations that alias project-owned files or directories."""
    roots = [] if project_root is None else [Path(project_root).absolute()]
    for parent in path.parents:
        if (parent / "project.json").is_file() and parent not in roots:
            roots.append(parent)
    for root in roots:
        canonical = root / "project.json"
        reserved = [canonical, root / "source", root / ".cybersprite"]
        candidates = [path, original or path]
        protected = any(
            _folded_parts(candidate)[: len(base.parts)] == _folded_parts(base)
            for candidate in candidates
            for item in reserved
            for base in (item, item.resolve())
        )
        if not protected and path.exists():
            # samefile catches hard links, including aliases outside the project.
            protected = canonical.exists() and os.path.samefile(path, canonical)
            if not protected and path.stat().st_nlink > 1:
                for directory in reserved[1:]:
                    if directory.is_dir():
                        for folder, dirs, files in os.walk(directory, followlinks=False):
                            dirs.sort()
                            if any(
                                os.path.samefile(path, Path(folder) / name)
                                for name in sorted(files)
                            ):
                                protected = True
                                break
                    if protected:
                        break
        if protected:
            raise CyberSpriteError(
                "E_PATH_NOT_ALLOWED",
                "Export destination is reserved for the project, its sources, or its history.",
                "Choose a path outside the project directory or under an allowed export "
                "directory outside project.json, source/, and .cybersprite/.",
                {
                    "reason": "protected_project_file",
                    "path": path.as_posix(),
                    "project": root.resolve().as_posix(),
                },
            )


def preflight(paths, overwrite, *, project_root=None):
    resolved = [output_path(path) for path in paths]
    policy_root = (_POLICY.get() or (Path.cwd(), []))[0]
    for value, path in zip(paths, resolved, strict=True):
        protect_project_output(
            path, project_root, original=Path(os.path.abspath(policy_root / value))
        )
    if len(set(resolved)) != len(resolved):
        raise invalid("Export filenames collide; use distinct frame/split placeholders.")
    for path in resolved:
        if path.exists() and not overwrite:
            fail("E_EXISTS", "Export destination already exists.", path=display_path(path))
        if path.is_dir():
            fail("E_IO", "Export destination is a directory.", path=display_path(path))
    return resolved


def write_verified(path, data, verify, *, pixels=None, width=0, height=0):
    """Verify bytes read from disk, removing the file on a decoder or comparison failure."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        from cybersprite.core.history import atomic_write

        atomic_write(path, data)
        actual = path.read_bytes()
    except OSError as error:
        fail("E_IO", f"Cannot write/read export: {error}", path=display_path(path))
    try:
        if not verify(actual):
            raise ValueError("Decoded export does not match the expected content.")
    except Exception as error:
        path.unlink(missing_ok=True)
        raise CyberSpriteError(
            "E_INTERNAL",
            f"Export self-verification failed: {error}",
            "Report this export and its options; the failed file was removed.",
            {"path": display_path(path)},
        ) from error
    result = {
        "path": display_path(path),
        "bytes": len(actual),
        "sha256": hashlib.sha256(actual).hexdigest(),
    }
    if pixels is None:
        result["kind"] = "data"
    else:
        height, width = pixels.shape[:2]
        result.update(pixel_sha256=pixel_sha256(pixels), width=width, height=height)
    return result


def rgba_pixels(pixels, palette):
    from cybersprite.core.pixels import rgba

    return (
        pixels if palette is None else np.array([rgba(c) for c in palette], dtype=np.uint8)[pixels]
    )


def sequence_pixel_sha256(images):
    """Single-frame CSPX1 identity, or CSPA1 plus ordered CSPX1 digests for animation."""
    if len(images) == 1:
        return pixel_sha256(images[0])
    payload = b"CSPA1" + struct.pack("<I", len(images))
    return hashlib.sha256(
        payload + b"".join(bytes.fromhex(pixel_sha256(im)) for im in images)
    ).hexdigest()


def bounds(pixels, palette=None):
    ys, xs = np.nonzero(rgba_pixels(pixels, palette)[..., 3])
    if not len(xs):
        return 0, 0, 1, 1, True
    x, y = int(xs.min()), int(ys.min())
    return x, y, int(xs.max()) + 1 - x, int(ys.max()) + 1 - y, False


def slice_bounds(p, reference, frame):
    matches = [s for s in p.slices if s.id == reference or s.name == reference]
    if not matches:
        fail("E_SLICE_NOT_FOUND", "Export slice was not found.", reference=reference)
    if len(matches) != 1:
        fail("E_AMBIGUOUS_REF", "Slice name is ambiguous; use its ID.", reference=reference)
    s = matches[0]
    keys = [k for k in s.keys if k.frame <= frame]
    if not keys:
        raise invalid("Slice has no key at this frame.", slice=s.id, frame=frame)
    key = max(keys, key=lambda k: k.frame)
    return s, {k: getattr(key, k) for k in ("x", "y", "w", "h")}
