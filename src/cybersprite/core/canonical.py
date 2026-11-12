"""Canonical JSON independent of incoming object key ordering."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .errors import CyberSpriteError
from .models import Project, SliceKey, UserData
from .validation import require_valid

SCHEMA_VERSION = 1
MIGRATIONS: dict = {}  # old version -> pure dict migration; filled when a version 2 exists.


def _ordered(value: Any, context: str = "") -> Any:
    if isinstance(value, BaseModel):
        names = list(type(value).model_fields)
        if isinstance(value, SliceKey):
            names = ["frame", "x", "y", "w", "h", "center", "pivot"]
        result = {}
        for name in names:
            item = getattr(value, name)
            if name == "user_data" and (
                item is None
                or (
                    isinstance(item, UserData)
                    and not item.text
                    and item.color is None
                    and not item.properties
                )
            ):
                continue
            key = type(value).model_fields[name].alias or name
            if key == "color" and isinstance(item, str):
                item = item.lower()
            if key in ("colors", "pixels"):
                item = [entry.lower() for entry in item]
            if key == "tiles" and isinstance(item, list) and all(isinstance(x, str) for x in item):
                item = [" ".join(row.split()) for row in item]
            result[key] = _ordered(item, key)
        return result
    if isinstance(value, dict):
        return {
            key: _ordered(value[key])
            for key in sorted(value, key=int if context == "names" else None)
        }
    if isinstance(value, list):
        return [_ordered(item) for item in value]
    return value


def json_bytes(value: Any) -> bytes:
    """Serialize ordered data; all U+0000..001F controls use unicode escapes."""
    # json.dumps handles quotes and backslashes; replace only its short control escapes.
    raw = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
    short = {"b": "0008", "t": "0009", "n": "000a", "f": "000c", "r": "000d"}
    raw = re.sub(
        r'\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4})',
        lambda m: "\\u" + short[m[0][1:]] if m[0][1:] in short else m[0],
        raw,
    )
    return (raw + "\n").encode("utf-8")


def dumps_project(project: Project) -> bytes:
    require_valid(project)
    return json_bytes(_ordered(project))


def loads_project(data: bytes | str) -> Project:
    try:
        raw = json.loads(data)
        if not isinstance(raw, dict):
            raise ValueError("The top level must be an object.")
        version = raw.get("schema_version", SCHEMA_VERSION)
        if type(version) is int and version > SCHEMA_VERSION:
            raise CyberSpriteError(
                "E_SCHEMA_TOO_NEW",
                f"Project schema version {version} is newer than supported.",
                "Upgrade CyberSprite to a version supporting this schema.",
                {"schema_version": version, "supported_version": SCHEMA_VERSION},
            )
        while type(version) is int and version < SCHEMA_VERSION and version in MIGRATIONS:
            raw = MIGRATIONS[version](raw)
            new_version = raw.get("schema_version")
            if type(new_version) is not int or new_version <= version:
                raise ValueError("Schema migration did not advance the version.")
            version = new_version
        return require_valid(raw)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise CyberSpriteError(
            "E_INVALID_PROJECT",
            f"Cannot parse project JSON: {error}",
            "Provide a valid UTF-8 project.json matching the project schema.",
            {"issues": [{"rule": "S-01", "path": "/"}]},
        ) from error


def project_path(path: str | Path) -> Path:
    path = Path(path)
    return path if path.name == "project.json" else path / "project.json"


def load_project(path: str | Path) -> Project:
    path = project_path(path)
    try:
        return loads_project(path.read_bytes())
    except FileNotFoundError as error:
        raise CyberSpriteError(
            "E_PROJECT_NOT_FOUND",
            f"Project file does not exist: {path}",
            "Use --project to specify a project directory or run new first.",
            {"path": path.as_posix()},
        ) from error
    except OSError as error:
        raise CyberSpriteError(
            "E_IO",
            f"Cannot read project: {error}",
            "Check the path and read permissions.",
            {"path": path.as_posix()},
        ) from error
