"""Read contracts and new-project construction; no existing project writes here."""

from pathlib import Path

import numpy as np

from cybersprite.core import history
from cybersprite.core.errors import invalid
from cybersprite.core.models import GroupLayer, ImageCel, ImageLayer, LinkCel, Sources
from cybersprite.core.pixels import pixels_to_rows, resolve_color
from cybersprite.core.projects import new_project
from cybersprite.core.quality import report
from cybersprite.core.references import cel_at, cel_owner, walk_layers
from cybersprite.core.render import render_indexed
from cybersprite.formats.palette_files import raw_color, read_palette_with_names

from .common import SYMBOLS, array, fail, frame_index, frames, groups, image_layer
from .palette import usage
from .previews import diff, previews


def summary(p, root):
    return {
        "name": p.name,
        "width": p.canvas.width,
        "height": p.canvas.height,
        "frames": len(p.frames),
        "layers": sum(1 for _ in walk_layers(p.layers)),
        "palette_size": len(p.palette.colors),
        "transparent_index": p.palette.transparent_index,
        "revision": p.revision,
        "tags": [tag.name for tag in p.tags],
        "validation_ok": report(p, root=root)["ok"],
    }


def construct(a, root):
    colors, names = (
        read_palette_with_names(a.palette)
        if isinstance(a.palette, str)
        else ([raw_color(c) for c in a.palette], {})
    )
    p = new_project(
        width=a.width,
        height=a.height,
        frames=a.frames,
        duration=a.duration_ms,
        name=a.name or Path(root).stem,
        palette=colors,
    )
    if not 0 <= a.transparent_index < len(colors):
        fail("E_INDEX_OUT_OF_RANGE", "Transparent index is outside the palette.")
    p.palette.transparent_index = a.transparent_index
    p.palette.names = names
    p.layers[0].name = a.layer_name
    if a.background is not None:
        value = resolve_color(p.palette, a.background)
        bg = ImageLayer(
            id=p.id_counters.issue("layer"),
            name="Background",
            background=True,
            cels=[
                ImageCel(
                    frame=f,
                    x=0,
                    y=0,
                    w=a.width,
                    h=a.height,
                    pixels=[f"{value:02x}" * a.width] * a.height,
                )
                for f in range(a.frames)
            ],
        )
        p.layers.insert(0, bg)
    return p


def query(ctx, a, name):
    p, root = ctx.project, ctx.root
    if name == "get_info":
        result = {}
        for section in a.include:
            if section == "summary":
                result[section] = summary(p, root)
            elif section == "layers":

                def node(layer):
                    value = layer.model_dump(by_alias=True, exclude_none=True)
                    if isinstance(layer, GroupLayer):
                        value["children"] = [node(child) for child in layer.children]
                    else:
                        value["cels"] = []
                        for cel in layer.cels:
                            owner = cel_owner(layer, cel)
                            value["cels"].append(
                                {
                                    "frame": cel.frame,
                                    "x": owner.x,
                                    "y": owner.y,
                                    "w": owner.w,
                                    "h": owner.h,
                                    "z_index": cel.z_index,
                                    **({"link": owner.frame} if isinstance(cel, LinkCel) else {}),
                                }
                            )
                        value["link_groups"] = sorted(
                            sorted(members) for _, members in groups(layer) if len(members) > 1
                        )
                    return value

                result[section] = [node(layer) for layer in p.layers]
            elif section == "palette":
                result[section] = p.palette.model_dump()
            elif section == "validation":
                result[section] = report(p, root=root)
            elif section == "history":
                result[section] = history.history_result(root)
            elif section == "sources":
                path = root / "source/manifest.json"
                result[section] = (
                    Sources.model_validate_json(path.read_bytes()).model_dump()
                    if path.exists()
                    else {"sources": []}
                )
            else:
                result[section] = [
                    item.model_dump(by_alias=True, exclude_none=True)
                    for item in getattr(p, section)
                ]
        return result
    if name == "get_palette":
        counts = usage(p)
        return {
            "transparent_index": p.palette.transparent_index,
            "frozen": p.palette.frozen,
            "colors": [
                {
                    "index": i,
                    "color": c,
                    "name": p.palette.names.get(str(i)),
                    "used_pixels": counts[i],
                }
                for i, c in enumerate(p.palette.colors)
            ],
        }
    if name == "validate":
        return report(p, root=root, selected_frames=frames(p, a.frames), rules=a.rules)
    if name == "get_history":
        return history.history_result(root, a.limit)
    if name == "render_preview":
        if a.tileset is None and isinstance(a.frames, list) and not a.frames:
            raise invalid("Preview requires at least one frame.")
        return previews(
            p,
            frames(p, a.frames) if a.tileset is None else [],
            root,
            inline=a.inline,
            tileset=a.tileset,
            layout=a.layout,
            scale=a.scale,
            grid=a.grid,
            rulers=a.rulers,
            onion=a.onion.model_dump() if a.onion else None,
            rect=a.rect.model_dump() if a.rect else None,
            guide=a.guide.model_dump() if a.guide else None,
            background=a.background,
            layers=a.layers,
        )
    if name == "diff_preview":
        return diff(
            p,
            root,
            p.revision - 1 if a.from_revision is None else a.from_revision,
            p.revision if a.to_revision is None else a.to_revision,
            a.frames,
            a.inline,
        )
    frame_index(p, a.frame)
    if a.layer == "@composite":
        data = render_indexed(p, a.frame)
        x = y = 0
    else:
        layer = image_layer(p, a.layer, edit=False)
        cel = cel_owner(layer, cel_at(layer, a.frame))
        if cel is None:
            fail("E_CEL_NOT_FOUND", "No cel exists at the requested layer and frame.")
        data, x, y = array(cel), cel.x, cel.y
    if a.rect is not None:
        rect = a.rect
        if rect.w < 1 or rect.h < 1:
            raise invalid("Pixel read rectangle must have positive dimensions.")
        if rect.w * rect.h > 65536:
            fail(
                "E_LIMIT_EXCEEDED",
                "get_pixels reads at most 65536 pixels; narrow rect.",
                limit=65536,
            )
        output = np.full((rect.h, rect.w), p.palette.transparent_index, dtype=np.uint8)
        x0, y0 = max(x, rect.x), max(y, rect.y)
        x1, y1 = min(x + data.shape[1], rect.x + rect.w), min(y + data.shape[0], rect.y + rect.h)
        if x0 < x1 and y0 < y1:
            output[y0 - rect.y : y1 - rect.y, x0 - rect.x : x1 - rect.x] = data[
                y0 - y : y1 - y, x0 - x : x1 - x
            ]
        data, x, y = output, rect.x, rect.y
    if data.size > 65536:
        fail(
            "E_LIMIT_EXCEEDED",
            "get_pixels reads at most 65536 pixels; specify a smaller rect.",
            limit=65536,
        )
    result = {"x": x, "y": y, "w": data.shape[1], "h": data.shape[0], "rows": pixels_to_rows(data)}
    if a.format == "sym":
        if len(p.palette.colors) > 62:
            raise invalid("Symbol output requires at most 62 palette colors.")
        result["rows"] = [
            "".join("." if i == p.palette.transparent_index else SYMBOLS[i] for i in row)
            for row in data
        ]
        result["legend"] = {
            "." if i == p.palette.transparent_index else SYMBOLS[i]: i
            for i in range(len(p.palette.colors))
        }
    values, counts = np.unique(data, return_counts=True)
    result["used"] = [
        {"index": int(i), "color": p.palette.colors[i], "count": int(n)}
        for i, n in zip(values, counts, strict=True)
    ]
    return result
