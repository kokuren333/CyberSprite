"""Indexed tile editing, stable renumbering, and deterministic image decomposition."""

from copy import deepcopy
from dataclasses import replace

import numpy as np

from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.models import LinkCel, Tile, TileCel, TilemapLayer, Tileset
from cybersprite.core.pixels import (
    TileRef,
    parse_tile,
    pixels_to_rows,
    tiles_from_rows,
    tiles_to_rows,
)
from cybersprite.core.references import cel_at, cel_owner, resolve_layer, walk_layers

from .common import array, fail, frame_index, image_layer, rows, siblings, unlocked


def resolve_tileset(p, reference):
    matches = [ts for ts in p.tilesets if ts.id == reference]
    if not matches:
        matches = [ts for ts in p.tilesets if ts.name == reference]
    if len(matches) == 1:
        return matches[0]
    raise CyberSpriteError(
        "E_AMBIGUOUS_REF" if matches else "E_TILESET_NOT_FOUND",
        f"Tileset reference {reference!r} is ambiguous or missing.",
        "Use an exact tileset ID from get_info(include=['tilesets']).",
        {"reference": reference, "candidates": [{"id": t.id, "name": t.name} for t in p.tilesets]},
    )


def tile_layers(p, ts, *, edit=False):
    for layer, _ in walk_layers(p.layers):
        if isinstance(layer, TilemapLayer) and layer.tileset == ts.id:
            if edit:
                unlocked(p, layer)
            yield layer


def tile_index(ts, index, *, empty=True):
    if not 0 <= index < len(ts.tiles):
        raise invalid("Tile index is outside the tileset.", tile=index, tiles=len(ts.tiles))
    if not empty and index == 0:
        raise invalid("Empty tile 0 cannot be edited, deleted, or moved.")
    return index


def new_tileset(p, name, w, h, **options):
    if len(p.tilesets) >= 64:
        fail("E_LIMIT_EXCEEDED", "A project can contain at most 64 tilesets.", limit=64)
    ts = Tileset(
        id=p.id_counters.issue("tileset"),
        name=name,
        tile_w=w,
        tile_h=h,
        tiles=[Tile(pixels=[f"{p.palette.transparent_index:02x}" * w] * h)],
        **options,
    )
    p.tilesets.append(ts)
    return ts


def append_tile(ts, values):
    if len(ts.tiles) >= 65536:
        fail("E_LIMIT_EXCEEDED", "A tileset can contain at most 65536 tiles.", limit=65536)
    ts.tiles.append(Tile(pixels=values))
    return len(ts.tiles) - 1


def remap_tiles(p, ts, mapping):
    for layer in tile_layers(p, ts, edit=True):
        for cel in layer.cels:
            if isinstance(cel, LinkCel):
                continue
            refs = tiles_from_rows(cel.tiles, cel.w, cel.h)
            cel.tiles = tiles_to_rows(
                [
                    [
                        replace(ref, index=mapping[ref.index]) if mapping[ref.index] else TileRef(0)
                        for ref in row
                    ]
                    for row in refs
                ]
            )


def tile_target(p, a, *, edit):
    layer = resolve_layer(p, a.layer)
    if not isinstance(layer, TilemapLayer):
        fail("E_WRONG_LAYER_TYPE", "Tile operations require a tilemap layer.", type=layer.type)
    assert isinstance(layer, TilemapLayer)
    if edit:
        unlocked(p, layer)
    frame_index(p, a.frame)
    ts = resolve_tileset(p, layer.tileset)
    owner = cel_owner(layer, cel_at(layer, a.frame))
    ox, oy = (owner.x % ts.tile_w, owner.y % ts.tile_h) if owner else (0, 0)
    return layer, ts, owner, ox, oy


def check_rect(p, ts, ox, oy, col, row, w, h):
    columns = (p.canvas.width - ox + ts.tile_w - 1) // ts.tile_w
    height = (p.canvas.height - oy + ts.tile_h - 1) // ts.tile_h
    if col < 0 or row < 0 or w < 1 or h < 1 or col + w > columns or row + h > height:
        fail(
            "E_OUT_OF_CANVAS",
            "Tile rectangle is outside the canvas grid.",
            col=col,
            row=row,
            w=w,
            h=h,
            columns=columns,
            rows=height,
        )


