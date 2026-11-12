"""Configured public plugin API; the core metadata loader has no outward dependencies."""

from cybersprite.core.plugin_loader import (
    GROUPS,
    Descriptor,
    PluginLoader,
    as_items,
    discover,
    plugin_error,
)

__all__ = ["GROUPS", "Descriptor", "PluginManager", "as_items", "discover", "plugin_error"]


class PluginManager(PluginLoader):
    def __init__(self, settings=None, *, groups=GROUPS, entry_points=None):
        if settings is None:
            from cybersprite.config import load_config

            settings = load_config()
        self.settings = settings
        super().__init__(plugin_settings=settings.plugins, groups=groups, entry_points=entry_points)
