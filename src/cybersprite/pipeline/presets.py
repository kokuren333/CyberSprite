"""Resolve versioned preset data into independent settings dictionaries."""

import copy

from pydantic import ValidationError

from cybersprite.core.errors import invalid

from ._common import require
from .args import PipelineSettings
from .defaults import load_defaults


def _merge(base, extra):
    result = copy.deepcopy(base)
    for key in sorted(extra):
        value = extra[key]
        result[key] = (
            _merge(result.get(key, {}), value) if isinstance(value, dict) else copy.deepcopy(value)
        )
    return result


def resolve_preset(name, *, existing_project=False, overrides=None):
    try:
        overrides = PipelineSettings.model_validate(overrides or {}).model_dump(exclude_unset=True)
    except ValidationError as error:
        raise invalid("Invalid pipeline overrides.", reason=str(error)) from error
    data = load_defaults()
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
