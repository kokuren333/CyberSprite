"""Resolve plugin presets through the same palette reader as bundled presets."""

from cybersprite.core.pixels import rgba

from . import PluginManager, as_items, plugin_error


def palette_presets(builtin_names=(), manager=None):
    manager = manager or PluginManager(groups=("cybersprite.palettes",))
    staged = {}
    for descriptor in manager.descriptors("cybersprite.palettes"):
        try:
            pending = {}
            for item in as_items(manager.load(descriptor.group, descriptor.name)):
                name = item["name"]
                if not isinstance(name, str) or not name:
                    raise ValueError("palette name must be a nonempty string")
                if name in builtin_names or name in pending or name in staged:
                    raise ValueError(f"duplicate palette preset {name}")
                colors = ["#" + bytes(rgba(color)).hex() for color in item["colors"]]
                if not 1 <= len(colors) <= 256:
                    raise ValueError("palette must contain 1..256 colors")
                names = dict(item.get("names", {}))
                if any(not k.isdecimal() or not 0 <= int(k) < len(colors) for k in names):
                    raise ValueError("color names must refer to palette indices")
                pending[name] = dict(
                    name=name,
                    colors=colors,
                    names=names,
                    license=item.get("license") or descriptor.license,
                    distribution=descriptor.distribution,
                    version=descriptor.version,
                    provider=descriptor.name,
                )
            staged.update(pending)
        except Exception as error:
            manager.discard(descriptor.group, descriptor.name)
            raise plugin_error(descriptor.name, f"palette registration failed: {error}") from error
    return [staged[key] for key in sorted(staged)]
