"""Pure cel normalization for later transaction commits; never persists projects."""

from copy import deepcopy
from functools import lru_cache
from typing import Any

import numpy as np

from .errors import CyberSpriteError
from .models import GroupLayer, ImageLayer, LinkCel, Project
from .pixels import pixels_from_rows, pixels_to_rows, tiles_from_rows, tiles_to_rows
from .references import walk_layers


@lru_cache(maxsize=256)
def _image_bounds(rows: tuple[str, ...], w: int, h: int, ti: int):
    data = pixels_from_rows(list(rows), w, h)
    ys, xs = np.nonzero(data != ti)
    if not len(xs):
        return None
    left, top, right, bottom = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    return left, top, right, bottom, tuple(pixels_to_rows(data[top:bottom, left:right]))


def normalize_cels(project: Project, *, in_place: bool = False) -> Project:
    """Normalize a detached transaction in place, or return an independent copy by default."""
    result = project if in_place else deepcopy(project)
    ti = result.palette.transparent_index
    tilesets = {ts.id: ts for ts in result.tilesets}
    for layer, _ancestors in walk_layers(result.layers):
        if isinstance(layer, GroupLayer):
            continue
        by_frame: dict[int, Any] = {cel.frame: cel for cel in layer.cels}
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
        normalized: list[Any] = []
        for old_owner in sorted(groups):
            members = groups[old_owner]
            z_indices = {frame: by_frame[frame].z_index for frame in members}
            owner = by_frame[old_owner]
            data: Any
            if not (isinstance(layer, ImageLayer) and layer.background):
                if isinstance(layer, ImageLayer):
                    rows = tuple(owner.pixels)
                    if sum(map(len, rows)) <= 65536:
                        bounds = _image_bounds(rows, owner.w, owner.h, ti)
                    else:
                        bounds = _image_bounds.__wrapped__(rows, owner.w, owner.h, ti)
                    if bounds is None:
                        continue
                    left, top, right, bottom, cropped = bounds
                    owner.x += left
                    owner.y += top
                    owner.w, owner.h = right - left, bottom - top
                    owner.pixels = list(cropped)
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
                    owner.tiles = tiles_to_rows([row[left:right] for row in data[top:bottom]])
            first = min(members)
            owner.frame = first
            owner.z_index = z_indices[first]
            normalized.append(owner)
            normalized.extend(
                LinkCel(frame=frame, link=first, z_index=z_indices[frame])
                for frame in sorted(members)
                if frame != first
            )
        layer.cels = sorted(normalized, key=lambda cel: cel.frame)
    return result
