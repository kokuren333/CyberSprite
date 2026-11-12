"""Pure platform snapshots, integer color constraints and tick allocation."""

import json
from functools import lru_cache
from itertools import islice, product
from typing import Annotated, Literal, get_args

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .color import rgb_to_oklab_fixed, rgb_to_oklab_fixed_numpy

Positive = Annotated[int, Field(ge=1)]
Budget = Annotated[int, Field(ge=1, le=256)]
Range = Annotated[list[int], Field(min_length=2, max_length=2)]


class Data(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def reset_defaults(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            for name, field in cls.model_fields.items():
                key = field.alias or name
                if (
                    value.get(key, 0) is None
                    and not field.is_required()
                    and type(None) not in get_args(field.annotation)
                ):
                    value.pop(key)
        return value


class Size(Data):
    w: Positive = 1
    h: Positive = 1


class Tick(Data):
    num: Positive = 1
    den: Positive = 60


class Bits(Data):
    r: Annotated[int, Field(ge=1, le=8)] = 8
    g: Annotated[int, Field(ge=1, le=8)] = 8
    b: Annotated[int, Field(ge=1, le=8)] = 8


class Color(Data):
    model: Literal["rgb", "master"] = "rgb"
    bits: Bits | None = None
    expand: Literal["replicate", "shift"] | None = None
    master_palette: str | None = None
    master_colors: list[
        Annotated[list[Annotated[int, Field(ge=0, le=255)]], Field(min_length=3, max_length=3)]
    ] = Field(default_factory=list)
    alpha: Literal["binary", "any"] = "any"

    @model_validator(mode="after")
    def complete(self):
        if self.model == "master" and not self.master_palette:
            raise ValueError("Master color model requires master_palette.")
        if self.bits is not None and self.expand is None:
            self.expand = "replicate"
        return self


class PaletteStructure(Data):
    rows: Positive = 1
    row_size: Budget = 16
    slot0: Literal["transparent", "shared", "color"] = "transparent"
    unit: Literal["object", "tile", "block", "layer"] = "object"
    block: Size | None = None


class Flips(Data):
    x: bool = False
    y: bool = False
    d: bool = False


class TileSpec(Size):
    bpp: Annotated[int, Field(ge=1, le=8)] | None = None
    flips: Flips = Field(default_factory=Flips)
    unique_max: Positive | None = None
    map_max: Size | None = None


class ObjectSpec(Data):
    sizes: list[Annotated[list[Positive], Field(min_length=2, max_length=2)]] | None = None
    notes: str = ""


class System(Data):
    id: str = "free"
    screen: Size | None = None
    pixel_aspect: Size = Field(default_factory=Size)
    color: Color = Field(default_factory=Color)
    palette: PaletteStructure | None = None
    tile: TileSpec | None = None
    object: ObjectSpec | None = None
    native: list[str] = Field(default_factory=list)


class Canvas(Size):
    fixed: bool = False


class Colors(Data):
    palette_max: Budget | None = None
    opaque_max: Budget | None = None


class Animation(Data):
    tick: Tick | None = None
    tags: list[str] = Field(default_factory=list)
    tags_optional: list[str] = Field(default_factory=list)
    frames_max: Positive | None = None


class Asset(Data):
    class_: str = Field("custom", alias="class")
    role: Literal["sprite", "tileset", "background", "ui", "portrait", "effect"] = "sprite"
    canvas: Canvas | None = None
    colors: Colors = Field(default_factory=Colors)
    animation: Animation = Field(default_factory=Animation)


class PreviewDefaults(Data):
    scale: Annotated[int, Field(ge=1, le=16)] | None = None
    backgrounds: list[str] = Field(default_factory=list)


class SheetDefaults(Data):
    layout: str = "horizontal"
    data_format: str = "json-hash"


class ExportDefaults(Data):
    scale: Annotated[int, Field(ge=1, le=16)] | None = None
    review_scale: Annotated[int, Field(ge=1, le=16)] | None = None
    sheet: SheetDefaults | None = None


class PipelineDefaults(Data):
    preset: Literal["ai", "exact", "upscaled", "photo"] | None = None
    overrides: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def integers(self):
        check_integer_data(self.overrides)
        return self


class Defaults(Data):
    grid: Size | None = None
    palette: str | list[str] | None = None
    preview: PreviewDefaults = Field(default_factory=PreviewDefaults)
    export: ExportDefaults = Field(default_factory=ExportDefaults)
    pipeline: PipelineDefaults = Field(default_factory=PipelineDefaults)


class Validation(Data):
    palette_max: Budget | None = None
    colors_per_frame_max: Positive | None = None
    orphan_pixels_max: Annotated[int, Field(ge=0)] | None = None
    min_cluster: Positive | None = None
    require_tag_coverage: bool | None = None
    silhouette_jitter_max: Annotated[int, Field(ge=0)] | None = None
    severity: dict[str, Literal["error", "warning", "info", "off"]] = Field(default_factory=dict)


class Outline(Data):
    style: str | None = None
    dark_permille: Range | None = None


class Corpus(Data):
    name: str
    count: Positive
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Craft(Data):
    basis: Literal["authored", "measured"] = "authored"
    corpus: Corpus | None = None
    ramp_steps: Range | None = None
    outline: Outline | None = None
    dither: str | None = None
    light: str | None = None
    fill_permille: Range | None = None
    depth_max: Range | None = None
    flat_permille: Range | None = None
    region_density_x100: Range | None = None
    parts: dict[str, Range] = Field(default_factory=dict)

    @model_validator(mode="after")
    def measured_corpus(self):
        if self.basis == "measured" and self.corpus is None:
            raise ValueError("Measured craft requires a corpus record.")
        for name in ("fill_permille", "flat_permille"):
            value = getattr(self, name)
            if value is not None and not 0 <= value[0] <= value[1] <= 1000:
                raise ValueError(f"{name} must be an ordered permille range within 0..1000.")
        return self


class Platform(Data):
    id: str = "custom"
    title: str = "Custom platform"
    preset_version: Annotated[int, Field(ge=0)] = 0
    origin: str = "custom"
    overrides: list[str] = Field(default_factory=list)
    system: System = Field(default_factory=System)
    asset: Asset = Field(default_factory=lambda: Asset.model_validate({}))
    defaults: Defaults = Field(default_factory=Defaults)
    validation: Validation = Field(default_factory=Validation)
    craft: Craft | None = None
    workflow: Literal["direct", "silhouette-first", "turnaround-parts", "tiles-first", "scene"] = (
        "direct"
    )
    notes: str = ""


def check_integer_data(value):
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("Platform object keys must be strings.")
        for key in sorted(value):
            check_integer_data(value[key])
    elif isinstance(value, list):
        for item in value:
            check_integer_data(item)
    elif value is not None and type(value) not in (int, str, bool):
        raise ValueError("Platform data accepts only integers, strings, booleans and null.")


def expand_channel(value: int, bits: int, mode: str | None) -> int:
    if mode == "shift":
        return value << (8 - bits)
    result, count = value, bits
    while count < 8:
        result = (result << bits) | value
        count += bits
    return result >> (count - 8)


@lru_cache(maxsize=16)
def _candidates(bits: tuple[int, int, int], mode: str | None):
    values = [tuple(expand_channel(c, n, mode) for c in range(1 << n)) for n in bits]
    candidates = np.array(list(product(*values)), dtype=np.uint8)
    labs = rgb_to_oklab_fixed_numpy(candidates)
    candidates.flags.writeable = labs.flags.writeable = False
    return candidates, labs


@lru_cache(maxsize=4096)
def nearest_rgb(
    rgb: tuple[int, int, int], color_json: str, master: tuple = ()
) -> tuple[int, int, int]:
    color = Color.model_validate_json(color_json)
    if color.model == "master":
        if not master:
            raise ValueError("A master platform snapshot requires a nonempty master_colors table.")
        candidates = np.array(sorted(set(master)), dtype=np.uint8)
        labs = rgb_to_oklab_fixed_numpy(candidates)
    elif color.bits is None:
        return rgb
    else:
        bits = (color.bits.r, color.bits.g, color.bits.b)
        if all(
            expand_channel(v >> (8 - n), n, color.expand) == v
            for v, n in zip(rgb, bits, strict=True)
        ):
            return rgb
        if sum(bits) <= 16:
            candidates, labs = _candidates(bits, color.expand)
        else:
            channels = [
                tuple(expand_channel(c, n, color.expand) for c in range(1 << n)) for n in bits
            ]
            iterator = product(*channels)
            lab = np.array(rgb_to_oklab_fixed(rgb), dtype=np.int64)
            best = None
            while batch := list(islice(iterator, 4096)):
                candidates = np.array(batch, dtype=np.uint8)
                labs = rgb_to_oklab_fixed_numpy(candidates)
                distances = np.sum((labs - lab) ** 2, axis=1)
                index = int(np.argmin(distances))
                value = (int(distances[index]), tuple(int(v) for v in candidates[index]))
                if best is None or value < best:
                    best = value
            assert best is not None
            return best[1][0], best[1][1], best[1][2]
    lab = np.array(rgb_to_oklab_fixed(rgb), dtype=np.int64)
    distances = np.sum((labs.astype(np.int64) - lab) ** 2, axis=1)
    chosen = candidates[int(np.argmin(distances))]
    return int(chosen[0]), int(chosen[1]), int(chosen[2])


def tick_durations(ticks: list[int], tick: Tick) -> list[int]:
    total, previous, result = 0, 0, []
    for count in ticks:
        total += count
        end = total * 1000 * tick.num // tick.den
        result.append(end - previous)
        previous = end
    return result


def guide(platform: Platform) -> str:
    p = platform
    canvas = p.asset.canvas
    lines = [
        f"Platform: {p.id} ({p.title})",
        f"Canvas: {canvas.w}x{canvas.h}" if canvas else "Canvas: unrestricted",
        f"Opaque colors per frame: {p.asset.colors.opaque_max}",
        f"Color: {p.system.color.model}; alpha: {p.system.color.alpha}",
        f"Workflow: skills/workflows/{p.workflow}.md",
        "Check constraints, view all frames at 1x, validate, then inspect exported files.",
    ]
    if p.craft:
        lines.append(
            "Craft guidance (informational): "
            + json.dumps(
                p.craft.model_dump(exclude_none=True), sort_keys=True, separators=(",", ":")
            )
        )
    return "\n".join(lines).encode("utf-8")[:2048].decode("utf-8", errors="ignore")
