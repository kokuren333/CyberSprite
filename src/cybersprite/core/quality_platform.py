"""Platform constraint rules; no definition discovery during validation."""

import numpy as np

from .models import GroupLayer, TilemapLayer
from .pixels import rgba
from .platform import nearest_rgb, tick_durations
from .references import cel_owner, walk_layers
from .render import render_indexed

LEVELS = {
    "Q-PLT-01": "error",
    "Q-PLT-02": "error",
    "Q-PLT-03": "error",
    "Q-PLT-05": "warning",
    "Q-PLT-07": "info",
    "Q-PLT-08": "info",
}


def evaluate(p, colors_per_frame):
    platform = p.platform
    issues = []

    def add(rule, message, *, frames=None, layer=None, **where):
        level = p.validation.severity.get(rule, LEVELS[rule])
        if level != "off":
            issues.append(
                {
                    "rule": rule,
                    "level": level,
                    "message": message,
                    "where": {
                        "frames": frames or [],
                        "layer": layer,
                        "bbox": None,
                        "points": [],
                        **where,
                    },
                }
            )

    system, asset = platform.system, platform.asset
    canvas = asset.canvas
    w, h = p.canvas.width, p.canvas.height
    if canvas and canvas.fixed and (w, h) != (canvas.w, canvas.h):
        add(
            "Q-PLT-01",
            "Canvas differs from the fixed platform dimensions; resize_canvas or change platform.",
            expected={"w": canvas.w, "h": canvas.h},
            actual={"w": w, "h": h},
        )
    if (
        asset.role == "background"
        and system.screen
        and (w < system.screen.w or h < system.screen.h)
    ):
        add("Q-PLT-01", "Background is smaller than the platform screen.")
    tile = system.tile
    if tile and tile.map_max and (w > tile.map_max.w * tile.w or h > tile.map_max.h * tile.h):
        add("Q-PLT-01", "Canvas exceeds the platform tile map dimensions.")
    color = system.color
    master = tuple(tuple(c) for c in color.master_colors)
    unrepresentable = 0
    for i, entry in enumerate(p.palette.colors):
        r, g, b, a = rgba(entry)
        rgb = nearest_rgb((r, g, b), color.model_dump_json(), master)
        if rgb != (r, g, b):
            unrepresentable += 1
            add(
                "Q-PLT-02",
                "Palette color is not representable; preview conform_palette with dry_run=true.",
                index=i,
                nearest="#" + bytes((*rgb, a)).hex(),
            )
        if color.alpha == "binary" and a not in (0, 255):
            add("Q-PLT-03", "Platform requires binary palette alpha.", index=i)
    sizes = system.object.sizes if system.object else None

    def dimensions(width, height, **where):
        if tile and (width % tile.w or height % tile.h):
            add("Q-PLT-05", "Dimensions are not multiples of the platform tile size.", **where)
        if sizes and asset.role == "sprite" and [width, height] not in sizes:
            add(
                "Q-PLT-05",
                "Dimensions require several platform objects; inspect object composition.",
                **where,
            )

    dimensions(w, h, resource="canvas")
    for layer, _ in walk_layers(p.layers):
        if color.alpha == "binary" and layer.opacity < 255:
            add("Q-PLT-03", "Platform requires layer opacity 255.", layer=layer.id)
        if isinstance(layer, GroupLayer):
            continue
        for cel in layer.cels:
            owner = cel_owner(layer, cel)
            if color.alpha == "binary" and owner.opacity < 255:
                add(
                    "Q-PLT-03",
                    "Platform requires cel opacity 255.",
                    layer=layer.id,
                    frames=[cel.frame],
                )
            cw, ch = owner.w, owner.h
            if isinstance(layer, TilemapLayer):
                ts = next(ts for ts in p.tilesets if ts.id == layer.tileset)
                cw, ch = cw * ts.tile_w, ch * ts.tile_h
            dimensions(cw, ch, layer=layer.id, frames=[cel.frame])
    for slc in p.slices:
        for key in slc.keys:
            if key.w and key.h:
                dimensions(key.w, key.h, frames=[key.frame], slice=slc.id)
    deviations = []
    tick = asset.animation.tick
    if tick:
        # Each tag owns its phase. Overlapping tags use their earliest start.
        groups: dict[int, list[int]] = {}
        for f in range(len(p.frames)):
            starts = [t.from_ for t in p.tags if t.from_ <= f <= t.to]
            start = min(starts) if starts else 0
            groups.setdefault(start, []).append(f)
        for start in sorted(groups):
            fs = groups[start]
            counts = [
                max(1, (p.frames[f].duration_ms * tick.den + 500 * tick.num) // (1000 * tick.num))
                for f in fs
            ]
            expected = tick_durations(counts, tick)
            for f, duration in zip(fs, expected, strict=True):
                if abs(p.frames[f].duration_ms - duration) > 1:
                    deviations.append(f)
                    add(
                        "Q-PLT-07",
                        "Frame duration differs from the tick allocation; use set_frame_ticks.",
                        frames=[f],
                        expected_ms=duration,
                    )
    tags = {t.name for t in p.tags}
    for name in asset.animation.tags:
        if name not in tags:
            add("Q-PLT-08", "Required platform animation tag is missing.", tag=name)
    if asset.animation.frames_max is not None and len(p.frames) > asset.animation.frames_max:
        add(
            "Q-PLT-08",
            "Frame count exceeds the platform animation limit.",
            limit=asset.animation.frames_max,
        )
    unique, flipped = set(), set()
    if tile:
        for f in range(len(p.frames)):
            image = render_indexed(p, f, {"flatten": "nearest"})
            for y in range(0, h, tile.h):
                for x in range(0, w, tile.w):
                    data = np.full((tile.h, tile.w), p.palette.transparent_index, dtype=np.uint8)
                    part = image[y : y + tile.h, x : x + tile.w]
                    data[: part.shape[0], : part.shape[1]] = part
                    raw = data.tobytes()
                    unique.add(raw)
                    variants = []
                    for d in (False, True) if tile.flips.d and tile.w == tile.h else (False,):
                        for fy in (False, True) if tile.flips.y else (False,):
                            for fx in (False, True) if tile.flips.x else (False,):
                                v = data.T if d else data
                                v = v[::-1] if fy else v
                                v = v[:, ::-1] if fx else v
                                variants.append(v.tobytes())
                    flipped.add(min(variants))
    # The shared quality reporter groups by rule/frame/layer. Preserve every
    # resource-specific location before that grouping can discard later colors,
    # slices or missing tags.
    grouped: dict[tuple, dict] = {}
    common = {"frames", "layer", "bbox", "points", "findings"}
    for issue in issues:
        where = issue["where"]
        key = issue["rule"], tuple(where["frames"]), where["layer"]
        if key not in grouped:
            grouped[key] = issue
            continue
        previous = grouped[key]
        prior_where = previous["where"]
        old = {k: v for k, v in prior_where.items() if k not in common}
        new = {k: v for k, v in where.items() if k not in common}
        if old != new:
            locations = prior_where.setdefault("findings", [old])
            if new not in locations:
                locations.append(new)
        if issue["message"] not in previous["message"]:
            previous["message"] += " " + issue["message"]
    ordered = sorted(grouped, key=lambda key: (key[0], key[1], key[2] or ""))
    return [grouped[key] for key in ordered], {
        "id": platform.id,
        "opaque_max": max(colors_per_frame),
        "unrepresentable_colors": unrepresentable,
        "unique_tiles": len(unique),
        "unique_tiles_with_flips": len(flipped),
        "tick_deviations": len(set(deviations)),
    }
