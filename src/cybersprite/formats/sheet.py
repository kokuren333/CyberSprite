"""Integer sheet enumeration, shelf placement, and the three normative JSON forms."""

from dataclasses import dataclass
from math import isqrt

import numpy as np

from cybersprite import __version__
from cybersprite.core.canonical import _ordered
from cybersprite.core.errors import invalid
from cybersprite.core.hashing import pixel_sha256
from cybersprite.core.models import GroupLayer
from cybersprite.core.references import resolve_layer, resolve_tag, walk_layers
from cybersprite.core.render import indexed_result, render_result

from .common import bounds, fail, format_name, frame_sequence, name_values, slice_bounds


@dataclass
class Item:
    name: str
    frame: int
    layer_id: str | None
    tag_id: str | None
    slice_id: str | None
    pixels: np.ndarray
    palette: list[str] | None
    source_rect: dict
    source_size: dict
    trimmed: bool
    duration_ms: int
    rect: dict | None = None


def ceil_sqrt(n):
    root = isqrt(n)
    return root + int(root * root < n)


def layout_rectangles(sizes, a):
    """All sizes include inner padding; explicit width/height include the outer border."""
    b, gap = a.border, a.spacing
    width = a.width - 2 * b if a.width is not None else None
    height = a.height - 2 * b if a.height is not None else None
    if width is not None and width < 1 or height is not None and height < 1:
        raise invalid("Sheet width/height must leave room inside the border.")
    order = list(range(len(sizes)))
    if a.layout == "packed":
        order.sort(key=lambda i: (-sizes[i][1], -sizes[i][0], i))
        if width is None:
            width = max(
                max((w for w, h in sizes), default=1), ceil_sqrt(sum(w * h for w, h in sizes))
            )
    vertical = a.layout in ("vertical", "columns")
    major_limit = height if vertical else width
    count = a.rows if vertical else a.columns
    if a.layout in ("rows", "columns") and count is None and major_limit is None:
        count = max(1, ceil_sqrt(len(sizes)))
    placements = [None] * len(sizes)
    cursor = cross = line_size = line_count = 0
    used_w = used_h = 0
    for index in order:
        w, h = sizes[index]
        if width is not None and w > width or height is not None and h > height:
            raise invalid(
                "An item does not fit inside the requested sheet dimensions.",
                item=index,
                width=w,
                height=h,
            )
        major, minor = (h, w) if vertical else (w, h)
        wrap = (
            a.layout in ("rows", "columns", "packed")
            and line_count
            and (
                count is not None
                and line_count >= count
                or major_limit is not None
                and cursor + major > major_limit
            )
        )
        if wrap:
            cross += line_size + gap
            cursor = line_size = line_count = 0
        x, y = (cross, cursor) if vertical else (cursor, cross)
        placements[index] = (b + x, b + y)
        used_w, used_h = max(used_w, x + w), max(used_h, y + h)
        cursor += major + gap
        line_size = max(line_size, minor)
        line_count += 1
    final_w = max(1, used_w) + 2 * b
    final_h = max(1, used_h) + 2 * b
    if a.width is not None:
        if final_w > a.width:
            raise invalid("Items exceed the specified sheet width.", required=final_w)
        final_w = a.width
    elif a.layout == "packed":
        final_w = width + 2 * b
    if a.height is not None:
        if final_h > a.height:
            raise invalid("Items exceed the specified sheet height.", required=final_h)
        final_h = a.height
    if a.power_of_two:
        final_w = 1 << (final_w - 1).bit_length()
        final_h = 1 << (final_h - 1).bit_length()
    if max(final_w, final_h) > 16384:
        fail(
            "E_LIMIT_EXCEEDED",
            "Sheet dimensions exceed 16384 pixels.",
            width=final_w,
            height=final_h,
            limit=16384,
        )
    return placements, final_w, final_h


def selected_layers(p, a):
    included = None if a.layers is None else {resolve_layer(p, r).id for r in a.layers}
    excluded = {resolve_layer(p, r).id for r in a.exclude_layers}
    return [
        layer
        for layer, ancestors in walk_layers(p.layers)
        if not isinstance(layer, GroupLayer)
        and (a.include_hidden or all(node.visible for node in (*ancestors, layer)))
        and not any(node.id in excluded for node in (*ancestors, layer))
        and (included is None or any(node.id in included for node in (*ancestors, layer)))
    ]


