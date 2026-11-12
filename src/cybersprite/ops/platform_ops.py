"""Platform operations and explicit default propagation through the registry."""

from typing import Annotated, Literal, cast

from pydantic import Field

from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.models import Model, ValidationSettings
from cybersprite.core.pixels import rgba
from cybersprite.core.platform import Tick, guide, nearest_rgb, tick_durations
from cybersprite.core.registry import Op
from cybersprite.platforms import list_platforms, resolve

from .common import frames


class SetPlatformArgs(Model):
    platform: str | dict | None = Field(
        description="Platform ID, data-only snapshot, or null to remove."
    )
    overrides: dict = Field(
        default_factory=dict, description="JSON Pointer to replacement value mapping."
    )
    apply_validation: bool = Field(
        True, description="Copy platform validation defaults into project settings."
    )


class SetPlatformResult(Model):
    platform: dict | None
    copied_validation_keys: list[str]
    issues: list[dict]


class ListArgs(Model):
    id: str | None = Field(None, description="Optional platform ID to resolve and show.")
    guide: bool = Field(
        False, description="Include a deterministic guide of at most 2048 UTF-8 bytes."
    )


class ListResult(Model):
    platforms: list[dict]
    platform: dict | None = None
    guide: str | None = None


class ConformArgs(Model):
    pass


class ConformResult(Model):
    replacements: list[dict]


class TicksArgs(Model):
    frames: int | list[int] | str = Field(
        "all", description="Zero-based frame selection or tag:name."
    )
    ticks: Annotated[int, Field(ge=1)] | list[Annotated[int, Field(ge=1)]] = Field(
        description="Positive tick count per frame, or one count for every selected frame."
    )
    tick: Tick | None = Field(
        None, description="Seconds per tick; omission uses the platform tick."
    )


class TicksResult(Model):
    durations_ms: list[int]


def copy_validation(p):
    plat = p.platform
    if plat is None:
        return []
    patch = plat.validation.model_dump(exclude_none=True)
    if not patch.get("severity"):
        patch.pop("severity", None)
    for source, target in (("palette_max", "palette_max"), ("opaque_max", "colors_per_frame_max")):
        value = getattr(plat.asset.colors, source)
        if value is not None and target not in patch:
            patch[target] = value
    current = p.validation.model_dump()
    copied: list[str] = []
    for key in sorted(patch):
        if key == "severity":
            current[key].update(patch[key])
            copied.extend("severity." + rule for rule in sorted(patch[key]))
        else:
            current[key] = patch[key]
            copied.append(key)
    p.validation = ValidationSettings.model_validate(current)
    return copied


def replacements(p):
    if p.platform is None:
        raise invalid("conform_palette requires a platform; apply set_platform first.")
    color = p.platform.system.color
    master = tuple(tuple(c) for c in color.master_colors)
    result = []
    for index, before in enumerate(p.palette.colors):
        r, g, b, a = rgba(before)
        rgb = nearest_rgb((r, g, b), color.model_dump_json(), master)
        after = "#" + bytes((*rgb, a)).hex()
        if before.lower() != after:
            result.append({"index": index, "before": before, "after": after})
    return result


