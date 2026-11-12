"""Strict Op arguments. Common transport options are validated separately."""

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, Field, create_model, model_validator

from cybersprite.core.limits import drawing_work
from cybersprite.core.models import (
    BlendMode,
    Coordinate,
    Grid,
    MatchFlips,
    Model,
    Name,
    Rect,
    Size,
    SliceKey,
    UserData,
)
from cybersprite.core.raster import geometry_work

from .descriptions import argument_model

Color = int | str
Frames = int | list[int] | str
Point = Annotated[list[int], Field(min_length=2, max_length=2)]
Positive = Annotated[int, Field(ge=1)]
Byte = Annotated[int, Field(ge=0, le=255)]
Duration = Annotated[int, Field(ge=1, le=65535)]


class AllRegion(Model):
    type: Literal["all"] = "all"


class RectRegion(Rect):
    type: Literal["rect"]


class MaskRegion(Model):
    type: Literal["mask"]
    x: int
    y: int
    rows: list[str]


class ColorRegion(Model):
    type: Literal["color"]
    color: Color


class WandRegion(Model):
    type: Literal["wand"]
    x: int
    y: int
    connectivity: Literal[4, 8] = 4


Region = Annotated[
    AllRegion | RectRegion | MaskRegion | ColorRegion | WandRegion, Field(discriminator="type")
]


class Brush(Model):
    size: Annotated[int, Field(ge=1, le=64)] = 1
    shape: Literal["square", "circle"] = "square"


class TxOptions(Model):
    expect_revision: Annotated[int, Field(ge=0)] | None = Field(
        None, description="Reject if the current revision differs."
    )
    idempotency_key: Annotated[str, Field(min_length=1, max_length=64)] | None = Field(
        None, description="Replay a prior result for this transaction key."
    )
    dry_run: bool = Field(False, description="Validate without committing project changes.")
    preview: Literal["none", "path", "inline"] = Field(
        "path", description="Return no preview, PNG paths, or inline PNG images."
    )


class OpCall(Model):
    op: str
    args: dict[str, Any] = Field(default_factory=dict)


class ValidationPatch(Model):
    palette_max: Annotated[int, Field(ge=1, le=256)] | None = None
    colors_per_frame_max: Positive | None = None
    orphan_pixels_max: Annotated[int, Field(ge=0)] | None = None
    min_cluster: Positive | None = None
    require_tag_coverage: bool | None = None
    silhouette_jitter_max: Annotated[int, Field(ge=0)] | None = None
    severity: dict[str, Literal["error", "warning", "info", "off"]] | None = None


class Onion(Model):
    prev: Annotated[int, Field(ge=0, le=8)] = 0
    next: Annotated[int, Field(ge=0, le=8)] = 0
    loop_tag: str | None = Field(
        None, description="Tag ID or unique name to wrap onion frames within."
    )


class Above(Model):
    above: str


class Below(Model):
    below: str


Position = Literal["top", "bottom"] | Above | Below
COMMON_DRAW = {"layer": (str, ...), "frame": (int, ...)}
REGION = (Region, Field(default_factory=AllRegion))
BRUSH = (Brush, Field(default_factory=Brush))
COLOR = (Color, ...)
XY = {"x": (int, ...), "y": (int, ...)}
WH = {"w": (Positive, ...), "h": (Positive, ...)}


class GeometryArgs(Model):
    @model_validator(mode="after")
    def check_work(self) -> Self:
        drawing_work(geometry_work(self))
        return self


def contract(name: str, fields: dict[str, Any], *, draw: bool = False) -> type[Model]:
    values: dict[str, Any] = {**(COMMON_DRAW if draw else {}), **fields}
    base = (
        GeometryArgs
        if name in ("LineArgs", "RectArgs", "EllipseArgs", "PolygonArgs", "StrokeArgs")
        else Model
    )
    return create_model(name, __base__=base, **values)


ARGS: dict[str, type[BaseModel]] = {}


def define(name: str, fields: dict[str, Any], draw: bool = False) -> None:
    ARGS[name] = argument_model(
        name, contract("".join(s.title() for s in name.split("_")) + "Args", fields, draw=draw)
    )


