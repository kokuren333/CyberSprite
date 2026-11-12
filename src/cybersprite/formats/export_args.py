"""Strict export/ingest contracts consumed by the generated CLI and MCP surfaces."""

from typing import Annotated, Literal

from pydantic import Field

from cybersprite.core.models import Model, Rect

Scale = Annotated[int, Field(ge=1, le=64)]
Positive = Annotated[int, Field(ge=1)]
Padding = Annotated[int, Field(ge=0)]
Frames = int | list[int] | str | None
Mode = Literal["indexed", "rgba"]
Compression = Literal["stored", "zlib"]


class ExportBase(Model):
    out: str
    overwrite: bool = True
    allow_invalid: bool = False


class ImageArgs(ExportBase):
    frames: Frames = None
    layers: list[str] | None = None
    color_mode: Mode = "indexed"
    flatten: Literal["strict", "nearest"] = "strict"
    scale: Scale = 1
    crop: Rect | None = None
    slice: str | None = None
    trim: bool = False
    background: int | str | None = None
    apply_pixel_ratio: bool = False
    compression: Compression = "zlib"


class SheetArgs(ExportBase):
    data_out: str | None = None
    data_format: Literal["cybersprite", "json-hash", "json-array"] = "cybersprite"
    layout: Literal["horizontal", "vertical", "rows", "columns", "packed"] = "rows"
    columns: Positive | None = None
    rows: Positive | None = None
    width: Positive | None = None
    height: Positive | None = None
    frames: Frames = None
    tag: str | None = None
    layers: list[str] | None = None
    exclude_layers: list[str] = Field(default_factory=list)
    include_hidden: bool = False
    split_layers: bool = False
    split_tags: bool = False
    split_slices: bool = False
    scale: Scale = 1
    trim: bool = False
    ignore_empty: bool = False
    merge_duplicates: bool = False
    border: Padding = 0
    spacing: Padding = 0
    inner: Padding = 0
    power_of_two: bool = False
    color_mode: Mode = "indexed"
    flatten: Literal["strict", "nearest"] = "strict"
    compression: Compression = "zlib"
    item_name: str = "{name} {frame}"


class AnimationArgs(ExportBase):
    format: Literal["gif", "apng"] | None = None
    tag: str | None = None
    frames: Frames = None
    layers: list[str] | None = None
    scale: Scale = 1
    loop: Annotated[int, Field(ge=0, le=65535)] = 0
    color_mode: Mode | None = None
    flatten: Literal["strict", "nearest"] = "strict"
    background: int | str | None = None
    compression: Compression = "zlib"


class AsepriteArgs(ExportBase):
    verify: bool = True


class PaletteArgs(ExportBase):
    format: Literal["gpl", "pal", "hex", "png"] | None = None


class TilesetArgs(ExportBase):
    tileset: str
    data_out: str | None = None
    layout: Literal["horizontal", "vertical", "rows", "columns", "packed"] = "rows"
    columns: Positive | None = None
    rows: Positive | None = None
    width: Positive | None = None
    height: Positive | None = None
    spacing: Padding = 0
    border: Padding = 0
    inner: Padding = 0
    scale: Scale = 1
    power_of_two: bool = False
    include_empty: bool = False
    compression: Compression = "zlib"


class ImportAsepriteArgs(Model):
    file: str
    quantize: dict | None = None
    if_exists: Literal["error", "open"] = "error"


class ExportFile(Model):
    path: str
    bytes: int
    sha256: str
    pixel_sha256: str | None
    width: int
    height: int


class ExportResult(Model):
    files: list[ExportFile]
    fingerprint: str
    warnings: list[dict]
    validation_ok: bool
    verified: bool
    sheet: dict[str, int] | None = None
    items: int | None = None


class ImportResult(Model):
    summary: dict
    dropped: list[dict]
    source: str | None


EXPORT_ARGS = {
    "export_image": ImageArgs,
    "export_sheet": SheetArgs,
    "export_animation": AnimationArgs,
    "export_aseprite": AsepriteArgs,
    "export_palette": PaletteArgs,
    "export_tileset": TilesetArgs,
}