def get_tiles(ctx, a):
    p = ctx.project
    _layer, ts, owner, ox, oy = tile_target(p, a, edit=False)
    if a.rect is None:
        return dict(
            col=(owner.x - ox) // ts.tile_w if owner else 0,
            row=(owner.y - oy) // ts.tile_h if owner else 0,
            w=owner.w if owner else 0,
            h=owner.h if owner else 0,
            rows=list(owner.tiles) if owner else [],
            tileset=ts.id,
        )
    r = a.rect
    check_rect(p, ts, ox, oy, r.x, r.y, r.w, r.h)
    result = [[TileRef(0) for _ in range(r.w)] for _ in range(r.h)]
    if owner:
        left, top = (owner.x - ox) // ts.tile_w, (owner.y - oy) // ts.tile_h
        for y, row in enumerate(tiles_from_rows(owner.tiles, owner.w, owner.h)):
            for x, ref in enumerate(row):
                if r.x <= left + x < r.x + r.w and r.y <= top + y < r.y + r.h:
                    result[top + y - r.y][left + x - r.x] = ref
    return dict(col=r.x, row=r.y, w=r.w, h=r.h, rows=tiles_to_rows(result), tileset=ts.id)


def set_tiles(ctx, a, name):
    p = ctx.project
    layer, ts, owner, ox, oy = tile_target(p, a, edit=True)
    if name == "set_tile":
        tile_index(ts, a.tile)
        values = [[parse_tile(str(a.tile) + a.flip)]]
    else:
        if not a.rows or not a.rows[0].split():
            raise invalid("Tile rows must be nonempty rectangular reference rows.")
        values = tiles_from_rows(a.rows, len(a.rows[0].split()), len(a.rows))
        for row in values:
            for ref in row:
                tile_index(ts, ref.index)
    w, h = len(values[0]), len(values)
    check_rect(p, ts, ox, oy, a.col, a.row, w, h)
    left, top, right, bottom = a.col, a.row, a.col + w, a.row + h
    if owner:
        col, row = (owner.x - ox) // ts.tile_w, (owner.y - oy) // ts.tile_h
        left, top = min(left, col), min(top, row)
        right, bottom = max(right, col + owner.w), max(bottom, row + owner.h)
    refs = [[TileRef(0) for _ in range(right - left)] for _ in range(bottom - top)]
    if owner:
        for y, entries in enumerate(tiles_from_rows(owner.tiles, owner.w, owner.h)):
            refs[row - top + y][col - left : col - left + owner.w] = entries
    before = deepcopy(refs)
    for y, entries in enumerate(values):
        refs[a.row - top + y][a.col - left : a.col - left + w] = entries
    if refs == before:
        return {}
    if owner is None:
        owner = TileCel(frame=a.frame, x=0, y=0, w=1, h=1, tiles=["0"])
        layer.cels.append(owner)
        layer.cels.sort(key=lambda c: c.frame)
    else:
        linked = [
            c.frame
            for c in layer.cels
            if c is owner or isinstance(c, LinkCel) and c.link == owner.frame
        ]
        if len(linked) > 1:
            ctx.linked_frames.update(linked)
    owner.x, owner.y = ox + left * ts.tile_w, oy + top * ts.tile_h
    owner.w, owner.h = right - left, bottom - top
    owner.tiles = tiles_to_rows(refs)
    return {}