define("set_pixel", {**XY, "color": COLOR}, True)
define(
    "set_pixels",
    {
        "pixels": (list[list[Color]] | None, None),
        "points": (list[Point] | None, None),
        "color": (Color | None, None),
    },
    True,
)
define(
    "draw_rows",
    {
        **XY,
        "rows": (list[str], ...),
        "format": (Literal["hex", "sym"], "hex"),
        "skip_transparent": (bool, False),
    },
    True,
)
define(
    "line",
    {**{k: (int, ...) for k in ("x0", "y0", "x1", "y1")}, "color": COLOR, "brush": BRUSH},
    True,
)
for name in ("rect", "ellipse"):
    define(name, {**XY, **WH, "color": COLOR, "filled": (bool, False), "brush": BRUSH}, True)
define(
    "polygon",
    {
        "points": (list[Point], ...),
        "color": COLOR,
        "filled": (bool, False),
        "closed": (bool, True),
        "brush": BRUSH,
    },
    True,
)
define(
    "stroke",
    {"points": (list[Point], ...), "color": COLOR, "brush": BRUSH, "pixel_perfect": (bool, False)},
    True,
)
define(
    "fill",
    {
        **XY,
        "color": COLOR,
        "connectivity": (Literal[4, 8], 4),
        "sample": (Literal["layer", "composite"], "layer"),
    },
    True,
)
define("erase", {"region": (Region, ...)}, True)
define(
    "replace_color",
    {
        "from_": (Color, Field(alias="from")),
        "to": COLOR,
        "layers": (list[str] | None, None),
        "frames": (Frames, "all"),
        "region": REGION,
        "tilesets": (bool, False),
    },
)
define(
    "transform_region",
    {
        "region": (Region, ...),
        "action": (Literal["move", "copy"], "move"),
        "dx": (int, 0),
        "dy": (int, 0),
        "flip": (Literal["h", "v"] | None, None),
        "rotate": (Literal[0, 90, 180, 270], 0),
        "target_layer": (str | None, None),
        "target_frame": (int | None, None),
        "overwrite_transparent": (bool, False),
    },
    True,
)
define(
    "outline",
    {
        "color": COLOR,
        "placement": (Literal["outside", "inside"], "outside"),
        "connectivity": (Literal[4, 8], 4),
        "region": REGION,
    },
    True,
)
define(
    "cleanup_pixels",
    {
        "layer": (str, ...),
        "frame": (int | None, None),
        "frames": (Frames, "all"),
        "min_cluster": (Positive, 2),
        "connectivity": (Literal[4, 8], 8),
        "protect": (list[Color] | None, None),
        "region": REGION,
        "max_passes": (Positive, 2),
    },
)
define(
    "add_frame",
    {
        "at": (int | None, None),
        "count": (Positive, 1),
        "duration_ms": (Duration | None, None),
        "cels": (Literal["empty", "copy", "link", "auto"], "empty"),
        "copy_from": (int | None, None),
    },
)
define("delete_frames", {"frames": (Frames, ...)})
for name in ("move_frames", "reverse_frames"):
    define(
        name,
        {
            "from_": (int, Field(alias="from")),
            "to": (int, ...),
            **({"before": (int, ...)} if name == "move_frames" else {}),
        },
    )
define("set_frame_duration", {"frames": (Frames, ...), "duration_ms": (Duration, ...)})
define(
    "set_cel",
    {
        **{k: (Coordinate | None, None) for k in ("x", "y", "z_index")},
        "opacity": (Byte | None, None),
        "user_data": (UserData | None, None),
    },
    True,
)
for name in ("clear_cel", "unlink_cel"):
    define(name, {}, True)
