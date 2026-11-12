"""Shared configuration location and strict plugin permission data; no surface imports."""

import os
import sys
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .errors import invalid


class PluginSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: list[str] = Field(default_factory=list)
    disabled: list[str] = Field(default_factory=list)


def config_path() -> Path:
    override = os.environ.get("CYBERSPRITE_CONFIG_DIR")
    if override:
        return Path(override).expanduser().resolve() / "config.toml"
    if sys.platform == "win32":
        folder = Path(os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming")))
    else:
        folder = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return folder / "cybersprite/config.toml"


def load_plugin_settings() -> PluginSettings:
    """Standalone registries read the same permission table as configured surfaces."""
    path = config_path()
    try:
        data = tomllib.loads(path.read_text("utf-8")) if path.exists() else {}
        return PluginSettings.model_validate(data.get("plugins", {}))
    except ValidationError as error:
        raise invalid(
            "Invalid plugin configuration; fix config.toml before retrying.",
            path=path.as_posix(),
            issues=error.errors(include_input=False, include_context=False),
        ) from error
    except tomllib.TOMLDecodeError as error:
        raise invalid(
            "Invalid plugin configuration; fix config.toml before retrying.",
            path=path.as_posix(),
            reason=str(error),
        ) from error
