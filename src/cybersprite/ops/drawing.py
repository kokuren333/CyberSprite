"""Indexed drawing operations using the normative raster module exclusively."""

import numpy as np

from cybersprite.core import raster
from cybersprite.core.errors import invalid
from cybersprite.core.models import ImageLayer
from cybersprite.core.pixels import pixels_from_rows, pixels_to_rows, resolve_color
from cybersprite.core.references import walk_layers
from cybersprite.core.render import render_indexed

from .common import (
    canvas_pixels,
    fail,
    frame_index,
    frames,
    image_layer,
    rows,
    unlocked,
    write_points,
)


def region(p, value, image):
    spec = value.model_dump()
    if spec["type"] == "color":
        spec["color"] = resolve_color(p.palette, spec["color"])
    return raster.region_mask(spec, p.canvas.width, p.canvas.height, image)


def drawing(ctx, a, name):
    p = ctx.project
    if name == "cleanup_pixels":
        from cybersprite.core.pixels import rgba
        from cybersprite.core.references import cel_at, cel_owner
        from cybersprite.pipeline.cleanup import cleanup_pixels

        layer = image_layer(p, a.layer)
        selected = frames(p, a.frames) if a.frame is None else [frame_index(p, a.frame)]
        protect = [resolve_color(p.palette, c) for c in (a.protect or [])]
        palette = [rgba(c) for c in p.palette.colors]
        visited, count = set(), 0
        positions: list[dict] = []
        for frame in selected:
            owner = cel_owner(layer, cel_at(layer, frame))
            key = owner.frame if owner else frame
            if key in visited:
                continue
            visited.add(key)
            original = canvas_pixels(p, layer, frame)
            cleaned, _ = cleanup_pixels(
                original,
                palette,
                transparent_index=p.palette.transparent_index,
                min_cluster=a.min_cluster,
                connectivity=a.connectivity,
                max_passes=a.max_passes,
                protect=protect,
            )
            mask = region(p, a.region, original) & (cleaned != original)
            points = [(int(x), int(y), int(cleaned[y, x])) for y, x in np.argwhere(mask)]
            count += write_points(ctx, layer, frame, points)
            positions.extend(
                {"frame": frame, "x": x, "y": y, "from": int(original[y, x]), "to": value}
                for x, y, value in points
            )
        return {
            "pixels_written": count,
            "positions": positions[:256],
            "positions_truncated": len(positions) > 256,
        }
    if name == "replace_color":
        source, target = resolve_color(p.palette, a.from_), resolve_color(p.palette, a.to)
        if a.layers is None:
            layers = []
            for node, ancestors in walk_layers(p.layers):
                if isinstance(node, ImageLayer) and not any(n.locked for n in (*ancestors, node)):
                    layers.append(node)
        else:
            layers = [image_layer(p, ref) for ref in a.layers]
        count = 0
        selected_frames = frames(p, a.frames)
        if a.tilesets:
            # Tiles are shared resources: frame/layer/region selections apply to image cels;
            # all nonzero tiles are replaced once, including currently unused tiles.
            for ts in p.tilesets:
                from .tiles import tile_layers

                list(tile_layers(p, ts, edit=True))
                for tile in ts.tiles[1:]:
                    data = pixels_from_rows(tile.pixels, ts.tile_w, ts.tile_h)
                    mask = data == source
                    if source != target:
                        count += int(np.count_nonzero(mask))
                        data[mask] = target
                        tile.pixels = pixels_to_rows(data)
        for layer in layers:
            visited = set()
            for f in selected_frames:
                from cybersprite.core.references import cel_at, cel_owner

                owner = cel_owner(layer, cel_at(layer, f))
                key = owner.frame if owner else f
                if key in visited:
                    continue
                visited.add(key)
                frame_image = canvas_pixels(p, layer, f)
                mask = region(p, a.region, frame_image) & (frame_image == source)
                count += write_points(
                    ctx,
                    layer,
                    f,
                    ((int(x), int(y), target) for y, x in zip(*np.nonzero(mask), strict=True)),
                )
        return {"pixels_written": count}
    layer = image_layer(p, a.layer)
    frame_index(p, a.frame)

    def image():
        return canvas_pixels(p, layer, a.frame)

    if name == "set_pixel":
        points = [(a.x, a.y, resolve_color(p.palette, a.color))]
    elif name == "set_pixels":
        if (a.pixels is None) == (a.points is None):
            raise invalid("Provide either pixels, or points with color.")
        raw = a.pixels
        if raw is None:
            if a.color is None:
                raise invalid("points requires color.")
            raw = [[x, y, a.color] for x, y in a.points]
        if len(raw) > 65536:
            fail("E_LIMIT_EXCEEDED", "set_pixels accepts at most 65536 points.", limit=65536)
        points = []
        for item in raw:
            if len(item) != 3 or type(item[0]) is not int or type(item[1]) is not int:
                raise invalid("Each pixel must be [integer x, integer y, color].")
            points.append((item[0], item[1], resolve_color(p.palette, item[2])))
    elif name == "draw_rows":
        data = rows(p, a.rows, a.format)
        points = [
            (a.x + x, a.y + y, int(value))
            for y, row in enumerate(data)
            for x, value in enumerate(row)
            if not a.skip_transparent or value != p.palette.transparent_index
        ]
    elif name in ("line", "rect", "ellipse", "polygon", "stroke"):
        if name == "line":
            coords = raster.line_points(a.x0, a.y0, a.x1, a.y1)
        elif name in ("rect", "ellipse"):
            coords = getattr(raster, name + "_points")(a.x, a.y, a.w, a.h, a.filled)
        elif name == "polygon":
            coords = raster.polygon_points(a.points, a.closed, a.filled)
        else:
            coords = raster.stroke_path(a.points, a.pixel_perfect, brush_size=a.brush.size)
        color = resolve_color(p.palette, a.color)
        points = [(x, y, color) for x, y in raster.stamp(coords, a.brush.model_dump())]
    elif name in ("fill", "erase", "outline"):
        data = image()
        if name == "fill":
            sample = render_indexed(p, a.frame) if a.sample == "composite" else data
            mask = raster.flood_fill_mask(sample, a.x, a.y, a.connectivity)
        elif name == "erase":
            mask = region(p, a.region, data)
        else:
            mask = raster.outline_mask(
                data != p.palette.transparent_index, a.placement, a.connectivity
            ) & region(p, a.region, data)
        color = (
            p.palette.transparent_index if name == "erase" else resolve_color(p.palette, a.color)
        )
        points = [(int(x), int(y), color) for y, x in zip(*np.nonzero(mask), strict=True)]
    elif name == "transform_region":
        data = image()
        mask = region(p, a.region, data)
        ys, xs = np.nonzero(mask)
        if not len(xs):
            return {"pixels_written": 0}
        x, y, w, h = (
            int(xs.min()),
            int(ys.min()),
            int(xs.max() - xs.min() + 1),
            int(ys.max() - ys.min() + 1),
        )
        block, selected = raster.transform_block(
            data[y : y + h, x : x + w], mask[y : y + h, x : x + w], a.flip, a.rotate
        )
        target = image_layer(p, a.target_layer or a.layer)
        target_frame = a.frame if a.target_frame is None else frame_index(p, a.target_frame)
        unlocked(p, target)
        from cybersprite.core.references import cel_at, cel_owner

        source_owner = cel_owner(layer, cel_at(layer, a.frame))
        target_owner = cel_owner(target, cel_at(target, target_frame))
        shared = layer is target and source_owner is not None and source_owner is target_owner
        target_before = canvas_pixels(p, target, target_frame)
        if a.action == "move":
            write_points(
                ctx,
                layer,
                a.frame,
                (
                    (int(px), int(py), p.palette.transparent_index)
                    for py, px in zip(ys, xs, strict=True)
                ),
            )
        points = [
            (x + a.dx + px, y + a.dy + py, int(value))
            for py, row in enumerate(block)
            for px, value in enumerate(row)
            if selected[py, px]
            and (a.overwrite_transparent or value != p.palette.transparent_index)
        ]
        write_points(ctx, target, target_frame, points)
        count = int(np.count_nonzero(canvas_pixels(p, target, target_frame) != target_before))
        if a.action == "move" and not shared:
            count += int(np.count_nonzero(canvas_pixels(p, layer, a.frame) != data))
        return {"pixels_written": count}
    else:
        raise invalid("Unknown drawing operation.", name=name)
    return {"pixels_written": write_points(ctx, layer, a.frame, points)}
