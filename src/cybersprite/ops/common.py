"""Shared reference checks and indexed cel edits, with explicit link ownership."""

from copy import deepcopy
from typing import NoReturn

import numpy as np

from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.models import ImageCel, ImageLayer, LinkCel
from cybersprite.core.pixels import pixels_from_rows, pixels_to_rows, resolve_color
from cybersprite.core.references import cel_at, cel_owner, resolve_layer, resolve_tag, walk_layers

SYMBOLS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def fail(code, message, **details) -> NoReturn:
    raise CyberSpriteError(
        code, message, "Correct the indicated target or argument and retry.", details
    )


def frame_index(p, frame):
    if not 0 <= frame < len(p.frames):
        fail(
            "E_FRAME_OUT_OF_RANGE",
            "Frame is outside the project.",
            frame=frame,
            frames=len(p.frames),
        )
    return frame


def frames(p, value):
    if type(value) is int:
        result = [value]
    elif isinstance(value, list):
        result = value
    elif value == "all":
        result = list(range(len(p.frames)))
    elif value.startswith("tag:"):
        tag = resolve_tag(p, value[4:])
        result = list(range(tag.from_, tag.to + 1))
    else:
        import re

        match = re.fullmatch(r"(\d+)-(\d+)", value)
        if match is None or int(match[1]) > int(match[2]):
            raise invalid("Frame specifier must be an index, list, a-b, all, or tag:name.")
        result = list(range(int(match[1]), int(match[2]) + 1))
    for f in result:
        frame_index(p, f)
    return sorted(set(result))


def unlocked(p, layer):
    for node, ancestors in walk_layers(p.layers):
        if node.id == layer.id:
            for parent in (*ancestors, node):
                if parent.locked:
                    fail("E_LAYER_LOCKED", "Layer or an ancestor is locked.", layer=parent.id)


def image_layer(p, reference, *, edit=True):
    layer = resolve_layer(p, reference)
    if edit:
        unlocked(p, layer)
    if not isinstance(layer, ImageLayer):
        fail("E_WRONG_LAYER_TYPE", "Pixel operations require an image layer.", type=layer.type)
    return layer


def array(cel):
    return pixels_from_rows(cel.pixels, cel.w, cel.h)


def canvas_pixels(p, layer, frame):
    frame_index(p, frame)
    result = np.full((p.canvas.height, p.canvas.width), p.palette.transparent_index, dtype=np.uint8)
    cel = cel_owner(layer, cel_at(layer, frame))
    if cel is not None:
        x0, y0 = max(0, cel.x), max(0, cel.y)
        x1, y1 = min(p.canvas.width, cel.x + cel.w), min(p.canvas.height, cel.y + cel.h)
        if x0 < x1 and y0 < y1:
            result[y0:y1, x0:x1] = array(cel)[y0 - cel.y : y1 - cel.y, x0 - cel.x : x1 - cel.x]
    return result


def write_points(ctx, layer, frame, points):
    """Last point wins; count final changed values, retaining off-canvas cel content."""
    p = ctx.project
    frame_index(p, frame)
    values = {}
    for x, y, value in points:
        if not (0 <= x < p.canvas.width and 0 <= y < p.canvas.height):
            ctx.clipped_pixels += 1
        else:
            values[x, y] = value
    if not values:
        return 0
    current = cel_at(layer, frame)
    owner = cel_owner(layer, current)
    if owner is not None:
        linked = [
            c.frame
            for c in layer.cels
            if c.frame == owner.frame or isinstance(c, LinkCel) and c.link == owner.frame
        ]
        if len(linked) > 1:
            ctx.linked_frames.update(linked)
            ctx.link_groups.add(tuple(sorted(linked)))
    left = min(x for x, y in values)
    top = min(y for x, y in values)
    right = max(x for x, y in values) + 1
    bottom = max(y for x, y in values) + 1
    if owner is not None:
        left, top = min(left, owner.x), min(top, owner.y)
        right, bottom = max(right, owner.x + owner.w), max(bottom, owner.y + owner.h)
    data = np.full((bottom - top, right - left), p.palette.transparent_index, dtype=np.uint8)
    if owner is not None:
        data[owner.y - top : owner.y - top + owner.h, owner.x - left : owner.x - left + owner.w] = (
            array(owner)
        )
    changed = 0
    for (x, y), value in values.items():
        changed += int(data[y - top, x - left] != value)
        data[y - top, x - left] = value
    if not changed:
        return 0
    if owner is None:
        owner = ImageCel(
            frame=frame, x=left, y=top, w=right - left, h=bottom - top, pixels=pixels_to_rows(data)
        )
        layer.cels.append(owner)
    else:
        owner.x, owner.y, owner.w, owner.h = left, top, right - left, bottom - top
        owner.pixels = pixels_to_rows(data)
    layer.cels.sort(key=lambda c: c.frame)
    return changed