define(
    "copy_cel",
    {
        "to_layer": (str | None, None),
        "to_frame": (int, ...),
        "mode": (Literal["copy", "move"], "copy"),
        "on_conflict": (Literal["replace", "error", "skip"], "replace"),
    },
    True,
)
define("link_cel", {"layer": (str, ...), "source_frame": (int, ...), "frames": (Frames, ...)})
SHRINK = (Literal["error", "remap_nearest", "to_transparent"], "error")
define(
    "set_palette",
    {
        "colors": (list[str], ...),
        "names": (dict[str, str] | None, None),
        "transparent_index": (int | None, None),
        "on_shrink": SHRINK,
    },
)
define("set_palette_color", {"index": (int, ...), "color": (str, ...), "name": (str | None, None)})
define(
    "add_palette_colors",
    {
        "colors": (list[str], ...),
        "names": (dict[str, str] | None, None),
        "reuse_existing": (bool, True),
    },
)
define(
    "remap_palette",
    {
        "order": (list[int] | None, None),
        "sort_by": (Literal["lightness", "hue", "usage"] | None, None),
        "merge_duplicates": (bool, False),
        "remove_unused": (bool, False),
        "keep_transparent_first": (bool, True),
    },
)
define(
    "load_palette",
    {"source": (str, ...), "mode": (Literal["replace", "append"], "replace"), "on_shrink": SHRINK},
)
define("set_palette_frozen", {"frozen": (bool, ...)})
define(
    "add_layer",
    {
        "name": (Name, ...),
        "type": (Literal["image", "group", "tilemap"], "image"),
        "parent": (str | None, None),
        "position": (Position, "top"),
        "opacity": (Byte, 255),
        "blend_mode": (BlendMode, "normal"),
        "visible": (bool, True),
        "continuous": (bool, False),
        "tileset": (str | None, None),
        "if_exists": (Literal["error", "reuse", "allow"], "error"),
    },
)
define(
    "update_layer",
    {
        "layer": (str, ...),
        "name": (Name | None, None),
        **{
            k: (bool | None, None)
            for k in ("visible", "locked", "continuous", "collapsed", "background")
        },
        "opacity": (Byte | None, None),
        "blend_mode": (BlendMode | None, None),
        "user_data": (UserData | None, None),
        "parent": (str | None, None),
        "position": (Position | None, None),
    },
)
define("delete_layer", {"layer": (str, ...), "missing_ok": (bool, False)})
define("duplicate_layer", {"layer": (str, ...), "name": (Name | None, None)})
define(
    "merge_layers",
    {
        "layers": (list[str] | None, None),
        "down": (str | None, None),
        "flatten": (Literal["strict", "nearest"], "strict"),
    },
)
define(
    "flatten", {"visible_only": (bool, True), "flatten": (Literal["strict", "nearest"], "strict")}
)
DIRECTION = Literal["forward", "reverse", "pingpong", "pingpong_reverse"]
define(
    "add_tag",
    {
        "name": (Name, ...),
        "from_": (int, Field(alias="from")),
        "to": (int, ...),
        "direction": (DIRECTION, "forward"),
        "repeat": (int, 0),
        "color": (str | None, None),
        "if_exists": (Literal["error", "update", "allow"], "error"),
    },
)
define(
    "update_tag",
    {
        "tag": (str, ...),
        "name": (Name | None, None),
        "from_": (int | None, Field(None, alias="from")),
        "to": (int | None, None),
        "direction": (DIRECTION | None, None),
        "repeat": (int | None, None),
        "color": (str | None, None),
        "user_data": (UserData | None, None),
        "position": (int | None, None),
    },
)
define("delete_tag", {"tag": (str, ...), "missing_ok": (bool, False)})
define(
    "add_slice",
    {
        "name": (Name, ...),
        "keys": (list[SliceKey], ...),
        "color": (str | None, None),
        "if_exists": (Literal["error", "update", "allow"], "error"),
    },
)
define(
    "update_slice",
    {
        "slice": (str, ...),
        "name": (Name | None, None),
        "color": (str | None, None),
        "user_data": (UserData | None, None),
        "keys": (list[SliceKey] | None, None),
        "set_key": (SliceKey | None, None),
        "remove_key": (int | None, None),
    },
)
define("delete_slice", {"slice": (str, ...), "missing_ok": (bool, False)})
define(
    "resize_canvas",
    {
        "width": (Positive, ...),
        "height": (Positive, ...),
        "anchor": (Literal["nw", "n", "ne", "w", "c", "e", "sw", "s", "se"], "nw"),
        "discard_outside": (bool, False),
    },
)
define("crop_canvas", {"rect": (Rect | Literal["content"], ...), "discard_outside": (bool, True)})
define("scale_sprite", {"factor": (Annotated[int, Field(ge=2, le=16)], ...)})
define(
    "transform_sprite",
    {"flip": (Literal["h", "v"] | None, None), "rotate": (Literal[0, 90, 180, 270], 0)},
)
define(
    "set_project_meta",
    {
        "name": (Name | None, None),
        "grid": (Grid | None, None),
        "pixel_ratio": (Size | None, None),
        "user_data": (UserData | None, None),
    },
)
define("set_validation", {"settings": (ValidationPatch, ...)})
define(
    "apply_ops",
    {
        "ops": (Annotated[list[OpCall], Field(min_length=1, max_length=1000)], ...),
        "label": (str | None, None),
    },
)
for name in ("undo", "redo"):
    define(name, {"steps": (Annotated[int, Field(ge=1, le=200)], 1)})
