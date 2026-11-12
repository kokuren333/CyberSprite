"""Resolve versioned preset data into independent settings dictionaries."""

import copy
import json
from importlib.resources import files

from ._common import require


def _merge(base, extra):
    result = copy.deepcopy(base)
    for key in sorted(extra):
        value = extra[key]
        result[key] = (
            _merge(result.get(key, {}), value) if isinstance(value, dict) else copy.deepcopy(value)
        )
    return result


def resolve_preset(name, *, existing_project=False, overrides=None):
    data = json.loads(files("cybersprite").joinpath("data", "pipeline_defaults.json").read_bytes())
    require(
        name in data["presets"], "Unknown pipeline preset.", "Choose exact, upscaled, ai or photo."
    )
    settings = _merge(data["common"], data["presets"][name])
    mode = settings["palette"].pop("existing_mode", None)
    if existing_project and mode:
        settings["palette"]["mode"] = mode
    settings = _merge(settings, overrides or {})
    return settings, {
        "preset": name,
        "calibration": data["calibration"],
        "overrides": copy.deepcopy(overrides or {}),
    }
