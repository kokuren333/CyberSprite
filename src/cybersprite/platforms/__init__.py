"""Data-only platform resolution outside the pure core."""

import json
import re
from copy import deepcopy
from importlib.resources import files
from pathlib import Path

from pydantic import ValidationError

from cybersprite.config import config_path, load_config
from cybersprite.core.errors import invalid
from cybersprite.core.platform import Platform, check_integer_data
from cybersprite.plugins import PluginManager, plugin_error


def plugin_definitions(manager=None):
    """Load data definitions through the shared enabled/API-checked boundary."""
    manager = manager or PluginManager(groups=("cybersprite.platforms",))
    result = {}
    for descriptor in manager.descriptors("cybersprite.platforms"):
        try:
            payload = manager.load(descriptor.group, descriptor.name)
            if not isinstance(payload, dict):
                raise ValueError(
                    "Platform entry point must supply a mapping of IDs to definitions."
                )
            for key in sorted(payload):
                if not isinstance(key, str) or not key or not isinstance(payload[key], dict):
                    raise ValueError("Platform IDs must be nonempty strings with JSON definitions.")
                if key in result:
                    raise ValueError(f"Duplicate plugin platform ID: {key}.")
                check_integer_data(payload[key])
                if payload[key].get("id", key) != key:
                    raise ValueError(f"Platform definition ID must match {key}.")
                result[key] = ({**payload[key], "id": key}, "plugin:" + descriptor.name)
        except Exception as error:
            manager.discard(descriptor.group, descriptor.name)
            raise plugin_error(descriptor.name, f"platform registration failed: {error}") from error
    return result


def merge(base, patch):
    if not isinstance(base, dict) or not isinstance(patch, dict):
        return deepcopy(patch)
    result = deepcopy(base)
    for key in sorted(patch):
        result[key] = merge(result.get(key), patch[key])
    return result


