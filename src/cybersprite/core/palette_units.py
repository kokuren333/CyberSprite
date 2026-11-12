"""Strict per-resource local palette row closure for hardware constraints."""

from collections.abc import Iterable

import numpy as np

from .models import GroupLayer, ImageLayer
from .pixels import pixels_from_rows, tiles_from_rows
from .references import cel_owner, walk_layers


def resources(p, *, selected_layer=None, selected_frame=None, include_tilesets=True):
    """Yield original indexed units, including hidden and unused data."""
    for layer, _ in walk_layers(p.layers):
        if (
            isinstance(layer, GroupLayer)
            or selected_layer is not None
            and layer.id != selected_layer
        ):
            continue
        for cel in layer.cels:
            if selected_frame is not None and cel.frame != selected_frame:
                continue
            owner = cel_owner(layer, cel)
            if isinstance(layer, ImageLayer):
                yield (
                    pixels_from_rows(owner.pixels, owner.w, owner.h),
                    owner.x,
                    owner.y,
                    dict(layer=layer.id, frames=[cel.frame]),
                )
            else:
                ts = next(t for t in p.tilesets if t.id == layer.tileset)
                refs = tiles_from_rows(owner.tiles, owner.w, owner.h)
                for y, row in enumerate(refs):
                    for x, ref in enumerate(row):
                        data = pixels_from_rows(ts.tiles[ref.index].pixels, ts.tile_w, ts.tile_h)
                        if ref.d and ts.tile_w == ts.tile_h:
                            data = data.T
                        if ref.x:
                            data = data[:, ::-1]
                        if ref.y:
                            data = data[::-1]
                        yield (
                            data,
                            owner.x + x * ts.tile_w,
                            owner.y + y * ts.tile_h,
                            dict(layer=layer.id, frames=[cel.frame]),
                        )
    for ts in p.tilesets if include_tilesets else []:
        for index, tile in enumerate(ts.tiles[1:], 1):
            yield (
                pixels_from_rows(tile.pixels, ts.tile_w, ts.tile_h),
                0,
                0,
                dict(layer=None, frames=[], tileset=ts.id, tile=index),
            )


def violations(p):
    spec = p.platform.system.palette
    if spec is None:
        return []
    ti, found = p.palette.transparent_index, []
    tile = p.platform.system.tile
    block = spec.block if spec.unit == "block" else tile if spec.unit == "tile" else None
    if spec.unit in ("tile", "block") and block is None:
        return []  # Invalid combinations are rejected by the platform schema.
    units: dict[tuple, dict] = {}
    origins: Iterable[tuple[int, int]]
    for image, ox, oy, resource in resources(p):
        h, w = image.shape
        if block:
            origins = (
                (x, y)
                for y in range(oy // block.h * block.h, oy + h, block.h)
                for x in range(ox // block.w * block.w, ox + w, block.w)
            )
        else:
            origins = [(ox, oy)]
        for x, y in origins:
            cw, ch = (block.w, block.h) if block else (w, h)
            data = image[max(0, y - oy) : min(h, y + ch - oy), max(0, x - ox) : min(w, x + cw - ox)]
            indices = [int(v) for v in np.unique(data)]
            key = (
                resource["layer"] or "",
                tuple(resource["frames"]),
                resource.get("tileset", ""),
                resource.get("tile", -1),
                x if block else 0,
                y if block else 0,
            )
            unit = units.setdefault(
                key, dict(resource=resource, bbox=dict(x=x, y=y, w=cw, h=ch), indices=set())
            )
            unit["indices"].update(indices)
            if not block:
                box = unit["bbox"]
                right, bottom = max(box["x"] + box["w"], x + cw), max(box["y"] + box["h"], y + ch)
                box["x"], box["y"] = min(box["x"], x), min(box["y"], y)
                box["w"], box["h"] = right - box["x"], bottom - box["y"]
    for key in sorted(units):
        unit = units[key]
        indices = sorted(unit["indices"])
        opaque = [i for i in indices if i != ti]
        offset = 1 if spec.slot0 == "color" else 0
        rows = sorted({(i - offset) // spec.row_size for i in opaque})
        forbidden = (
            [i for i in opaque if i % spec.row_size == 0]
            if spec.slot0 != "color"
            else ([ti] if ti in indices else [])
        )
        outside = [i for i in opaque if not 0 <= (i - offset) // spec.row_size < spec.rows]
        if len(rows) > 1 or forbidden or outside:
            found.append(
                dict(
                    **unit["resource"],
                    bbox=unit["bbox"],
                    rows=rows,
                    forbidden_indices=forbidden,
                    outside_indices=outside,
                )
            )
    return found
