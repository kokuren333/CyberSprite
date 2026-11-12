"""Creation only; existing project mutations are reserved for the M2 Op registry."""

from pathlib import Path

from .canonical import dumps_project, project_path
from .errors import CyberSpriteError
from .models import Project
from .validation import require_valid

DEFAULT_PALETTE = ["#00000000", "#000000ff", "#ffffffff"]


def new_project(
    *,
    width: int,
    height: int,
    frames: int = 1,
    duration: int = 100,
    name: str = "Untitled",
    palette: list[str] | None = None,
) -> Project:
    for key, value, maximum in (
        ("width", width, 8192),
        ("height", height, 8192),
        ("frames", frames, 4096),
    ):
        if type(value) is not int or value < 1:
            raise CyberSpriteError(
                "E_INVALID_ARGS",
                f"{key} must be a positive integer.",
                "Use a positive integer within the documented limit.",
            )
        if value > maximum:
            raise CyberSpriteError(
                "E_LIMIT_EXCEEDED",
                f"{key} exceeds {maximum}.",
                "Reduce the requested value.",
                {"requested": value, "limit": maximum},
            )
    if width * height > 16777216:
        raise CyberSpriteError(
            "E_LIMIT_EXCEEDED",
            "Canvas area exceeds 16777216 pixels.",
            "Reduce width or height.",
            {"limit": 16777216, "requested": width * height},
        )
    for key, sequence, maximum in (("name", name, 255), ("palette", palette, 256)):
        if sequence is not None and isinstance(sequence, (str, list)) and len(sequence) > maximum:
            raise CyberSpriteError(
                "E_LIMIT_EXCEEDED",
                f"{key} exceeds {maximum} entries/characters.",
                "Reduce the requested name length or palette size.",
                {"limit": maximum, "requested": len(sequence)},
            )
    project = {
        "name": name,
        "canvas": {"width": width, "height": height},
        "palette": {"colors": palette if palette is not None else DEFAULT_PALETTE},
        "frames": [{"duration_ms": duration} for _ in range(frames)],
        "layers": [{"id": "L1", "name": "Layer 1", "type": "image"}],
        "id_counters": {"layer": 1},
    }
    try:
        return require_valid(project)
    except CyberSpriteError as error:
        raise CyberSpriteError(
            "E_INVALID_ARGS",
            "New project arguments are invalid.",
            "Correct the fields listed in details.issues.",
            error.details,
        ) from error


def create_project(path: str | Path, project: Project) -> Path:
    target = project_path(path)
    data = dumps_project(project)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
    except FileExistsError as error:
        raise CyberSpriteError(
            "E_EXISTS",
            f"Project already exists: {target}",
            "Use a different directory; new never overwrites a project.",
            {"path": target.as_posix()},
        ) from error
    except OSError as error:
        raise CyberSpriteError(
            "E_IO",
            f"Cannot create project: {error}",
            "Check the destination directory and write permissions.",
            {"path": target.as_posix()},
        ) from error
    return target