define(
    "new_project",
    {
        "width": (Positive, ...),
        "height": (Positive, ...),
        "palette": (str | list[str], "cs-circuit-16"),
        "transparent_index": (int, 0),
        "frames": (Positive, 1),
        "duration_ms": (Duration, 100),
        "name": (Name | None, None),
        "layer_name": (Name, "Layer 1"),
        "background": (Color | None, None),
        "if_exists": (Literal["error", "open"], "error"),
    },
)
define(
    "get_info",
    {
        "include": (
            list[
                Literal[
                    "summary",
                    "layers",
                    "frames",
                    "tags",
                    "slices",
                    "tilesets",
                    "palette",
                    "sources",
                    "validation",
                    "history",
                ]
            ],
            ["summary"],
        )
    },
)
define(
    "get_pixels",
    {
        "layer": (str, ...),
        "frame": (int, ...),
        "rect": (Rect | None, None),
        "format": (Literal["hex", "sym"], "hex"),
    },
)
define("get_palette", {})

TileSize = Annotated[int, Field(ge=1, le=256)]
define("delete_tileset", {"tileset": (str, ...), "missing_ok": (bool, False)})
define(
    "add_tileset",
    {
        "name": (Name, ...),
        "tile_w": (TileSize, ...),
        "tile_h": (TileSize, ...),
        "base_index": (int, 1),
        "if_exists": (Literal["error", "reuse", "allow"], "error"),
    },
)
define(
    "set_tile_pixels",
    {
        "tileset": (str, ...),
        "tile": (int | Literal["new"], ...),
        "rows": (list[str], ...),
        "format": (Literal["hex", "sym"], "hex"),
    },
)
define(
    "delete_tiles",
    {
        "tileset": (str, ...),
        "tiles": (list[int], ...),
        "on_used": (Literal["error", "clear"], "error"),
    },
)
define(
    "move_tiles",
    {
        "tileset": (str, ...),
        "from_": (int, Field(alias="from")),
        "to": (int, ...),
        "before": (int, ...),
    },
)
define(
    "set_tile",
    {
        "col": (int, ...),
        "row": (int, ...),
        "tile": (int, ...),
        "flip": (Annotated[str, Field(pattern=r"^x?y?d?$")], ""),
    },
    True,
)
define("set_tiles", {"col": (int, ...), "row": (int, ...), "rows": (list[str], ...)}, True)
define("get_tiles", {"rect": (Rect | None, None)}, True)
define(
    "tileset_from_layer",
    {
        "layer": (str, ...),
        "tile_w": (TileSize, ...),
        "tile_h": (TileSize, ...),
        "origin_x": (
            int | None,
            Field(None, description="Grid origin X; defaults to canvas.grid.x."),
        ),
        "origin_y": (
            int | None,
            Field(None, description="Grid origin Y; defaults to canvas.grid.y."),
        ),
        "name": (Name | None, None),
        "match_flips": (MatchFlips, Field(default_factory=MatchFlips)),
    },
)
define("validate", {"frames": (Frames, "all"), "rules": (list[str] | None, None)})
define(
    "render_preview",
    {
        "frames": (Frames, Field(default_factory=lambda: [0])),
        "tileset": (
            str | None,
            Field(None, description="Tileset ID or unique name; render its labeled tile grid."),
        ),
        "layout": (
            Literal["frames", "strip", "grid"],
            Field(
                "frames", description="Separate images (at most 8), one strip, or one frame grid."
            ),
        ),
        "layers": (list[str] | None, None),
        "scale": (Annotated[int, Field(ge=1, le=64)] | Literal["auto"], "auto"),
        "grid": (bool, False),
        "rulers": (bool, False),
        "onion": (Onion | None, None),
        "background": (Color, "checker"),
        "inline": (bool, True),
    },
)
define(
    "diff_preview",
    {
        "from_revision": (int | None, None),
        "to_revision": (int | None, None),
        "frames": (Annotated[list[int], Field(max_length=4)] | None, None),
        "inline": (bool, True),
    },
)
define("get_history", {"limit": (Annotated[int, Field(ge=1, le=1000)], 20)})