def from_layer(ctx, a):
    p = ctx.project
    layer = image_layer(p, a.layer)
    if layer.background:
        raise invalid("Convert the background to a normal image layer with update_layer first.")
    ts = new_tileset(
        p,
        a.name if a.name is not None else layer.name,
        a.tile_w,
        a.tile_h,
        match_flips=a.match_flips,
    )
    lookup = {tuple(ts.tiles[0].pixels): TileRef(0)}

    def remember(index, data):
        # Lowest tile index, then '', x, y, xy, d, xd, yd, xyd wins an exact tie.
        for d in (False, True) if a.match_flips.d and ts.tile_w == ts.tile_h else (False,):
            for y in (False, True) if a.match_flips.y else (False,):
                for x in (False, True) if a.match_flips.x else (False,):
                    variant = data.T if d else data
                    if x:
                        variant = variant[:, ::-1]
                    if y:
                        variant = variant[::-1]
                    lookup.setdefault(tuple(pixels_to_rows(variant)), TileRef(index, x, y, d))

    cels: list[TileCel | LinkCel] = []
    for cel in sorted(layer.cels, key=lambda c: c.frame):
        if isinstance(cel, LinkCel):
            cels.append(deepcopy(cel))
            continue
        data = array(cel)
        w, h = (cel.w + ts.tile_w - 1) // ts.tile_w, (cel.h + ts.tile_h - 1) // ts.tile_h
        padded = np.full(
            (h * ts.tile_h, w * ts.tile_w), p.palette.transparent_index, dtype=np.uint8
        )
        padded[: cel.h, : cel.w] = data
        refs = []
        for row in range(h):
            entries = []
            for col in range(w):
                block = padded[
                    row * ts.tile_h : (row + 1) * ts.tile_h, col * ts.tile_w : (col + 1) * ts.tile_w
                ]
                values = tuple(pixels_to_rows(block))
                if values not in lookup:
                    remember(append_tile(ts, list(values)), block)
                entries.append(lookup[values])
            refs.append(entries)
        cels.append(
            TileCel(
                **cel.model_dump(exclude={"pixels", "w", "h"}), w=w, h=h, tiles=tiles_to_rows(refs)
            )
        )
    replacement = TilemapLayer(
        **layer.model_dump(exclude={"type", "background", "cels"}), tileset=ts.id, cels=cels
    )
    items = siblings(p, layer)
    items[items.index(layer)] = replacement
    return {"tileset": ts.id, "tiles": len(ts.tiles)}


def tile_op(ctx, a, name):
    p = ctx.project
    if name == "get_tiles":
        return get_tiles(ctx, a)
    if name in ("set_tile", "set_tiles"):
        return set_tiles(ctx, a, name)
    if name == "tileset_from_layer":
        return from_layer(ctx, a)
    if name == "add_tileset":
        matches = [ts for ts in p.tilesets if ts.name == a.name]
        if matches and a.if_exists != "allow":
            if a.if_exists == "reuse":
                return {"id": matches[0].id}
            fail("E_EXISTS", "Tileset name already exists.", id=matches[0].id)
        return {"id": new_tileset(p, a.name, a.tile_w, a.tile_h, base_index=a.base_index).id}
    ts = resolve_tileset(p, a.tileset)
    list(tile_layers(p, ts, edit=True))
    if name == "set_tile_pixels":
        data = rows(p, a.rows, a.format)
        if data.shape != (ts.tile_h, ts.tile_w):
            raise invalid(
                "Tile rows must match tile_w and tile_h exactly.",
                tile_w=ts.tile_w,
                tile_h=ts.tile_h,
            )
        values = pixels_to_rows(data)
        if a.tile == "new":
            index = append_tile(ts, values)
        else:
            index = tile_index(ts, a.tile, empty=False)
            ts.tiles[index].pixels = values
        return {"tile": index}
    if name == "delete_tiles":
        deleted = set(a.tiles)
        for index in sorted(deleted):
            tile_index(ts, index, empty=False)
        used = sorted(
            {
                ref.index
                for layer in tile_layers(p, ts)
                for cel in layer.cels
                if not isinstance(cel, LinkCel)
                for row in tiles_from_rows(cel.tiles, cel.w, cel.h)
                for ref in row
                if ref.index in deleted
            }
        )
        if used and a.on_used == "error":
            raise invalid(
                "Tiles are in use; use on_used='clear' to clear their placements.",
                tiles=used,
                tileset=ts.id,
            )
        order = [i for i in range(len(ts.tiles)) if i not in deleted]
    else:
        start, end = tile_index(ts, a.from_, empty=False), tile_index(ts, a.to, empty=False)
        if start > end or not 1 <= a.before <= len(ts.tiles):
            raise invalid("Use from <= to and before between 1 and the tileset size.")
        order = list(range(len(ts.tiles)))
        if not start <= a.before <= end + 1:
            moving = order[start : end + 1]
            order = order[:start] + order[end + 1 :]
            position = a.before - (len(moving) if a.before > end else 0)
            order[position:position] = moving
    mapping = {i: 0 for i in range(len(ts.tiles))}
    mapping.update({old: new for new, old in enumerate(order)})
    remap_tiles(p, ts, mapping)
    ts.tiles = [ts.tiles[i] for i in order]
    return (
        {"mapping": {str(i): mapping[i] for i in sorted(mapping)}} if name == "move_tiles" else {}
    )