def enumerate_items(p, a):
    sequence = sorted(set(frame_sequence(p, a.frames)))
    if a.tag is not None:
        tag = resolve_tag(p, a.tag)
        sequence = [f for f in sequence if tag.from_ <= f <= tag.to]
    layers = selected_layers(p, a)
    tags = list(p.tags) if a.split_tags else [resolve_tag(p, a.tag) if a.tag else None]
    slices = list(p.slices) if a.split_slices else [None]
    items, warnings = [], []
    for layer in layers if a.split_layers else [None]:
        for tag in tags:
            for slice in slices:
                for frame in sequence:
                    if tag is not None and not tag.from_ <= frame <= tag.to:
                        continue
                    if slice is not None and not any(k.frame <= frame for k in slice.keys):
                        continue
                    crop = slice_bounds(p, slice.id, frame)[1] if slice else None
                    options = dict(
                        layers=[layer.id] if layer else [node.id for node in layers],
                        include_hidden=a.include_hidden,
                        crop=crop,
                        scale=a.scale,
                        flatten=a.flatten,
                    )
                    rendered = (indexed_result if a.color_mode == "indexed" else render_result)(
                        p, frame, options
                    )
                    warnings.extend(rendered.warnings)
                    pixels = rendered.pixels
                    left, top, w, h, empty = bounds(pixels, rendered.palette)
                    if empty and a.ignore_empty:
                        continue
                    trimmed = a.trim and (left, top, w, h) != (
                        0,
                        0,
                        pixels.shape[1],
                        pixels.shape[0],
                    )
                    if a.trim or empty:
                        pixels = pixels[top : top + h, left : left + w].copy()
                    else:
                        left = top = 0
                        h, w = pixels.shape[:2]
                    source_rect = dict(
                        x=left + (crop["x"] * a.scale if crop else 0),
                        y=top + (crop["y"] * a.scale if crop else 0),
                        w=w,
                        h=h,
                    )
                    name = format_name(
                        a.item_name, **name_values(p, frame, layer=layer, tag=tag, slice=slice)
                    )
                    items.append(
                        Item(
                            name,
                            frame,
                            layer.id if layer else None,
                            tag.id if tag else None,
                            slice.id if slice else None,
                            pixels,
                            rendered.palette,
                            source_rect,
                            dict(w=p.canvas.width * a.scale, h=p.canvas.height * a.scale),
                            bool(trimmed or empty),
                            p.frames[frame].duration_ms,
                        )
                    )
    return items, warnings


def shared_palette(items, fallback):
    """Indexed renders may alter alpha at background indices, but cannot conflict."""
    palette, assigned = list(fallback), {}
    for item in items:
        for index in (int(i) for i in np.unique(item.pixels)):
            color = item.palette[index]
            if index in assigned and assigned[index] != color:
                fail(
                    "E_NOT_PALETTE_CLOSED",
                    "Frames require conflicting colors at one palette index.",
                    index=index,
                )
            assigned[index] = color
    for index in sorted(assigned):
        palette[index] = assigned[index]
    return palette


def build_sheet(p, a, items):
    unique, mapping, seen = [], [], {}
    for item in items:
        key = (item.pixels.shape, pixel_sha256(item.pixels))
        if not a.merge_duplicates or key not in seen:
            seen[key] = len(unique)
            unique.append(item)
        mapping.append(seen[key])
    sizes = [
        (item.pixels.shape[1] + 2 * a.inner, item.pixels.shape[0] + 2 * a.inner) for item in unique
    ]
    positions, width, height = layout_rectangles(sizes, a)
    indexed = a.color_mode == "indexed"
    pixels = (
        np.full((height, width), p.palette.transparent_index, dtype=np.uint8)
        if indexed
        else np.zeros((height, width, 4), dtype=np.uint8)
    )
    for item, (x, y) in zip(unique, positions, strict=True):
        x, y = x + a.inner, y + a.inner
        h, w = item.pixels.shape[:2]
        pixels[y : y + h, x : x + w] = item.pixels
        item.rect = dict(x=x, y=y, w=w, h=h)
    for item, index in zip(items, mapping, strict=True):
        item.rect = dict(unique[index].rect)
    palette = shared_palette(items, p.palette.colors) if indexed else None
    if indexed and not items:
        palette[p.palette.transparent_index] = "#00000000"
    return pixels, palette


