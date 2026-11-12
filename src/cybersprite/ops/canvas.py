"""Integer canvas geometry, including off-canvas data and slice coordinate transforms."""

import numpy as np

from cybersprite.core import raster
from cybersprite.core.errors import invalid
from cybersprite.core.models import GroupLayer, ImageLayer, LinkCel, Tile, TilemapLayer
from cybersprite.core.pixels import (
    TileRef,
    pixels_from_rows,
    pixels_to_rows,
    tiles_from_rows,
    tiles_to_rows,
)
from cybersprite.core.references import walk_layers
from cybersprite.core.render import render

from .common import array, background_fit, fail, unlocked


def dimensions(w, h):
    if w > 8192 or h > 8192 or w * h > 16777216:
        fail(
            "E_LIMIT_EXCEEDED",
            "Canvas exceeds width, height or area limits.",
            width=w,
            height=h,
            max_side=8192,
            max_area=16777216,
        )


def crop_cels(p):
    for layer, _ in walk_layers(p.layers):
        if not isinstance(layer, ImageLayer):
            continue
        dropped = set()
        for cel in layer.cels:
            if isinstance(cel, LinkCel):
                continue
            x0, y0 = max(0, cel.x), max(0, cel.y)
            x1, y1 = min(p.canvas.width, cel.x + cel.w), min(p.canvas.height, cel.y + cel.h)
            if x0 >= x1 or y0 >= y1:
                dropped.add(cel.frame)
            else:
                data = array(cel)[y0 - cel.y : y1 - cel.y, x0 - cel.x : x1 - cel.x]
                cel.x, cel.y, cel.w, cel.h = x0, y0, x1 - x0, y1 - y0
                cel.pixels = pixels_to_rows(data)
        layer.cels = [
            c
            for c in layer.cels
            if c.frame not in dropped and not (isinstance(c, LinkCel) and c.link in dropped)
        ]
        background_fit(p, layer)
    # Boundary tiles get independent masked copies; shared tiles remain unchanged elsewhere.
    for layer, _ in walk_layers(p.layers):
        if not isinstance(layer, TilemapLayer):
            continue
        ts = next(ts for ts in p.tilesets if ts.id == layer.tileset)
        lookup = {tuple(tile.pixels): i for i, tile in reversed(list(enumerate(ts.tiles)))}
        for cel in layer.cels:
            if isinstance(cel, LinkCel):
                continue
            refs = tiles_from_rows(cel.tiles, cel.w, cel.h)
            for row, entries in enumerate(refs):
                for col, ref in enumerate(entries):
                    x, y = cel.x + col * ts.tile_w, cel.y + row * ts.tile_h
                    if ref.index == 0 or (
                        0 <= x
                        and 0 <= y
                        and x + ts.tile_w <= p.canvas.width
                        and y + ts.tile_h <= p.canvas.height
                    ):
                        continue
                    if (
                        x >= p.canvas.width
                        or y >= p.canvas.height
                        or x + ts.tile_w <= 0
                        or y + ts.tile_h <= 0
                    ):
                        refs[row][col] = TileRef(0)
                        continue
                    data = pixels_from_rows(ts.tiles[ref.index].pixels, ts.tile_w, ts.tile_h)
                    if ref.d and ts.tile_w == ts.tile_h:
                        data = data.T
                    if ref.x:
                        data = data[:, ::-1]
                    if ref.y:
                        data = data[::-1]
                    data = data.copy()
                    yy, xx = np.indices(data.shape, dtype=np.int32)
                    outside = (
                        (xx + x < 0)
                        | (yy + y < 0)
                        | (xx + x >= p.canvas.width)
                        | (yy + y >= p.canvas.height)
                    )
                    data[outside] = p.palette.transparent_index
                    values = tuple(pixels_to_rows(data))
                    if values not in lookup:
                        if len(ts.tiles) >= 65536:
                            fail(
                                "E_LIMIT_EXCEEDED",
                                "Cropping requires a boundary tile beyond the tile limit.",
                            )
                        lookup[values] = len(ts.tiles)
                        ts.tiles.append(Tile(pixels=list(values)))
                    refs[row][col] = TileRef(lookup[values])
            cel.tiles = tiles_to_rows(refs)