def _read(path):
    try:
        data = json.loads(path.read_text("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("The platform definition must be a JSON object.")
        for key in ("id", "extends"):
            if key in data and (not isinstance(data[key], str) or not data[key]):
                raise ValueError(f"Platform {key} must be a nonempty string.")
        check_integer_data(data)
        return data
    except (OSError, ValueError) as error:
        raise invalid(
            "Cannot read platform definition; provide integer-only JSON.",
            path=str(path),
            reason=str(error),
        ) from error


def definitions(platform_file=None):
    result = {}
    builtin = files("cybersprite").joinpath("data/platforms")
    for entry in sorted(builtin.iterdir(), key=lambda p: p.name):
        if entry.name.endswith(".json"):
            data = _read(entry)
            result[data["id"]] = (data, "builtin")
    result.update(plugin_definitions())
    directory = config_path().parent / "platforms"
    for path in (
        sorted(directory.rglob("*.json"), key=lambda p: p.relative_to(directory).as_posix())
        if directory.exists()
        else []
    ):
        data = _read(path)
        key = data.get("id", path.stem)
        result[key] = (data, "user")
    if platform_file:
        data = _read(Path(platform_file))
        result[data.get("id", "custom")] = (data, "file")
    return result


def pointers(data, overrides):
    check_integer_data(overrides or {})
    result = deepcopy(data)
    for pointer, value in sorted((overrides or {}).items()):
        if not pointer.startswith("/") or re.search(r"~(?![01])", pointer):
            raise invalid(
                "Platform overrides require JSON Pointers beginning with /.", pointer=pointer
            )
        parts = [p.replace("~1", "/").replace("~0", "~") for p in pointer[1:].split("/")]
        target = result
        try:
            for part in parts[:-1]:
                if isinstance(target, list) and not re.fullmatch(r"0|[1-9][0-9]*", part):
                    raise KeyError(pointer)
                target = target[int(part)] if isinstance(target, list) else target[part]
            key = int(parts[-1]) if isinstance(target, list) else parts[-1]
            if isinstance(target, list) and (str(key) != parts[-1] or key < 0):
                raise KeyError(pointer)
            if isinstance(target, dict) and key not in target:
                raise KeyError(pointer)
            target[key] = deepcopy(value)
        except (KeyError, IndexError, ValueError, TypeError) as error:
            raise invalid(
                "Platform override points to an unknown location.", pointer=pointer
            ) from error
    return result


def resolve(
    platform=None, *, platform_file=None, overrides=None, width=None, height=None, use_default=False
):
    if platform is None and not platform_file and use_default:
        platform = load_config().defaults.platform
    if platform is None and not platform_file:
        return None
    available = definitions(platform_file)
    if platform is None:
        platform = _read(Path(platform_file)).get("id", "custom")

    def visit(value, stack=()):
        if isinstance(value, str):
            if value in stack:
                raise invalid("Platform inheritance contains a cycle.", cycle=list(stack) + [value])
            if value not in available:
                raise invalid(
                    "Unknown platform; use platforms list or provide platform_file.", platform=value
                )
            data, origin = available[value]
            stack = (*stack, value)
        elif isinstance(value, dict):
            data, origin = value, "custom"
        else:
            raise invalid("Platform must be an ID or JSON object.")
        base = visit(data["extends"], stack) if data.get("extends") else {}
        data = merge(base, {k: v for k, v in data.items() if k != "extends"})
        data["origin"] = origin
        if isinstance(value, dict) and "id" not in value:
            data["id"] = "custom"
            data["preset_version"] = 0
        return data

    try:
        data = visit(platform)
        check_integer_data(data)
        # Null resets an object with defaults to its unconstrained default model.
        for key in ("system", "asset", "defaults", "validation"):
            if data.get(key) is None:
                data.pop(key, None)
        resolved = Platform.model_validate(data)
        if resolved.asset.canvas is None and width is not None and height is not None:
            from cybersprite.core.platform import Canvas

            resolved.asset.canvas = Canvas(w=width, h=height, fixed=False)
        payload = resolved.model_dump(by_alias=True)
        payload = pointers(payload, overrides)
        payload["overrides"] = sorted(set(resolved.overrides) | set(overrides or {}))
        from cybersprite.formats.palette_files import presets

        known_palettes = {entry["name"] for entry in presets()}
        default_palette = payload["defaults"]["palette"]
        if isinstance(default_palette, str) and default_palette not in known_palettes:
            raise invalid(
                "Platform defaults.palette requires a preset ID or literal colors. "
                "Pass palette file paths through new_project.palette.",
                palette=default_palette,
            )
        # Freeze the master RGB table as well as its human-readable preset ID.
        if payload["system"]["color"]["model"] == "master" and not payload["system"]["color"].get(
            "master_colors"
        ):
            from cybersprite.core.pixels import rgba
            from cybersprite.formats.palette_files import read_palette

            name = payload["system"]["color"]["master_palette"]
            if name not in known_palettes:
                raise invalid(
                    "Provide a registered system.color.master_palette ID or explicit "
                    "system.color.master_colors via platform_overrides; no hardware RGB table "
                    "is supplied for this platform.",
                    palette=name,
                )
            payload["system"]["color"]["master_colors"] = sorted(
                {c[:3] for c in map(rgba, read_palette(name)) if c[3] == 255}
            )
            payload["system"]["color"]["master_colors"] = [
                list(c) for c in payload["system"]["color"]["master_colors"]
            ]
        return Platform.model_validate(payload)
    except (ValidationError, ValueError) as error:
        raise invalid(
            "Invalid platform snapshot; correct the indicated fields.", reason=str(error)
        ) from error


def _summary(available, key):
    """Inherited system ID, role and canvas for listings; no validation, cycle-safe."""
    merged, seen = {}, set()
    while key in available and key not in seen:
        seen.add(key)
        data = available[key][0]
        merged = merge({k: v for k, v in data.items() if k != "extends"}, merged)
        key = data.get("extends")
    system = merged.get("system") if isinstance(merged.get("system"), dict) else {}
    asset = merged.get("asset") if isinstance(merged.get("asset"), dict) else {}
    canvas = asset.get("canvas") if isinstance(asset.get("canvas"), dict) else None
    return {
        "system": system.get("id") if isinstance(system.get("id"), str) else None,
        "role": asset.get("role") if isinstance(asset.get("role"), str) else None,
        "canvas": (
            {"w": canvas["w"], "h": canvas["h"], "fixed": bool(canvas.get("fixed", False))}
            if canvas and isinstance(canvas.get("w"), int) and isinstance(canvas.get("h"), int)
            else None
        ),
    }


def list_platforms():
    available = definitions()
    return [
        {
            "id": key,
            "title": data.get("title", key),
            "origin": origin,
            **_summary(available, key),
        }
        for key, (data, origin) in sorted(available.items())
    ]
