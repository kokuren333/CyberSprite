"""Validated user-owned settings. Tool arguments never supply configuration."""

import string
import sys as sys
import tomllib
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from cybersprite.core.errors import invalid
from cybersprite.core.plugin_settings import PluginSettings
from cybersprite.core.plugin_settings import config_path as shared_config_path


class SettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ModelLocation(SettingsModel):
    id: str | None = None
    local_path: str | None = None
    license: Annotated[str, Field(min_length=1)]
    source_url: str = ""


class GenerationModel(ModelLocation):
    adapters: list[ModelLocation] = Field(default_factory=list)


class CommandBackend(SettingsModel):
    program: Annotated[str, Field(min_length=1)]
    args: list[str]
    license: Annotated[str, Field(min_length=1)]
    model: GenerationModel | None = None
    timeout_seconds: Annotated[int, Field(ge=1)] = 600

    @field_validator("args")
    @classmethod
    def safe_placeholders(cls, args):
        allowed = {"prompt", "negative_prompt", "width", "height", "seed", "out", "count"}
        for arg in args:
            for _, field, spec, conversion in string.Formatter().parse(arg):
                if field is not None and (field not in allowed or spec or conversion):
                    raise ValueError("Only documented generation placeholders are allowed.")
        return args


class DiffusersSettings(SettingsModel):
    models: dict[str, GenerationModel] = Field(default_factory=dict)


class Generators(SettingsModel):
    command: dict[str, CommandBackend] = Field(default_factory=dict)
    diffusers: DiffusersSettings = Field(default_factory=DiffusersSettings)


class GuiSettings(SettingsModel):
    port: Annotated[int, Field(ge=0, le=65535)] = 0
    open_browser: bool = True
    language: Literal["en", "ja"] = "ja"


class UserConfig(SettingsModel):
    generators: Generators = Field(default_factory=Generators)
    gui: GuiSettings = Field(default_factory=GuiSettings)
    plugins: PluginSettings = Field(default_factory=PluginSettings)


def config_path() -> Path:
    return shared_config_path()


def load_config() -> UserConfig:
    path = config_path()
    try:
        data = tomllib.loads(path.read_text("utf-8")) if path.exists() else {}
        return UserConfig.model_validate(data)
    except ValidationError as error:
        raise invalid(
            "Invalid user configuration; fix config.toml before retrying.",
            path=path.as_posix(),
            issues=error.errors(include_input=False, include_context=False),
        ) from error
    except tomllib.TOMLDecodeError as error:
        raise invalid(
            "Invalid user configuration; fix config.toml before retrying.",
            path=path.as_posix(),
            reason=str(error),
        ) from error


def reject_tool_configuration(args):
    """Generation parameters select configured resources; they never define programs."""
    forbidden = {
        "program",
        "command",
        "executable",
        "shell",
        "config",
        "plugins",
        "model_id",
        "local_path",
    }
    if isinstance(args, dict):
        for key, value in args.items():
            if key in forbidden:
                raise invalid(
                    f"Define generation setting {key!r} in user config.toml, not tool arguments."
                )
            reject_tool_configuration(value)
    elif isinstance(args, list):
        for value in args:
            reject_tool_configuration(value)
