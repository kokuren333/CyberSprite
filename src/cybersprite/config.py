"""Validated user-owned settings. Tool arguments never supply configuration."""

import string
import sys as sys
import tomllib
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

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
    display_name: str = ""
    kind: Literal["diffusers-dir", "checkpoint", "lora", "vae", "controlnet"] = "checkpoint"
    base_model: str = "unknown"
    license_url: str = ""
    commercial_use: Literal["yes", "no", "unknown"] = "unknown"
    note: str = ""
    sha256: str = ""
    registered_at: str = ""


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

    @model_validator(mode="after")
    def valid_bases(self):
        for alias in sorted(self.models):
            visited = {alias}
            base = self.models[alias].base_model
            while base != "unknown":
                if base not in self.models or base in visited:
                    raise ValueError(
                        f"Model {alias!r} needs a registered, non-cyclic base_model or unknown."
                    )
                visited.add(base)
                base = self.models[base].base_model
            for adapter in self.models[alias].adapters:
                if adapter.base_model != "unknown" and adapter.base_model not in self.models:
                    raise ValueError(
                        f"Adapter of {alias!r} needs a registered base_model or unknown."
                    )
        return self


BindKey = Literal[
    "prompt", "negative_prompt", "seed", "width", "height", "steps", "cfg", "checkpoint", "lora"
]


class ComfyWorkflow(SettingsModel):
    file: Annotated[str, Field(min_length=1)]
    license: Annotated[str, Field(min_length=1)]
    commercial_use: Literal["yes", "no", "unknown"]
    bind: dict[BindKey, list[str]] = Field(default_factory=dict)

    @field_validator("bind")
    @classmethod
    def input_paths_only(cls, bindings):
        paths = []
        for key in sorted(bindings):
            path = bindings[key]
            if len(path) != 3 or path[1] != "inputs" or not path[0] or not path[2]:
                raise ValueError(f"Binding {key!r} must be [node_id, 'inputs', key].")
            if path in paths:
                raise ValueError("Each workflow input may be bound only once.")
            paths.append(path)
        return bindings


class ComfySettings(SettingsModel):
    url: str = "http://127.0.0.1:8188"
    timeout_seconds: Annotated[int, Field(ge=1, le=86400)] = 600
    request_timeout_seconds: Annotated[int, Field(ge=1, le=60)] = 10
    poll_interval_ms: Annotated[int, Field(ge=1, le=60000)] = 500
    workflows: dict[str, ComfyWorkflow] = Field(default_factory=dict)

    @field_validator("url")
    @classmethod
    def http_server_only(cls, value):
        from urllib.parse import urlsplit

        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port == 0
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "ComfyUI URL must be an HTTP(S) server URL without credentials, query or fragment."
            )
        return value.rstrip("/")


class Generators(SettingsModel):
    command: dict[str, CommandBackend] = Field(default_factory=dict)
    diffusers: DiffusersSettings = Field(default_factory=DiffusersSettings)
    comfyui: ComfySettings = Field(default_factory=ComfySettings)


class GuiSettings(SettingsModel):
    port: Annotated[int, Field(ge=0, le=65535)] = 0
    open_browser: bool = True
    language: Literal["en", "ja"] = "ja"


class Defaults(SettingsModel):
    platform: str | None = None


class UserConfig(SettingsModel):
    defaults: Defaults = Field(default_factory=Defaults)
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
