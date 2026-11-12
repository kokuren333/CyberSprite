"""Pure cel normalization for later transaction commits; never persists projects."""

from copy import deepcopy
from typing import Any

import numpy as np

from .errors import CyberSpriteError
from .models import GroupLayer, ImageLayer, LinkCel, Project, TilemapLayer
from .pixels import pixels_from_rows, pixels_to_rows, tiles_from_rows, tiles_to_rows
from .references import walk_layers


def normalize_cels(project: Project) -> Project:
    result = deepcopy(project)
    ti = result.palette.transparent_index
    tilesets = {ts.id: ts for ts in result.tilesets}
    for layer, _ancestors in walk_layers(result.layers):
        if isinstance(layer, GroupLayer):
            continue
        by_frame = {cel.frame: cel for cel in layer.cels}
        if len(by_frame) != len(layer.cels):
            raise CyberSpriteError(
                "E_INVARIANT",
                "Cannot normalize duplicate cel frames.",
                "Remove duplicate frame entries before normalization.",
                {"rule": "S-04", "layer": layer.id},
            )
        groups: dict[int, list[int]] = {}
        for frame in sorted(by_frame):
            owner = by_frame[frame]
            seen = set()
            while isinstance(owner, LinkCel):
                if owner.frame in seen or owner.link not in by_frame:
                    raise CyberSpriteError(
                        "E_INVARIANT",
                        "Cannot normalize broken or cyclic links.",
                        "Point each link chain to a data cel in the same layer.",
                        {"rule": "S-05", "layer": layer.id, "frame": frame},
                    )
                seen.add(owner.frame)
                owner = by_frame[owner.link]
            groups.setdefault(owner.frame, []).append(frame)
        normalized = []
        for old_owner in sorted(groups):
            members = groups[old_owner]
            owner = deepcopy(by_frame[old_owner])
            data: Any
            if not (isinstance(layer, ImageLayer) and layer.background):
                if isinstance(layer, ImageLayer):
                    data = pixels_from_rows(owner.pixels, owner.w, owner.h)
                    mask = data != ti
                    step_x = step_y = 1
                else:
                    data = tiles_from_rows(owner.tiles, owner.w, owner.h)
                    mask = np.array([[ref.index != 0 for ref in row] for row in data], dtype=bool)
                    ts = tilesets[layer.tileset]
                    step_x, step_y = ts.tile_w, ts.tile_h
                ys, xs = np.nonzero(mask)
                if not len(xs):
                    continue
                left, top, right, bottom = (
                    int(xs.min()),
                    int(ys.min()),
                    int(xs.max()) + 1,
                    int(ys.max()) + 1,
                )
                owner.x += left * step_x
                owner.y += top * step_y
                owner.w, owner.h = right - left, bottom - top
                if isinstance(layer, TilemapLayer):
                    owner.tiles = tiles_to_rows([row[left:right] for row in data[top:bottom]])
                else:
                    owner.pixels = pixels_to_rows(data[top:bottom, left:right])
            first = min(members)
            owner.frame = first
            owner.z_index = by_frame[first].z_index
            normalized.append(owner)
            normalized.extend(
                LinkCel(frame=frame, link=first, z_index=by_frame[frame].z_index)
                for frame in sorted(members)
                if frame != first
            )
        layer.cels = sorted(normalized, key=lambda cel: cel.frame)
    return result
