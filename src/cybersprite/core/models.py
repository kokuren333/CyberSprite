"""Strict, ordered models for project schema version 1."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Name = Annotated[str, Field(min_length=1, max_length=255)]
Byte = Annotated[int, Field(ge=0, le=255)]
Positive = Annotated[int, Field(ge=1)]
Coordinate = Annotated[int, Field(ge=-32768, le=32767)]
RGB = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
RGBA = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{8}$")]
LayerId = Annotated[str, Field(pattern=r"^L[1-9][0-9]*$")]
TagId = Annotated[str, Field(pattern=r"^T[1-9][0-9]*$")]
SliceId = Annotated[str, Field(pattern=r"^S[1-9][0-9]*$")]
TilesetId = Annotated[str, Field(pattern=r"^TS[1-9][0-9]*$")]
BlendMode = Literal[
    "normal",
    "multiply",
    "screen",
    "overlay",
    "darken",
    "lighten",
    "color_dodge",
    "color_burn",
    "hard_light",
    "soft_light",
    "difference",
    "exclusion",
    "hue",
    "saturation",
    "color",
    "luminosity",
    "addition",
    "subtract",
    "divide",
]


class Model(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", populate_by_name=True)


class Point(Model):
    x: int
    y: int


class Size(Model):
    w: Positive = 1
    h: Positive = 1


class Rect(Point):
    w: Annotated[int, Field(ge=0)]
    h: Annotated[int, Field(ge=0)]


class Grid(Point):
    x: int = 0
    y: int = 0
    w: Positive = 16
    h: Positive = 16


class Canvas(Model):
    width: Positive
    height: Positive
    grid: Grid = Field(default_factory=Grid)
    pixel_ratio: Size = Field(default_factory=Size)
    color_profile: Literal["srgb", "none"] = "srgb"


class Palette(Model):
    transparent_index: Annotated[int, Field(ge=0)] = 0
    frozen: bool = False
    colors: list[RGBA]
    names: dict[str, str] = Field(default_factory=dict)

    @field_validator("names")
    @classmethod
    def numeric_names(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not re.fullmatch(r"0|[1-9][0-9]*", key) for key in value):
            raise ValueError("Palette names must use canonical decimal index keys.")
        return value


class Frame(Model):
    duration_ms: Annotated[int, Field(ge=1, le=65535)] = 100


class UserData(Model):
    text: str = ""
    color: RGBA | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class CelData(Model):
    frame: int
    x: Coordinate
    y: Coordinate
    w: Positive
    h: Positive
    opacity: Byte = 255
    z_index: Coordinate = 0
    user_data: UserData | None = None


class ImageCel(CelData):
    pixels: list[Annotated[str, Field(pattern=r"^(?:[0-9a-fA-F]{2})*$")]]


class TileCel(CelData):
    tiles: list[str]


class LinkCel(Model):
    frame: int
    link: int
    z_index: Coordinate = 0


class LayerBase(Model):
    id: LayerId
    name: Name
    type: str
    visible: bool = True
    locked: bool = False
    opacity: Byte = 255
    blend_mode: BlendMode = "normal"


class ImageLayer(LayerBase):
    type: Literal["image"] = "image"
    background: bool = False
    continuous: bool = False
    user_data: UserData | None = None
    cels: list[ImageCel | LinkCel] = Field(default_factory=list)


class TilemapLayer(LayerBase):
    type: Literal["tilemap"] = "tilemap"
    continuous: bool = False
    tileset: TilesetId
    user_data: UserData | None = None
    cels: list[TileCel | LinkCel] = Field(default_factory=list)


class GroupLayer(LayerBase):
    type: Literal["group"] = "group"
    collapsed: bool = False
    user_data: UserData | None = None
    children: list[Layer] = Field(default_factory=list)


Layer = Annotated[ImageLayer | TilemapLayer | GroupLayer, Field(discriminator="type")]
GroupLayer.model_rebuild()


class Tag(Model):
    id: TagId
    name: Name
    from_: int = Field(alias="from")
    to: int
    direction: Literal["forward", "reverse", "pingpong", "pingpong_reverse"] = "forward"
    repeat: Annotated[int, Field(ge=0, le=65535)] = 0
    color: RGB = "#19c3e6"
    user_data: UserData | None = None


class SliceKey(Rect):
    # Field order is specified explicitly by the canonical writer (frame precedes x).
    frame: int
    center: Rect | None = None
    pivot: Point | None = None


class Slice(Model):
    id: SliceId
    name: Name
    color: RGBA = "#19c3e6ff"
    user_data: UserData | None = None
    keys: Annotated[list[SliceKey], Field(min_length=1)]


class MatchFlips(Model):
    x: bool = False
    y: bool = False
    d: bool = False


class Tile(Model):
    pixels: list[Annotated[str, Field(pattern=r"^(?:[0-9a-fA-F]{2})*$")]]
    user_data: UserData | None = None


class Tileset(Model):
    id: TilesetId
    name: Name
    tile_w: Annotated[int, Field(ge=1, le=256)]
    tile_h: Annotated[int, Field(ge=1, le=256)]
    base_index: int = 1
    match_flips: MatchFlips = Field(default_factory=MatchFlips)
    user_data: UserData | None = None
    tiles: Annotated[list[Tile], Field(min_length=1)]


class ValidationSettings(Model):
    palette_max: Annotated[int, Field(ge=1, le=256)] = 256
    colors_per_frame_max: Positive | None = None
    orphan_pixels_max: Annotated[int, Field(ge=0)] | None = None
    min_cluster: Positive = 2
    require_tag_coverage: bool = False
    silhouette_jitter_max: Annotated[int, Field(ge=0)] | None = None
    severity: dict[str, Literal["error", "warning", "info", "off"]] = Field(default_factory=dict)


class IdCounters(Model):
    layer: Annotated[int, Field(ge=0)] = 0
    tag: Annotated[int, Field(ge=0)] = 0
    slice: Annotated[int, Field(ge=0)] = 0
    tileset: Annotated[int, Field(ge=0)] = 0

    def issue(self, kind: Literal["layer", "tag", "slice", "tileset"]) -> str:
        value = getattr(self, kind) + 1
        setattr(self, kind, value)
        return {"layer": "L", "tag": "T", "slice": "S", "tileset": "TS"}[kind] + str(value)


class Project(Model):
    format: Literal["cybersprite-project"] = "cybersprite-project"
    schema_version: Literal[1] = 1
    revision: Annotated[int, Field(ge=0)] = 0
    name: Name
    canvas: Canvas
    palette: Palette
    frames: list[Frame]
    layers: list[Layer]
    tags: list[Tag] = Field(default_factory=list)
    slices: list[Slice] = Field(default_factory=list)
    tilesets: list[Tileset] = Field(default_factory=list)
    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    user_data: UserData | None = None
    id_counters: IdCounters = Field(default_factory=IdCounters)
    extensions: dict[str, Any] = Field(default_factory=dict)


class SourceFile(Model):
    path: str
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    width: Positive
    height: Positive
    bytes: Annotated[int, Field(ge=0)]


class SourceAdapter(Model):
    id: str
    license: Annotated[str, Field(min_length=1)]


class SourceModel(SourceAdapter):
    sha256: str
    adapters: list[SourceAdapter]


class SourcePipeline(Model):
    preset: str
    params: dict[str, Any]
    report: dict[str, Any]
    result_sha256: str
    accepted: bool
    gates_overridden: list[str]


class Placement(Model):
    revision: Annotated[int, Field(ge=0)]
    layer: LayerId
    frames: list[int]


class Source(Model):
    id: Annotated[str, Field(pattern=r"^SRC[1-9][0-9]*$")]
    kind: Literal["generated", "imported"]
    use: Literal["canvas", "design"] = "canvas"
    files: list[SourceFile]
    provider: str
    model: SourceModel | None
    prompt: str
    negative_prompt: str
    seed: int | None
    params: dict[str, Any]
    license: Annotated[str, Field(min_length=1)]
    rights_note: str
    url: str
    created_at: str
    imported_at: str
    pipeline: SourcePipeline | None
    placements: list[Placement]

    @field_validator("created_at", "imported_at")
    @classmethod
    def timestamp_with_timezone(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Source timestamps must include an ISO 8601 timezone.")
        return value


class Sources(Model):
    format: Literal["cybersprite-sources"] = "cybersprite-sources"
    schema_version: Literal[1] = 1
    next_id: Positive = 1
    sources: list[Source] = Field(default_factory=list)