def rows(p, values, fmt):
    if not values or not values[0]:
        raise invalid("Rows must be a nonempty rectangular pixel array.")
    if fmt == "hex":
        result = pixels_from_rows(values, len(values[0]) // 2, len(values))
    else:
        if len(p.palette.colors) > 62:
            raise invalid("Symbol rows require a palette of at most 62 colors.")
        if any(len(row) != len(values[0]) for row in values):
            raise invalid("Symbol rows must have equal widths.")
        result = np.full((len(values), len(values[0])), p.palette.transparent_index, dtype=np.uint8)
        for y, row in enumerate(values):
            for x, symbol in enumerate(row):
                if symbol == ".":
                    continue
                if symbol not in SYMBOLS:
                    raise invalid("Unknown symbol in pixel rows.", symbol=symbol)
                index = SYMBOLS.index(symbol)
                if index == p.palette.transparent_index:
                    raise invalid("Use a dot for the transparent index.", symbol=symbol)
                result[y, x] = resolve_color(p.palette, index)
    if int(result.max()) >= len(p.palette.colors):
        fail(
            "E_INDEX_OUT_OF_RANGE",
            "Rows contain an index outside the palette.",
            palette_size=len(p.palette.colors),
        )
    return result


def groups(layer):
    result = []
    for cel in layer.cels:
        if not isinstance(cel, LinkCel):
            members = {
                c.frame: c.z_index
                for c in layer.cels
                if c is cel or isinstance(c, LinkCel) and c.link == cel.frame
            }
            result.append((deepcopy(cel), members))
    return result


def set_groups(layer, values):
    result = []
    for owner, members in values:
        if not members:
            continue
        first = min(members)
        owner.frame, owner.z_index = first, members[first]
        result.append(owner)
        result.extend(
            LinkCel(frame=f, link=first, z_index=z)
            for f, z in sorted(members.items())
            if f != first
        )
    layer.cels = sorted(result, key=lambda c: c.frame)


def detach(layer, frame):
    values = groups(layer)
    for _owner, members in values:
        members.pop(frame, None)
    set_groups(layer, values)


def put_cel(layer, cel, frame):
    detach(layer, frame)
    cel = deepcopy(cel)
    cel.frame = frame
    layer.cels.append(cel)
    layer.cels.sort(key=lambda c: c.frame)


def siblings(p, layer):
    for node, ancestors in walk_layers(p.layers):
        if node.id == layer.id:
            return ancestors[-1].children if ancestors else p.layers
    raise invalid("Layer is not in this project.")


def background_fit(p, layer):
    if not isinstance(layer, ImageLayer) or not layer.background:
        return
    values = groups(layer)
    represented = {f for _, members in values for f in members}
    for owner, _members in values:
        data = np.full(
            (p.canvas.height, p.canvas.width), p.palette.transparent_index, dtype=np.uint8
        )
        x0, y0 = max(0, owner.x), max(0, owner.y)
        x1, y1 = min(p.canvas.width, owner.x + owner.w), min(p.canvas.height, owner.y + owner.h)
        if x0 < x1 and y0 < y1:
            data[y0:y1, x0:x1] = array(owner)[
                y0 - owner.y : y1 - owner.y, x0 - owner.x : x1 - owner.x
            ]
        owner.x = owner.y = 0
        owner.w, owner.h = p.canvas.width, p.canvas.height
        owner.pixels = pixels_to_rows(data)
    for f in range(len(p.frames)):
        if f not in represented:
            values.append(
                (
                    ImageCel(
                        frame=f,
                        x=0,
                        y=0,
                        w=p.canvas.width,
                        h=p.canvas.height,
                        pixels=[f"{p.palette.transparent_index:02x}" * p.canvas.width]
                        * p.canvas.height,
                    ),
                    {f: 0},
                )
            )
    set_groups(layer, values)