def platform_op(ctx, a, name):
    if name == "list_platforms":
        result = {"platforms": list_platforms()}
        if a.id is not None:
            p = resolve(a.id)
            result["platform"] = p.model_dump(by_alias=True)
            if a.guide:
                result["guide"] = guide(p)
        return result
    p = ctx.project
    if name == "set_platform":
        p.platform = resolve(
            a.platform, overrides=a.overrides, width=p.canvas.width, height=p.canvas.height
        )
        copied = copy_validation(p) if a.apply_validation else []
        from cybersprite.core.quality import report

        return {
            "platform": p.platform.model_dump(by_alias=True) if p.platform else None,
            "copied_validation_keys": copied,
            "issues": [i for i in report(p)["issues"] if i["rule"].startswith("Q-PLT-")],
        }
    if name == "conform_palette":
        if p.palette.frozen:
            raise CyberSpriteError(
                "E_PALETTE_FROZEN",
                "Cannot conform a frozen palette.",
                "Use set_palette_frozen with frozen=false before conform_palette.",
            )
        changes = replacements(p)
        for change in changes:
            p.palette.colors[change["index"]] = change["after"]
        return {"replacements": changes}
    tick = a.tick or (p.platform.asset.animation.tick if p.platform else None)
    if tick is None:
        raise invalid("set_frame_ticks requires tick or a platform animation.tick.")
    selected = frames(p, a.frames)
    ticks = [a.ticks] * len(selected) if isinstance(a.ticks, int) else a.ticks
    if len(ticks) != len(selected):
        raise invalid("ticks must have exactly one count per selected frame.", frames=selected)
    durations = []
    phase_ticks: list[int] = []
    starts = {t.from_ for t in p.tags}
    for frame, count in zip(selected, ticks, strict=True):
        if frame in starts:
            phase_ticks = []
        phase_ticks.append(count)
        durations.append(tick_durations(phase_ticks, tick)[-1])
    for frame, duration in zip(selected, durations, strict=True):
        if not 1 <= duration <= 65535:
            raise invalid(
                "Allocated tick duration must be within 1..65535 ms.",
                frame=frame,
                duration_ms=duration,
            )
        p.frames[frame].duration_ms = duration
    return {"durations_ms": durations}


def register_platforms(registry):
    from functools import partial

    for name, args, result, kind, idem, description in (
        (
            "set_platform",
            SetPlatformArgs,
            SetPlatformResult,
            "mutate",
            "I",
            "Store a resolved platform snapshot and optionally copy validation defaults.",
        ),
        (
            "list_platforms",
            ListArgs,
            ListResult,
            "query",
            "R",
            "List data-only platforms or inspect a resolved platform and guide.",
        ),
        (
            "conform_palette",
            ConformArgs,
            ConformResult,
            "mutate",
            "I",
            "Explicitly replace palette RGB with the nearest representable platform colors.",
        ),
        (
            "set_frame_ticks",
            TicksArgs,
            TicksResult,
            "mutate",
            "I",
            "Allocate integer milliseconds from positive rational frame ticks.",
        ),
    ):
        registry.register(
            Op(
                name,
                args,
                partial(platform_op, name=name),
                result,
                cast(Literal["query", "mutate"], kind),
                cast(Literal["R", "I"], idem),
                description=description,
            )
        )


def apply_defaults(p, a, name):
    """Change omitted arguments only, returning their snapshot default keys."""
    if p.platform is None:
        if name in ("add_tileset", "tileset_from_layer") and (a.tile_w is None or a.tile_h is None):
            raise invalid("Provide tile_w and tile_h, or apply a platform with system.tile.")
        return []
    defaults = p.platform.defaults
    used = []
    if name == "render_preview" and a.scale == "auto" and defaults.preview.scale:
        a.scale = defaults.preview.scale
        used.append("defaults.preview.scale")
    if name in ("add_tileset", "tileset_from_layer"):
        tile = p.platform.system.tile
        for key, axis in (("tile_w", "w"), ("tile_h", "h")):
            if key not in a.model_fields_set and tile is not None:
                setattr(a, key, getattr(tile, axis))
                used.append("system.tile." + axis)
        if a.tile_w is None or a.tile_h is None:
            raise invalid("Provide tile_w and tile_h, or apply a platform with system.tile.")
    if (
        name.startswith("export_")
        and hasattr(a, "scale")
        and "scale" not in a.model_fields_set
        and defaults.export.scale
    ):
        a.scale = defaults.export.scale
        used.append("defaults.export.scale")
    if name == "export_sheet" and defaults.export.sheet is not None:
        for key in ("layout", "data_format"):
            if key not in a.model_fields_set:
                setattr(a, key, getattr(defaults.export.sheet, key))
                used.append("defaults.export.sheet." + key)
    return used
