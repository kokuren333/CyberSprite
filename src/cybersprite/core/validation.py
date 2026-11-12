"""Structural invariants S-01 through S-14; quality rules belong to M2."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from typing import Any, cast

from pydantic import BaseModel, ValidationError

from .errors import CyberSpriteError
from .models import GroupLayer, ImageCel, ImageLayer, LinkCel, Project, Tile, TileCel, TilemapLayer
from .pixels import parse_tile
from .references import cel_owner, walk_layers


@dataclass
class Issue:
    rule: str
    message: str
    hint: str
    where: dict[str, Any] = field(default_factory=dict)
    level: str = "error"

    def as_dict(self) -> dict:
        return asdict(self)


def _json_issues(value, path: str, allow_float: bool = False, depth: int = 0) -> list[Issue]:
    issues = []
    if allow_float and depth > 16:
        return [
            Issue(
                "S-01",
                "User properties exceed 16 nesting levels.",
                "Reduce nested arrays or objects to at most 16 levels.",
                {"path": path},
            )
        ]
    if type(value) is float and (not allow_float or not math.isfinite(value)):
        issues.append(
            Issue(
                "S-01",
                "Floats are allowed only as finite user properties.",
                "Use integers outside user_data.properties; remove NaN/Infinity.",
                {"path": path},
            )
        )
    elif type(value) is float:
        pass
    elif isinstance(value, str):
        if re.search(r"[\ud800-\udfff]", value):
            issues.append(
                Issue(
                    "S-01",
                    "String contains an unpaired Unicode surrogate.",
                    "Replace it with a valid Unicode character.",
                    {"path": path},
                )
            )
    elif isinstance(value, dict):
        if any(type(key) is not str for key in value):
            return [
                Issue(
                    "S-01",
                    "JSON object keys must be strings.",
                    "Use string keys in properties and extensions.",
                    {"path": path},
                )
            ]
        for key in sorted(value):
            issues.extend(_json_issues(key, path, False))
            issues.extend(_json_issues(value[key], f"{path}/{key}", allow_float, depth + 1))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            issues.extend(_json_issues(item, f"{path}/{i}", allow_float, depth + 1))
    elif value is not None and type(value) not in (int, bool):
        issues.append(
            Issue(
                "S-01",
                "Value is not a JSON value.",
                "Use null, bool, int, string, list, or object.",
                {"path": path},
            )
        )
    return issues


@lru_cache(maxsize=4096)
def _row_maximum(row: str) -> int:
    return max(bytes.fromhex(row[: len(row) // 2 * 2]), default=0)


def check_structure(project: Project | dict) -> list[Issue]:
    try:
        # Revalidate even models edited in memory by later Op implementations.
        p = Project.model_validate(
            project.model_dump(by_alias=True) if isinstance(project, Project) else project
        )
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            failures = [
                Issue(
                    "S-01",
                    e["msg"],
                    "Correct this field to match project.schema.json.",
                    {"path": "/" + "/".join(str(k) for k in e["loc"])},
                )
                for e in error.errors(include_context=False, include_input=False)
            ]
            for e in error.errors(include_input=False):
                if e["type"] == "string_too_long" and e.get("ctx", {}).get("max_length") == 255:
                    failures.append(
                        Issue(
                            "S-12",
                            "Name exceeds the limit of 255 characters.",
                            "Shorten this name to at most 255 characters.",
                            {"path": "/" + "/".join(str(k) for k in e["loc"])},
                        )
                    )
            return failures
        return [Issue("S-01", str(error), "Correct the project model.")]
    issues: list[Issue] = []

    def add(rule, message, hint, **where):
        issues.append(Issue(rule, message, hint, where))

    nodes = list(walk_layers(p.layers))
    nframes = len(p.frames)
    ncolors = len(p.palette.colors)
    ti = p.palette.transparent_index
    if not 1 <= ncolors <= 256 or not 0 <= ti < ncolors:
        add(
            "S-13",
            "Palette size or transparent index is invalid.",
            "Use 1..256 colors and a transparent index within that palette.",
            path="/palette",
        )
    for key in sorted(p.palette.names, key=int):
        if int(key) >= ncolors:
            add(
                "S-13",
                "Named palette index is outside the palette.",
                "Remove this name or add its palette color.",
                path=f"/palette/names/{key}",
            )
    if not nframes or not nodes:
        add(
            "S-14",
            "Projects require at least one frame and one layer.",
            "Create a frame and an image layer.",
        )
    if (p.canvas.pixel_ratio.w, p.canvas.pixel_ratio.h) not in ((1, 1), (2, 1), (1, 2)):
        add("S-01", "Unsupported pixel ratio.", "Use 1:1, 2:1, or 1:2.", path="/canvas/pixel_ratio")

    def limit(value, maximum, path):
        if value > maximum:
            add(
                "S-12",
                f"{path} exceeds the limit {maximum} (requested {value}).",
                "Reduce the requested size or number of objects.",
                path=path,
                requested=value,
                limit=maximum,
            )

    limit(p.canvas.width, 8192, "/canvas/width")
    limit(p.canvas.height, 8192, "/canvas/height")
    limit(p.canvas.width * p.canvas.height, 16777216, "/canvas/area")
    limit(nframes, 4096, "/frames")
    limit(len(nodes), 1024, "/layers")
    limit(ncolors, 256, "/palette/colors")
    for name, items, maximum in (
        ("tags", p.tags, 1024),
        ("slices", p.slices, 4096),
        ("tilesets", p.tilesets, 64),
    ):
        limit(len(items), maximum, f"/{name}")
    groups = (
        ("layer", [n[0] for n in nodes], "L"),
        ("tag", p.tags, "T"),
        ("slice", p.slices, "S"),
        ("tileset", p.tilesets, "TS"),
    )
    for kind, id_items, prefix in groups:
        seen = set()
        for item in id_items:
            if item.id in seen:
                add(
                    "S-06",
                    f"Duplicate {kind} ID {item.id}.",
                    "Assign a new ID using id_counters; never reuse an issued ID.",
                    id=item.id,
                )
            seen.add(item.id)
        maximum = max((int(item.id[len(prefix) :]) for item in id_items), default=0)
        if getattr(p.id_counters, kind) < maximum:
            add(
                "S-06",
                f"id_counters.{kind} is below issued ID {maximum}.",
                f"Set id_counters.{kind} to at least {maximum}.",
                path=f"/id_counters/{kind}",
            )

    def pixel_rows(rows, w, h, rule, **where):
        if len(rows) != h or any(len(row) != 2 * w for row in rows):
            add(
                rule,
                "Pixel row dimensions do not match w and h.",
                "Write h hexadecimal rows, each containing exactly 2*w digits.",
                **where,
            )
        for y, row in enumerate(rows):
            # Validate common rows in C, preserving the original first-invalid
            # coordinate and handling odd-length rows exactly as before.
            maximum = _row_maximum(row) if len(row) <= 16384 else _row_maximum.__wrapped__(row)
            if maximum < ncolors:
                continue
            for x in range(0, len(row) - 1, 2):
                index = int(row[x : x + 2], 16)
                if index >= ncolors:
                    add(
                        "S-02",
                        f"Pixel index {index} exceeds palette size {ncolors}.",
                        "Replace this index or explicitly add its palette color.",
                        **where,
                        point=[x // 2, y],
                        index=index,
                    )
                    return

    sets = {ts.id: ts for ts in p.tilesets}
    for ts in p.tilesets:
        limit(len(ts.tiles), 65536, f"/tilesets/{ts.id}/tiles")
        for i, tile in enumerate(ts.tiles):
            pixel_rows(tile.pixels, ts.tile_w, ts.tile_h, "S-09", tileset=ts.id, tile=i)
        if any(
            int(row[x : x + 2], 16) != ti
            for row in ts.tiles[0].pixels
            for x in range(0, len(row) - 1, 2)
        ):
            add(
                "S-09",
                "Tile 0 contains non-transparent indices.",
                "Replace every pixel of tile 0 with transparent_index.",
                tileset=ts.id,
            )
    backgrounds = []
    for layer, ancestors in nodes:
        limit(len(ancestors) + (isinstance(layer, GroupLayer)), 16, f"/layers/{layer.id}/depth")
        if isinstance(layer, GroupLayer):
            continue
        frames = [cel.frame for cel in layer.cels]
        if frames != sorted(set(frames)) or any(not 0 <= f < nframes for f in frames):
            add(
                "S-04",
                "Cels must have unique ascending frame numbers within frame range.",
                "Sort cels by frame and remove duplicate or out-of-range entries.",
                layer=layer.id,
            )
        if isinstance(layer, TilemapLayer) and layer.tileset not in sets:
            add(
                "S-10",
                f"Tileset {layer.tileset} does not exist.",
                "Assign an existing tileset ID to this tilemap layer.",
                layer=layer.id,
            )
        for cel in layer.cels:
            where = {"layer": layer.id, "frames": [cel.frame]}
            if isinstance(cel, LinkCel):
                owner = cel_owner(layer, cel)
                if owner is None or isinstance(owner, LinkCel) or cel.link >= cel.frame:
                    add(
                        "S-05",
                        "Link must point directly to an earlier data cel in this layer.",
                        "Normalize ownership to the lowest frame and link directly to it.",
                        **where,
                    )
                continue
            if isinstance(layer, ImageLayer):
                image_cel = cast(ImageCel, cel)
                pixel_rows(image_cel.pixels, image_cel.w, image_cel.h, "S-03", **where)
            else:
                tile_cel = cast(TileCel, cel)
                if len(tile_cel.tiles) != tile_cel.h or any(
                    len(row.split()) != tile_cel.w for row in tile_cel.tiles
                ):
                    add(
                        "S-03",
                        "Tile row dimensions do not match w and h.",
                        "Write h rows with w space-separated tile references each.",
                        **where,
                    )
                for row in tile_cel.tiles:
                    for token in row.split():
                        try:
                            ref = parse_tile(token)
                            if layer.tileset in sets and ref.index >= len(
                                sets[layer.tileset].tiles
                            ):
                                raise ValueError("Tile index is outside the referenced tileset.")
                        except (CyberSpriteError, ValueError) as error:
                            add(
                                "S-10",
                                str(error),
                                "Use an existing tile number; tile 0 has no flags.",
                                **where,
                                tile=token,
                            )
        if isinstance(layer, ImageLayer) and layer.background:
            backgrounds.append(layer.id)
            if (
                ancestors
                or not p.layers
                or p.layers[0] is not layer
                or layer.opacity != 255
                or layer.blend_mode != "normal"
                or frames != list(range(nframes))
            ):
                add(
                    "S-11",
                    "Background layer must be bottommost, opaque, normal, with every frame.",
                    "Place one background image layer at root index 0 and provide every frame.",
                    layer=layer.id,
                )
            for cel in layer.cels:
                owner = cel_owner(layer, cel)
                if (
                    owner is not None
                    and not isinstance(owner, LinkCel)
                    and (owner.x, owner.y, owner.w, owner.h)
                    != (0, 0, p.canvas.width, p.canvas.height)
                ):
                    add(
                        "S-11",
                        "Background cel must cover the exact canvas rectangle.",
                        "Set x=y=0 and w,h to the canvas width,height.",
                        layer=layer.id,
                        frames=[cel.frame],
                    )
    if len(backgrounds) > 1:
        add(
            "S-11",
            "Multiple background layers exist.",
            "Keep only one background layer at root index 0.",
            layers=backgrounds,
        )
    for tag in p.tags:
        if not 0 <= tag.from_ <= tag.to < nframes:
            add(
                "S-07",
                "Tag frame range is invalid.",
                "Use 0 <= from <= to < frame_count.",
                tag=tag.id,
            )
    for slc in p.slices:
        frames = [key.frame for key in slc.keys]
        if frames != sorted(set(frames)) or any(not 0 <= f < nframes for f in frames):
            add(
                "S-08",
                "Slice keys must have unique ascending in-range frame numbers.",
                "Sort keys and remove duplicate or out-of-range frame numbers.",
                slice=slc.id,
            )

    # Only actual user_data.properties permits floating point, never similarly named extension keys.
    def inspect(value, path=""):
        if isinstance(value, BaseModel):
            for name in type(value).model_fields:
                item = getattr(value, name)
                # Pixel/tile rows have already passed strict typing and ASCII grammar checks.
                if name == "pixels" and isinstance(value, (ImageCel, Tile)):
                    continue
                if type(value).__name__ == "UserData" and name == "properties":
                    issues.extend(_json_issues(item, path + "/properties", True, -1))
                else:
                    inspect(item, path + "/" + name)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                inspect(item, f"{path}/{i}")
        elif isinstance(value, dict):
            issues.extend(_json_issues(value, path))
        else:
            issues.extend(_json_issues(value, path))

    inspect(p)
    for key in sorted(p.extensions):
        if not re.fullmatch(r"[^.]+\.[^.]+", key):
            add(
                "S-01",
                "Extension keys must be provider.name.",
                "Namespace this extension key with its provider.",
                path=f"/extensions/{key}",
            )
    return sorted(issues, key=lambda i: (i.rule, str(i.where)))


def require_valid(project: Project | dict) -> Project:
    issues = check_structure(project)
    if issues:
        raise CyberSpriteError(
            "E_INVALID_PROJECT",
            "Project violates structural invariants.",
            "Correct the fields in details.issues, then load the project again.",
            {"issues": [issue.as_dict() for issue in issues]},
        )
    return project if isinstance(project, Project) else Project.model_validate(project)


def validation_report(project: Project) -> dict:
    issues = check_structure(project)
    nodes = [layer for layer, _ancestors in walk_layers(project.layers)]
    cels = [cel for layer in nodes if not isinstance(layer, GroupLayer) for cel in layer.cels]
    return {
        "ok": not issues,
        "revision": project.revision,
        "counts": {"error": len(issues), "warning": 0, "info": 0},
        "issues": [issue.as_dict() for issue in issues],
        "metrics": {
            "frames": len(project.frames),
            "layers": len(nodes),
            "cels": len(cels),
            "linked_cels": sum(isinstance(cel, LinkCel) for cel in cels),
            "palette_size": len(project.palette.colors),
            "tags": len(project.tags),
            "slices": len(project.slices),
            "tilesets": len(project.tilesets),
        },
        "settings": project.validation.model_dump(),
        "scope": "structural",
    }