def sheet_data(p, a, items, width, height, image):
    size = dict(w=width, h=height)
    if a.data_format == "cybersprite":
        layer_names = {layer.id: layer.name for layer, _ in walk_layers(p.layers)}
        tag_names = {tag.id: tag.name for tag in p.tags}
        slice_names = {slice.id: slice.name for slice in p.slices}
        return dict(
            format="cybersprite-sheet",
            schema_version=1,
            image=image,
            size=size,
            scale=a.scale,
            color_mode=a.color_mode,
            source=dict(
                name=p.name, revision=p.revision, canvas=dict(w=p.canvas.width, h=p.canvas.height)
            ),
            palette=p.palette.colors,
            transparent_index=p.palette.transparent_index,
            items=[
                dict(
                    name=i.name,
                    frame=i.frame,
                    layer=layer_names[i.layer_id] if i.layer_id is not None else None,
                    layer_id=i.layer_id,
                    tag=tag_names[i.tag_id] if i.tag_id is not None else None,
                    tag_id=i.tag_id,
                    slice=slice_names[i.slice_id] if i.slice_id is not None else None,
                    slice_id=i.slice_id,
                    rect=i.rect,
                    trimmed=i.trimmed,
                    source_rect=i.source_rect,
                    source_size=i.source_size,
                    duration_ms=i.duration_ms,
                    pixel_sha256=pixel_sha256(i.pixels),
                )
                for i in items
            ],
            tags=[
                {k: v for k, v in t.model_dump(by_alias=True).items() if k != "user_data"}
                for t in p.tags
            ],
            layers=[
                dict(
                    id=layer.id,
                    name=layer.name,
                    path="/".join(n.name for n in (*anc, layer)),
                    opacity=layer.opacity,
                    blend_mode=layer.blend_mode,
                )
                for layer, anc in walk_layers(p.layers)
            ],
            slices=[
                dict(id=s.id, name=s.name, color=s.color, keys=[_ordered(k) for k in s.keys])
                for s in p.slices
            ],
        )
    entries = [
        dict(
            frame=i.rect,
            rotated=False,
            trimmed=i.trimmed,
            spriteSourceSize=i.source_rect,
            sourceSize=i.source_size,
            duration=i.duration_ms,
        )
        for i in items
    ]
    names = [i.name for i in items]
    if a.data_format == "json-hash":
        if len(set(names)) != len(names):
            raise invalid(
                "json-hash item names must be unique; include layer/tag/slice placeholders."
            )
        frames = dict(zip(names, entries, strict=True))
    else:
        frames = [dict(filename=name, **entry) for name, entry in zip(names, entries, strict=True)]
    tags = []
    for tag in p.tags:
        positions = [n for n, item in enumerate(items) if tag.from_ <= item.frame <= tag.to]
        if positions:
            entry = dict(
                name=tag.name,
                **{"from": min(positions)},
                to=max(positions),
                direction=tag.direction,
            )
            if tag.repeat >= 1:
                entry["repeat"] = str(tag.repeat)
            entry["color"] = tag.color + "ff"
            tags.append(entry)
    layers = []
    for layer, ancestors in walk_layers(p.layers):
        entry = dict(name=layer.name)
        if not isinstance(layer, GroupLayer):
            if ancestors:
                entry["group"] = ancestors[-1].name
            entry.update(opacity=layer.opacity, blendMode=layer.blend_mode)
        layers.append(entry)
    slices = []
    for s in p.slices:
        keys = []
        for key in s.keys:
            entry = dict(frame=key.frame, bounds={k: getattr(key, k) for k in ("x", "y", "w", "h")})
            if key.center is not None:
                entry["center"] = key.center.model_dump()
            if key.pivot is not None:
                entry["pivot"] = key.pivot.model_dump()
            keys.append(entry)
        slices.append(dict(name=s.name, color=s.color, keys=keys))
    return dict(
        frames=frames,
        meta=dict(
            app="CyberSprite",
            version=__version__,
            image=image,
            format="I8" if a.color_mode == "indexed" else "RGBA8888",
            size=size,
            scale=str(a.scale),
            frameTags=tags,
            layers=layers,
            slices=slices,
        ),
    )
