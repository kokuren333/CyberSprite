"""Metadata-only discovery and selected, API-checked loading of trusted plugins."""

from dataclasses import dataclass
from importlib import metadata
from threading import RLock
from typing import Any

from cybersprite.core.errors import CyberSpriteError

GROUPS = tuple(
    "cybersprite." + name
    for name in (
        "exporters",
        "generators",
        "importers",
        "ops",
        "palettes",
        "pipeline_steps",
        "platforms",
        "validators",
    )
)


def plugin_error(name, message, **details):
    return CyberSpriteError(
        "E_PLUGIN",
        f"Plugin {name!r}: {message}",
        "Repair this plugin, use plugin_api=1, or disable its entry-point name in config.toml.",
        {"plugin": name, **details},
    )


@dataclass(frozen=True)
class Descriptor:
    group: str
    name: str
    distribution: str
    version: str
    license: str
    declared_api: str | None
    entry: Any

    def describe(self):
        return dict(
            name=self.name,
            group=self.group,
            distribution=self.distribution,
            version=self.version,
            license=self.license,
        )


def discover(groups=GROUPS, *, entry_points=None):
    """Read distribution metadata without loading entry-point code."""
    result = []
    enumerate_entries = entry_points or metadata.entry_points
    for group in sorted(groups):
        for entry in enumerate_entries(group=group):
            dist = getattr(entry, "dist", None)
            info = dist.metadata if dist is not None else {}
            classifiers = info.get_all("Classifier", []) if hasattr(info, "get_all") else []
            license = info.get("License-Expression") or info.get("License")
            if not license:
                license = "; ".join(sorted(c for c in classifiers if c.startswith("License ::")))
            result.append(
                Descriptor(
                    group,
                    entry.name,
                    info.get("Name", "unknown"),
                    getattr(dist, "version", "unknown"),
                    license or "unknown",
                    info.get("CyberSprite-Plugin-API"),
                    entry,
                )
            )
    return sorted(result, key=lambda d: (d.group, d.name, d.distribution, d.version))


class PluginManager:
    def __init__(self, settings=None, *, groups=GROUPS, entry_points=None):
        if settings is None:
            from cybersprite.config import load_config

            settings = load_config()
        self.settings = settings
        self.entries = discover(groups, entry_points=entry_points)
        self.loaded = {}
        self.incompatible = set()
        self._lock = RLock()

    def enabled(self, descriptor):
        config = self.settings.plugins
        return descriptor.name in config.enabled and descriptor.name not in config.disabled

    def descriptors(self, group, *, enabled_only=True):
        return [
            d for d in self.entries if d.group == group and (not enabled_only or self.enabled(d))
        ]

    def find(self, group, name):
        found = [d for d in self.entries if d.group == group and d.name == name]
        if len(found) != 1:
            raise plugin_error(
                name,
                "entry point is missing or ambiguous.",
                group=group,
                distributions=[d.distribution for d in found],
            )
        return found[0]

    def load(self, group, name):
        with self._lock:
            return self._load(group, name)

    def _load(self, group, name):
        descriptor = self.find(group, name)
        if not self.enabled(descriptor):
            raise plugin_error(name, "is not enabled in user config.toml.", group=group)
        key = (group, name)
        if key in self.loaded:
            return self.loaded[key]
        if descriptor.declared_api not in (None, "1"):
            self.incompatible.add(key)
            raise plugin_error(
                name,
                "unsupported metadata plugin API.",
                plugin_api=descriptor.declared_api,
                supported=1,
            )
        try:
            target = descriptor.entry.load()
            api = getattr(target, "plugin_api", None)
            if type(api) is not int or api != 1:
                self.incompatible.add(key)
                raise plugin_error(
                    name,
                    "plugin_api must be 1 before calling its factory.",
                    plugin_api=api,
                    supported=1,
                )
            value = target() if callable(target) else target
        except CyberSpriteError:
            raise
        except Exception as error:
            raise plugin_error(name, f"loading failed: {error}", group=group) from error
        self.loaded[key] = value
        return value

    def discard(self, group, name):
        with self._lock:
            self.loaded.pop((group, name), None)

    def listing(self):
        values = {}
        for d in self.entries:
            key = (d.name, d.distribution, d.version)
            item = values.setdefault(
                key,
                dict(
                    name=d.name,
                    distribution=d.distribution,
                    version=d.version,
                    license=d.license,
                    groups=[],
                    enabled=self.enabled(d),
                    state="enabled" if self.enabled(d) else "disabled",
                    api="unchecked",
                    loaded=False,
                ),
            )
            item["groups"].append(d.group)
            if d.declared_api is not None:
                item["api"] = d.declared_api
            if d.declared_api not in (None, "1") or (d.group, d.name) in self.incompatible:
                item["state"] = "incompatible"
            item["loaded"] |= (d.group, d.name) in self.loaded
        return [values[key] for key in sorted(values)]


def as_items(value):
    return list(value) if isinstance(value, (list, tuple)) else [value]
