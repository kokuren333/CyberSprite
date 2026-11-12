"""Strict export/ingest contracts consumed by the generated CLI and MCP surfaces."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from cybersprite.core.models import Model, Rect

Scale = Annotated[int, Field(ge=1, le=64)]
Positive = Annotated[int, Field(ge=1)]
Padding = Annotated[int, Field(ge=0)]
Frames = int | list[int] | str | None
Mode = Literal["indexed", "rgba"]
Compression = Literal["stored", "zlib"]


class ExportBase(Model):
    out: str = Field(
        description=(
            "Output file path, relative to the surface root. export image supports "
            "{name}, {frame} (zero-based), {frame1} (one-based), {layer}, {tag}, "
            "{tagframe} (zero-based within tag), and {slice}; integer frame fields "
            "accept widths such as {frame:02}. Other export subcommands use literal paths."
        )
    )
    overwrite: bool = Field(True, description="Replace existing output files when true.")
    allow_invalid: bool = Field(
        False, description="Explicitly export even when validation has errors, recording a warning."
    )


class PluginExportArgs(ExportBase):
    out: str = Field(
        description="Single output path.", json_schema_extra={"x-cybersprite-path": "output"}
    )
    format: str | None = Field(
        None, description="Enabled exporter entry-point name; omission uses extension."
    )
    options: dict = Field(
        default_factory=dict, description="Options validated by the exporter options model."
    )


class ImageArgs(ExportBase):
    frames: Frames = Field(
        None,
        description=(
            "Frame selection: zero-based index/list, all, range 0-3, or tag:name; "
            "omission uses all frames."
        ),
    )
    layers: list[str] | None = Field(
        None,
        description="Layer references to include; omission uses the operation default selection.",
    )
    color_mode: Mode = Field("indexed", description="Write palette-indexed or full RGBA output.")
    flatten: Literal["strict", "nearest"] = Field(
        "strict",
        description=(
            "Require exact palette closure (strict) or explicitly map to nearest palette colors."
        ),
    )
    scale: Scale = Field(
        1, description="Integer nearest-neighbor scale; auto fits previews within their size limit."
    )
    crop: Rect | None = Field(
        None, description="Integer crop rectangle {x,y,w,h} contained within the canvas."
    )
    slice: str | None = Field(None, description="Slice ID or unique name.")
    trim: bool = Field(
        False,
        description="Remove transparent borders and retain original bounds in sheet metadata.",
    )
    background: int | str | None = Field(
        None, description="Background palette index or color; omission preserves transparency."
    )
    apply_pixel_ratio: bool = Field(
        False, description="Apply the stored integer display pixel ratio during rendering."
    )
    compression: Compression = Field(
        "zlib",
        description=(
            "PNG compression: deterministic stored blocks or environment-dependent zlib bytes."
        ),
    )


class SheetArgs(ExportBase):
    data_out: str | None = Field(
        None,
        description=(
            "Optional sheet/tileset metadata JSON output path, relative to the surface root."
        ),
    )
    data_format: Literal["cybersprite", "json-hash", "json-array"] = Field(
        "cybersprite",
        description=(
            "Sheet metadata shape: cybersprite, filename-keyed json-hash, or ordered json-array."
        ),
    )
    layout: Literal["horizontal", "vertical", "rows", "columns", "packed"] = Field(
        "rows",
        description=(
            "Item layout: horizontal, vertical, fixed rows/columns, or "
            "deterministic packed shelves."
        ),
    )
    columns: Positive | None = Field(None, description="Maximum item columns for rows layout.")
    rows: Positive | None = Field(None, description="Maximum item rows for columns layout.")
    width: Positive | None = Field(None, description="Width in integer pixels.")
    height: Positive | None = Field(None, description="Height in integer pixels.")
    frames: Frames = Field(
        None,
        description=(
            "Frame selection: zero-based index/list, all, range 0-3, or tag:name; "
            "omission uses all frames."
        ),
    )
    tag: str | None = Field(None, description="Tag ID or unique name selecting the frame range.")
    layers: list[str] | None = Field(
        None,
        description="Layer references to include; omission uses the operation default selection.",
    )
    exclude_layers: list[str] = Field(
        default_factory=list, description="Layer references excluded from sheet rendering."
    )
    include_hidden: bool = Field(
        False, description="Include layers whose visibility flag is false."
    )
    split_layers: bool = Field(
        False, description="Create separate sheet items for individual selected layers."
    )
    split_tags: bool = Field(False, description="Create separate item sequences for tags.")
    split_slices: bool = Field(False, description="Create separate cropped items for slices.")
    scale: Scale = Field(
        1, description="Integer nearest-neighbor scale; auto fits previews within their size limit."
    )
    trim: bool = Field(
        False,
        description="Remove transparent borders and retain original bounds in sheet metadata.",
    )
    ignore_empty: bool = Field(False, description="Omit items containing only transparent pixels.")
    merge_duplicates: bool = Field(
        False, description="Share identical entries instead of keeping duplicates."
    )
    border: Padding = Field(
        0, description="Transparent integer padding around the outer sheet edge."
    )
    spacing: Padding = Field(0, description="Integer gap between neighboring sheet items.")
    inner: Padding = Field(0, description="Transparent integer padding inside every sheet item.")
    power_of_two: bool = Field(False, description="Round sheet dimensions up to powers of two.")
    color_mode: Mode = Field("indexed", description="Write palette-indexed or full RGBA output.")
    flatten: Literal["strict", "nearest"] = Field(
        "strict",
        description=(
            "Require exact palette closure (strict) or explicitly map to nearest palette colors."
        ),
    )
    compression: Compression = Field(
        "zlib",
        description=(
            "PNG compression: deterministic stored blocks or environment-dependent zlib bytes."
        ),
    )
    item_name: str = Field(
        "{name} {frame}",
        description=(
            "Metadata filename template using name, frame, frame1, layer, tag, "
            "slice, or tagframe placeholders."
        ),
    )


class AnimationArgs(ExportBase):
    format: Literal["gif", "apng"] | None = Field(
        None, description="Output format; omit to infer it from the output filename extension."
    )
    tag: str | None = Field(None, description="Tag ID or unique name selecting the frame range.")
    frames: Frames = Field(
        None,
        description=(
            "Frame selection: zero-based index/list, all, range 0-3, or tag:name; "
            "omission uses all frames."
        ),
    )
    layers: list[str] | None = Field(
        None,
        description="Layer references to include; omission uses the operation default selection.",
    )
    scale: Scale = Field(
        1, description="Integer nearest-neighbor scale; auto fits previews within their size limit."
    )
    loop: Annotated[int, Field(ge=0, le=65535)] = Field(
        0, description="Animation loop count; zero loops forever."
    )
    color_mode: Mode | None = Field(None, description="Write palette-indexed or full RGBA output.")
    flatten: Literal["strict", "nearest"] = Field(
        "strict",
        description=(
            "Require exact palette closure (strict) or explicitly map to nearest palette colors."
        ),
    )
    background: int | str | None = Field(
        None, description="Background palette index or color; omission preserves transparency."
    )
    compression: Compression = Field(
        "zlib",
        description=(
            "PNG compression: deterministic stored blocks or environment-dependent zlib bytes."
        ),
    )


class AsepriteArgs(ExportBase):
    verify: bool = Field(
        True,
        description=(
            "Also compare supported canonical fields on .aseprite readback; pixel "
            "verification always runs."
        ),
    )


class PaletteArgs(ExportBase):
    format: Literal["gpl", "pal", "hex", "png"] | None = Field(
        None, description="Output format; omit to infer it from the output filename extension."
    )


class TilesetArgs(ExportBase):
    tileset: str = Field(description="Tileset ID associated with this operation.")
    data_out: str | None = Field(
        None,
        description=(
            "Optional sheet/tileset metadata JSON output path, relative to the surface root."
        ),
    )
    layout: Literal["horizontal", "vertical", "rows", "columns", "packed"] = Field(
        "rows",
        description=(
            "Item layout: horizontal, vertical, fixed rows/columns, or "
            "deterministic packed shelves."
        ),
    )
    columns: Positive | None = Field(None, description="Maximum item columns for rows layout.")
    rows: Positive | None = Field(None, description="Maximum item rows for columns layout.")
    width: Positive | None = Field(None, description="Width in integer pixels.")
    height: Positive | None = Field(None, description="Height in integer pixels.")
    spacing: Padding = Field(0, description="Integer gap between neighboring sheet items.")
    border: Padding = Field(
        0, description="Transparent integer padding around the outer sheet edge."
    )
    inner: Padding = Field(0, description="Transparent integer padding inside every sheet item.")
    scale: Scale = Field(
        1, description="Integer nearest-neighbor scale; auto fits previews within their size limit."
    )
    power_of_two: bool = Field(False, description="Round sheet dimensions up to powers of two.")
    include_empty: bool = Field(False, description="Include the transparent tile at index zero.")
    compression: Compression = Field(
        "zlib",
        description=(
            "PNG compression: deterministic stored blocks or environment-dependent zlib bytes."
        ),
    )


class ImportAsepriteArgs(Model):
    file: str = Field(description="Input .aseprite or .ase file path.")
    quantize: dict | None = Field(
        None,
        json_schema_extra={
            "properties": {
                "source": {
                    "anyOf": [
                        {"type": "string", "x-cybersprite-path": "palette"},
                        {"type": "array"},
                    ]
                }
            }
        },
        description=(
            "Explicit palette quantization options required for input that cannot "
            "fit exact indexed colors."
        ),
    )
    if_exists: Literal["error", "open"] = Field(
        "error",
        description="Policy when a matching resource already exists; see the allowed enum values.",
    )


class ExportDataFile(Model):
    kind: Literal["data"]
    path: str = Field(json_schema_extra={"format": "path"})
    bytes: int
    sha256: str


class ExportFile(Model):
    path: str = Field(json_schema_extra={"format": "path"})
    bytes: int
    sha256: str
    pixel_sha256: str
    width: int
    height: int


class ExportResult(Model):
    files: list[ExportFile | ExportDataFile]
    fingerprint: str
    warnings: list[dict]
    validation_ok: bool
    verified: bool
    verification_reason: str | None = None
    sheet: dict[str, int] | None = None
    items: int | None = None


class ImportResult(Model):
    summary: dict
    dropped: list[dict]
    source: str | None


EXPORT_ARGS: dict[str, type[BaseModel]] = {
    "export_image": ImageArgs,
    "export_sheet": SheetArgs,
    "export_animation": AnimationArgs,
    "export_aseprite": AsepriteArgs,
    "export_palette": PaletteArgs,
    "export_tileset": TilesetArgs,
}
