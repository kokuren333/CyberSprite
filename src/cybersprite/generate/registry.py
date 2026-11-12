"""Lazy entry-point registry; user configuration is the sole plugin authority."""

from importlib.metadata import entry_points

from cybersprite.config import load_config
from cybersprite.core.errors import CyberSpriteError, invalid

from .backends import CommandBackend, DiffusersBackend
from .comfyui import ComfyUIBackend
from .contracts import Availability


class BackendRegistry:
    def __init__(self, settings=None):
        self.settings = settings or load_config()
        self.builtins = {
            "diffusers": DiffusersBackend(self.settings.generators.diffusers),
            "comfyui": ComfyUIBackend(self.settings.generators.comfyui),
        }
        for name in sorted(self.settings.generators.command):
            backend = CommandBackend(name, self.settings.generators.command[name])
            self.builtins[backend.name] = backend
        self.plugins = {}
        for entry in sorted(entry_points(group="cybersprite.generators"), key=lambda e: e.name):
            if entry.name in self.plugins or entry.name in self.builtins:
                raise invalid("Generator names must be unique.", backend=entry.name)
            self.plugins[entry.name] = entry

    def get(self, name):
        if name in self.builtins:
            return self.builtins[name]
        if name not in self.plugins:
            raise invalid(
                "Unknown generation backend.", candidates=sorted([*self.builtins, *self.plugins])
            )
        if name not in self.settings.plugins.enabled:
            raise CyberSpriteError(
                "E_PLUGIN",
                f"Generator plugin {name!r} is not enabled.",
                "Enable the installed plugin in user config.toml.",
            )
        try:
            factory = self.plugins[name].load()
            if getattr(factory, "plugin_api", None) != 1:
                raise ValueError("plugin_api must be 1")
            backend = factory()
            if backend.name != name:
                raise ValueError("backend name must match its entry point")
            return backend
        except Exception as error:
            raise CyberSpriteError(
                "E_PLUGIN",
                f"Cannot load generator {name}: {error}",
                "Repair or disable this generator plugin.",
            ) from error

    def describe(self):
        values = []
        for name in sorted([*self.builtins, *self.plugins]):
            if name in self.plugins:
                reason = (
                    "Plugin is enabled; select it to load and check its runtime."
                    if name in self.settings.plugins.enabled
                    else "Plugin is not enabled in user config.toml."
                )
                available, models, schema = Availability(available=False, reason=reason), [], {}
            else:
                backend = self.builtins[name]
                available = backend.availability()
                models = [m.model_dump() for m in backend.list_models()]
                schema = backend.params_schema.model_json_schema()
            values.append(
                dict(name=name, **available.model_dump(), models=models, params_schema=schema)
            )
        return {"backends": values}
