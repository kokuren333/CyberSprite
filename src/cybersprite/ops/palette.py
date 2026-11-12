"""Palette mutation and index remapping; edits never silently quantize colors."""

from collections import Counter
from functools import cmp_to_key

import numpy as np

from cybersprite.core.color import compare_hue, rgb_to_oklab_fixed
from cybersprite.core.errors import invalid
from cybersprite.core.models import ImageLayer, LinkCel, Palette
from cybersprite.core.pixels import pixels_from_rows, pixels_to_rows, rgb_distance, rgba
from cybersprite.core.references import walk_layers
from cybersprite.formats.palette_files import raw_color, read_palette_with_names

from .common import fail


def pixel_objects(p):
    for layer, _ in walk_layers(p.layers):
        if isinstance(layer, ImageLayer):
            for cel in layer.cels:
                if not isinstance(cel, LinkCel):
                    yield cel
    for ts in p.tilesets:
        yield from ts.tiles


def usage(p):
    result: Counter[int] = Counter()
    for obj in pixel_objects(p):
        result.update(bytes.fromhex("".join(obj.pixels)))
    return result


def remap_pixels(p, mapping):
    table = np.arange(256, dtype=np.uint8)
    for old, new in sorted(mapping.items()):
        table[old] = new
    for obj in pixel_objects(p):
        data = pixels_from_rows(obj.pixels, len(obj.pixels[0]) // 2, len(obj.pixels))
        obj.pixels = pixels_to_rows(table[data])


def palette_op(ctx, a, name):
    p = ctx.project
    pal = p.palette
    if name == "set_palette_frozen":
        pal.frozen = a.frozen
        return {}
    if pal.frozen:
        fail("E_PALETTE_FROZEN", "Palette is frozen; unfreeze it before editing.")
    if name == "load_palette":
        from .args import ARGS

        colors, names = read_palette_with_names(a.source)
        if a.mode == "append":
            palette_op(
                ctx, ARGS["add_palette_colors"](colors=colors, names=names), "add_palette_colors"
            )
            return {}
        return palette_op(
            ctx,
            ARGS["set_palette"](colors=colors, names=names, on_shrink=a.on_shrink),
            "set_palette",
        )
    if name == "set_palette":
        colors = [raw_color(c) for c in a.colors]
        if not 1 <= len(colors) <= 256:
            fail("E_LIMIT_EXCEEDED", "Palette must contain 1..256 colors.", limit=256)
        ti = pal.transparent_index if a.transparent_index is None else a.transparent_index
        if not 0 <= ti < len(colors):
            fail("E_INDEX_OUT_OF_RANGE", "Transparent index is outside the new palette.")
        out = [i for i in sorted(usage(p)) if i >= len(colors)]
        mapping = {}
        for i in out:
            if a.on_shrink == "error":
                fail(
                    "E_INDEX_OUT_OF_RANGE",
                    "Palette shrink would leave out-of-range pixels.",
                    index=i,
                )
            if a.on_shrink == "to_transparent" or i == pal.transparent_index:
                mapping[i] = ti
            else:
                candidates = [
                    j for j, color in enumerate(colors) if j != ti and rgba(color)[3] == 255
                ]
                if not candidates:
                    raise invalid(
                        "remap_nearest requires at least one opaque non-transparent palette entry."
                    )
                mapping[i] = min(
                    candidates,
                    key=lambda j: (rgb_distance(rgba(pal.colors[i]), rgba(colors[j])), j),
                )
        remap_pixels(p, mapping)
        for ts in p.tilesets:
            ts.tiles[0].pixels = [f"{ti:02x}" * ts.tile_w] * ts.tile_h
        names = (
            a.names
            if a.names is not None
            else {k: v for k, v in pal.names.items() if int(k) < len(colors)}
        )
        if any(int(k) >= len(colors) for k in names):
            raise invalid("Palette names must refer to indices in the new palette.")
        p.palette = Palette(colors=colors, names=names, transparent_index=ti)
        return {}
    if name == "set_palette_color":
        if not 0 <= a.index < len(pal.colors):
            fail("E_INDEX_OUT_OF_RANGE", "Palette index is outside the palette.", index=a.index)
        pal.colors[a.index] = raw_color(a.color)
        if a.name is not None:
            pal.names[str(a.index)] = a.name
        return {}
    if name == "add_palette_colors":
        result = []
        for pos, color in enumerate(a.colors):
            color = raw_color(color)
            if a.reuse_existing and color in pal.colors:
                index = pal.colors.index(color)
            else:
                if len(pal.colors) == 256:
                    fail("E_LIMIT_EXCEEDED", "Palette cannot exceed 256 colors.", limit=256)
                index = len(pal.colors)
                pal.colors.append(color)
            result.append(index)
            if a.names is not None and str(pos) in a.names:
                pal.names[str(index)] = a.names[str(pos)]
        return {"indices": result}
    choices = (
        int(a.order is not None) + int(a.sort_by is not None) + a.merge_duplicates + a.remove_unused
    )
    if choices != 1:
        raise invalid("Specify exactly one of order, sort_by, merge_duplicates, remove_unused.")
    counts = usage(p)
    order = list(range(len(pal.colors)))
    mapping = {}
    if a.order is not None:
        if sorted(a.order) != order:
            raise invalid("order must be a permutation of every old palette index.")
        order = list(a.order)
    elif a.sort_by is not None:
        labs = [rgb_to_oklab_fixed(rgba(c)[:3]) for c in pal.colors]
        if a.sort_by == "hue":

            def hue_compare(i: int, j: int) -> int:
                return compare_hue(labs[i], labs[j]) or (i > j) - (i < j)

            order.sort(key=cmp_to_key(hue_compare))
        elif a.sort_by == "lightness":
            order.sort(key=lambda i: (labs[i][0], i))
        else:
            order.sort(key=lambda i: (-counts[i], i))
    elif a.merge_duplicates:
        unique = {}
        order = []
        for i, color in enumerate(pal.colors):
            # Transparent semantics must remain distinct from identical opaque indices.
            key = (color, i == pal.transparent_index)
            if key not in unique:
                unique[key] = i
                order.append(i)
            mapping[i] = unique[key]
    else:
        order = [i for i in order if counts[i] or i == pal.transparent_index]
    if a.keep_transparent_first:
        order.remove(pal.transparent_index)
        order.insert(0, pal.transparent_index)
    positions = {old: new for new, old in enumerate(order)}
    mapping = {
        i: positions[mapping.get(i, i)] if mapping.get(i, i) in positions else 0
        for i in range(len(pal.colors))
    }
    removed = sorted(i for i in mapping if i not in positions and a.remove_unused)
    remap_pixels(p, mapping)
    oldnames = pal.names
    pal.colors = [pal.colors[i] for i in order]
    pal.names = {
        str(mapping[int(k)]): oldnames[k] for k in sorted(oldnames, key=int) if int(k) in positions
    }
    pal.transparent_index = mapping[pal.transparent_index]
    return {
        "mapping": {str(i): None if i in removed else mapping[i] for i in sorted(mapping)},
        "palette_size": len(pal.colors),
    }
