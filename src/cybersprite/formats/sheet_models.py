"""Language-neutral contracts for the three sheet metadata representations."""

from typing import Literal

from pydantic import Field, TypeAdapter

from cybersprite.core.models import Model, Positive, Rect


class Size(Model):
    w: Positive
    h: Positive


class SheetSource(Model):
    name: str
    revision: int
    canvas: Size


class SheetItem(Model):
    name: str
    frame: int
    layer: str | None
    layer_id: str | None
    tag: str | None
    tag_id: str | None
    slice: str | None
    slice_id: str | None
    rect: Rect
    trimmed: bool
    source_rect: Rect
    source_size: Size
    duration_ms: Positive
    pixel_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SheetData(Model):
    format: Literal["cybersprite-sheet"]
    schema_version: Literal[1]
    image: str = Field(json_schema_extra={"format": "path"})
    size: Size
    scale: Positive
    color_mode: Literal["indexed", "rgba"]
    source: SheetSource
    palette: list[str]
    transparent_index: int
    items: list[SheetItem]
    tags: list[dict]
    layers: list[dict]
    slices: list[dict]


class CompatibleFrame(Model):
    frame: Rect
    rotated: Literal[False]
    trimmed: bool
    spriteSourceSize: Rect
    sourceSize: Size
    duration: Positive


class NamedFrame(CompatibleFrame):
    filename: str


class CompatibleMeta(Model):
    app: Literal["CyberSprite"]
    version: str
    image: str = Field(json_schema_extra={"format": "path"})
    format: Literal["I8", "RGBA8888"]
    size: Size
    scale: str
    frameTags: list[dict]
    layers: list[dict]
    slices: list[dict]


class CompatibleSheet(Model):
    frames: dict[str, CompatibleFrame] | list[NamedFrame]
    meta: CompatibleMeta


def sheet_schema():
    return TypeAdapter(SheetData | CompatibleSheet).json_schema(by_alias=True)