def shift(p, dx, dy):
    for layer, _ in walk_layers(p.layers):
        if not isinstance(layer, GroupLayer):
            for cel in layer.cels:
                if not isinstance(cel, LinkCel):
                    cel.x += dx
                    cel.y += dy
    for slc in p.slices:
        for key in slc.keys:
            key.x += dx
            key.y += dy


def rect_transform(x, y, w, h, width, height, flip, rotate):
    if flip == "h":
        x = width - x - w
    elif flip == "v":
        y = height - y - h
    for _ in range(rotate // 90):
        x, y, w, h, width, height = height - y - h, x, h, w, height, width
    return x, y, w, h


def point_transform(x, y, width, height, flip, rotate):
    return rect_transform(x, y, 1, 1, width, height, flip, rotate)[:2]


def canvas_op(ctx, a, name):
    p = ctx.project
    oldw, oldh = p.canvas.width, p.canvas.height
    for layer, _ in walk_layers(p.layers):
        unlocked(p, layer)
    if name == "transform_sprite" and a.rotate in (90, 270):
        for layer, _ in walk_layers(p.layers):
            if isinstance(layer, TilemapLayer):
                ts = next(ts for ts in p.tilesets if ts.id == layer.tileset)
                if ts.tile_w != ts.tile_h:
                    fail(
                        "E_UNSUPPORTED",
                        "Quarter-turns require square tiles; use 180 or flips.",
                        tileset=ts.id,
                        tile_w=ts.tile_w,
                        tile_h=ts.tile_h,
                    )
    if name in ("resize_canvas", "crop_canvas"):
        if name == "resize_canvas":
            w, h = a.width, a.height
            horizontal = (
                0 if a.anchor in ("nw", "w", "sw") else 2 if a.anchor in ("ne", "e", "se") else 1
            )
            vertical = (
                0 if a.anchor in ("nw", "n", "ne") else 2 if a.anchor in ("sw", "s", "se") else 1
            )

            # Truncation toward zero keeps the smaller odd half on the left/top.
            def delta(size, side):
                return (1 if size >= 0 else -1) * (abs(size) * side // 2)

            dx, dy = delta(w - oldw, horizontal), delta(h - oldh, vertical)
        else:
            if a.rect == "content":
                masks = [render(p, f)[:, :, 3] != 0 for f in range(len(p.frames))]
                ys, xs = np.nonzero(np.logical_or.reduce(masks))
                if not len(xs):
                    return {}
                x, y, w, h = (
                    int(xs.min()),
                    int(ys.min()),
                    int(xs.max() - xs.min() + 1),
                    int(ys.max() - ys.min() + 1),
                )
            else:
                x, y, w, h = a.rect.x, a.rect.y, a.rect.w, a.rect.h
                if w < 1 or h < 1:
                    raise invalid("Crop width and height must be positive.")
            dx, dy = -x, -y
        dimensions(w, h)
        shift(p, dx, dy)
        p.canvas.width, p.canvas.height = w, h
        if a.discard_outside:
            crop_cels(p)
    elif name == "scale_sprite":
        f = a.factor
        dimensions(oldw * f, oldh * f)
        p.canvas.width, p.canvas.height = oldw * f, oldh * f
        for key in ("x", "y", "w", "h"):
            setattr(p.canvas.grid, key, getattr(p.canvas.grid, key) * f)
        for layer, _ in walk_layers(p.layers):
            if isinstance(layer, ImageLayer):
                for cel in layer.cels:
                    if not isinstance(cel, LinkCel):
                        cel.pixels = pixels_to_rows(np.repeat(np.repeat(array(cel), f, 0), f, 1))
                        cel.x, cel.y, cel.w, cel.h = cel.x * f, cel.y * f, cel.w * f, cel.h * f
            elif isinstance(layer, TilemapLayer):
                for cel in layer.cels:
                    if not isinstance(cel, LinkCel):
                        cel.x *= f
                        cel.y *= f
        for ts in p.tilesets:
            if ts.tile_w * f > 256 or ts.tile_h * f > 256:
                fail("E_LIMIT_EXCEEDED", "Scaled tile exceeds 256 pixels per side.")
            for tile in ts.tiles:
                data = pixels_from_rows(tile.pixels, ts.tile_w, ts.tile_h)
                tile.pixels = pixels_to_rows(np.repeat(np.repeat(data, f, 0), f, 1))
            ts.tile_w *= f
            ts.tile_h *= f
        for slc in p.slices:
            for key in slc.keys:
                for obj in (key, key.center, key.pivot):
                    if obj is not None:
                        for attr in ("x", "y", "w", "h"):
                            if hasattr(obj, attr):
                                setattr(obj, attr, getattr(obj, attr) * f)
    else:
        for layer, _ in walk_layers(p.layers):
            if isinstance(layer, ImageLayer):
                for cel in layer.cels:
                    if not isinstance(cel, LinkCel):
                        data = array(cel)
                        data, _mask = raster.transform_block(
                            data, np.ones(data.shape, dtype=bool), a.flip, a.rotate
                        )
                        cel.x, cel.y, cel.w, cel.h = rect_transform(
                            cel.x, cel.y, cel.w, cel.h, oldw, oldh, a.flip, a.rotate
                        )
                        cel.pixels = pixels_to_rows(data)
            elif isinstance(layer, TilemapLayer):
                ts = next(ts for ts in p.tilesets if ts.id == layer.tileset)
                for tile_cel in layer.cels:
                    if isinstance(tile_cel, LinkCel):
                        continue
                    refs = tiles_from_rows(tile_cel.tiles, tile_cel.w, tile_cel.h)
                    if a.flip == "h":
                        refs = [row[::-1] for row in refs]
                    elif a.flip == "v":
                        refs = refs[::-1]
                    for _ in range(a.rotate // 90):
                        refs = [list(row) for row in zip(*refs[::-1], strict=True)]
                    transformed = []
                    for row in refs:
                        entries = []
                        for ref in row:
                            if not ref.index:
                                entries.append(ref)
                                continue
                            flip_x, flip_y, diagonal = ref.x, ref.y, ref.d
                            flip_x = flip_x != (a.flip == "h")
                            flip_y = flip_y != (a.flip == "v")
                            if ts.tile_w == ts.tile_h:
                                for _ in range(a.rotate // 90):
                                    flip_x, flip_y, diagonal = not flip_y, flip_x, not diagonal
                            elif a.rotate == 180:
                                flip_x, flip_y = not flip_x, not flip_y
                            entries.append(TileRef(ref.index, flip_x, flip_y, diagonal))
                        transformed.append(entries)
                    tile_cel.x, tile_cel.y, _w, _h = rect_transform(
                        tile_cel.x,
                        tile_cel.y,
                        tile_cel.w * ts.tile_w,
                        tile_cel.h * ts.tile_h,
                        oldw,
                        oldh,
                        a.flip,
                        a.rotate,
                    )
                    tile_cel.w, tile_cel.h = len(transformed[0]), len(transformed)
                    tile_cel.tiles = tiles_to_rows(transformed)
        for slc in p.slices:
            for key in slc.keys:
                w, h = key.w, key.h
                if key.center is not None:
                    c = key.center
                    c.x, c.y, c.w, c.h = rect_transform(c.x, c.y, c.w, c.h, w, h, a.flip, a.rotate)
                if key.pivot is not None:
                    key.pivot.x, key.pivot.y = point_transform(
                        key.pivot.x, key.pivot.y, w, h, a.flip, a.rotate
                    )
                key.x, key.y, key.w, key.h = rect_transform(
                    key.x, key.y, w, h, oldw, oldh, a.flip, a.rotate
                )
        g = p.canvas.grid
        g.x, g.y, g.w, g.h = rect_transform(g.x, g.y, g.w, g.h, oldw, oldh, a.flip, a.rotate)
        if a.rotate in (90, 270):
            p.canvas.width, p.canvas.height = oldh, oldw
    for layer, _ in walk_layers(p.layers):
        background_fit(p, layer)
    return {}
