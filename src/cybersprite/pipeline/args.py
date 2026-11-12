"""Strict, documented pipeline overrides shared by ingest and convert."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from cybersprite.core.models import Model

Byte = Annotated[int, Field(ge=0, le=255)]
Positive = Annotated[int, Field(ge=1)]
Nonnegative = Annotated[int, Field(ge=0)]
Distance = Annotated[int, Field(ge=0, le=65535)]
Color = (
    Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")]
    | Annotated[list[Byte], Field(min_length=3, max_length=4)]
)


class GridSettings(Model):
    method: str | None = Field(None, description="Optional plugin grid preprocessing method.")
    params: dict = Field(default_factory=dict, description="Plugin-specific parameters.")
    mode: Literal["auto", "fixed", "target", "none"] = Field(
        "auto",
        description=(
            "Detect a rational grid, specify integer cells, divide into "
            "target counts, or keep input pixels."
        ),
    )
    min_cell: Positive = Field(2, description="Smallest auto pitch in input pixels.")
    max_cell: Positive = Field(64, description="Largest auto pitch in input pixels.")
    force_square: bool = Field(
        True, description="Choose a common pitch across both axes, allowing image-span rounding."
    )
    harmonic_tolerance: Annotated[int, Field(ge=0, le=1000)] = Field(
        850,
        description=(
            "Legacy peak harmonic tolerance in thousandths; exact integer boundaries take priority."
        ),
    )
    min_peak: Positive = Field(
        1500, description="Minimum normalized boundary alignment score for auto detection."
    )
    purity_tolerance: Byte = Field(
        16, description="Maximum per-channel deviation from cell median for grid purity."
    )
    cell_w: Positive = Field(
        1, description="Fixed grid cell width in integer input pixels; required in fixed mode."
    )
    cell_h: Positive = Field(
        1, description="Fixed grid cell height in integer input pixels; required in fixed mode."
    )
    offset_x: Nonnegative = Field(
        0, description="Fixed grid horizontal phase, smaller than cell_w."
    )
    offset_y: Nonnegative = Field(0, description="Fixed grid vertical phase, smaller than cell_h.")
    target_w: Positive = Field(1, description="Required output column count in target mode.")
    target_h: Positive = Field(1, description="Required output row count in target mode.")


class DownsampleSettings(Model):
    method: str = Field(
        "auto", description="Cell representative method; pixeloe requires a configured plugin."
    )
    params: dict = Field(default_factory=dict, description="Plugin-specific parameters.")
    alpha_threshold: Byte = Field(
        128, description="Minimum source alpha counted as opaque; a cell needs a majority."
    )


class BackgroundSettings(Model):
    mode: Literal["keep", "key", "auto"] = Field(
        "keep",
        description="Keep background, flood a supplied key, or estimate a border-supported key.",
    )
    color: Color = Field(
        "#000000", description="Key RGB/RGBA array or #rrggbb/#rrggbbaa; required for key mode."
    )
    tolerance: Byte = Field(0, description="Per-channel distance allowed in key mode.")
    auto_tolerance: Distance = Field(
        2500,
        description="Fixed-point Oklab distance for auto border support and connected removal.",
    )


class PaletteSettings(Model):
    method: str | None = Field(None, description="Optional plugin quantization method.")
    params: dict = Field(default_factory=dict, description="Plugin-specific parameters.")
    mode: Literal["project", "fixed", "extract", "exact"] = Field(
        "extract",
        description=(
            "Use project colors, supplied colors, perceptual extraction, or exact input colors."
        ),
    )
    source: (
        Annotated[str, Field(json_schema_extra={"x-cybersprite-path": "palette"})] | list[Color]
    ) = Field(
        default_factory=lambda: [],
        description="Fixed palette preset/file name or RGB/RGBA/hex color list.",
    )
    max_colors: Annotated[int, Field(ge=1, le=255)] = Field(
        32, description="Maximum opaque extracted/exact colors, excluding transparency."
    )
    refine_iterations: Nonnegative = Field(
        8, description="Maximum deterministic integer k-means refinement passes."
    )
    min_color_pixels: Nonnegative = Field(
        0, description="Merge colors used by fewer pixels; protected colors survive."
    )
    merge_distance: Distance = Field(
        1800,
        description=(
            "Merge near-duplicate colors within this fixed-point Oklab "
            "distance before allocating slots; zero disables."
        ),
    )
    salient_distance: Distance = Field(
        7000,
        description=(
            "Reserve 2-4 pixel accents separated from every other color by "
            "this Oklab distance; zero disables."
        ),
    )
    protect: list[Color] = Field(
        default_factory=list,
        description=(
            "Reserve these opaque colors, supplied as RGB/RGBA arrays or hex "
            "strings; also protect their cleanup indices."
        ),
    )


class CleanupSettings(Model):
    method: str | None = Field(None, description="Optional plugin indexed cleanup method.")
    params: dict = Field(default_factory=dict, description="Plugin-specific parameters.")
    min_cluster: Positive = Field(
        2, description="Remove smaller same-index components; one disables cleanup."
    )
    connectivity: Literal[4, 8] = Field(
        8, description="Neighborhood used to form same-index components."
    )
    max_passes: Positive = Field(2, description="Maximum simultaneous cleanup passes.")
    protect: list[Nonnegative] = Field(
        default_factory=list,
        description="Palette indices preserved by cleanup, including isolated accents.",
    )


class DitherSettings(Model):
    type: Literal["none", "bayer2", "bayer4", "bayer8"] = Field(
        "none", description="Optional ordered Bayer dithering; none preserves solid color regions."
    )
    strength: Byte = Field(255, description="Ordered dither strength from zero to 255.")


class OutlineSettings(Model):
    mode: Literal["keep", "add"] = Field(
        "keep", description="Keep current pixels or add an outer outline."
    )
    color: Nonnegative | Color = Field(
        0, description="Opaque palette index or RGB/RGBA/hex outline color; required for add mode."
    )
    connectivity: Literal[4, 8] = Field(8, description="Neighborhood used to expand the outline.")


class GateSettings(Model):
    grid_score: Annotated[list[Nonnegative], Field(min_length=2, max_length=2)] | None = Field(
        None, description="Minimum cell purity [fail, warn], or null to skip this gate."
    )
    fidelity: Annotated[list[Nonnegative], Field(min_length=2, max_length=2)] | None = Field(
        None, description="Maximum mean squared Oklab palette error [fail, warn], or null to skip."
    )


class PluginStepSettings(Model):
    method: str = Field(description="Registered reconstruct method; replaces grid and downsample.")
    params: dict = Field(default_factory=dict, description="Plugin-specific parameters.")


class PipelineSettings(Model):
    reconstruct: PluginStepSettings | None = Field(
        None, description="Optional composite preprocessing before the single quantization step."
    )

    @model_validator(mode="before")
    @classmethod
    def quantize_alias(cls, value):
        if isinstance(value, dict) and "quantize" in value:
            value = dict(value)
            if "palette" in value:
                raise ValueError("Use either quantize or palette, not both.")
            value["palette"] = value.pop("quantize")
        return value

    grid: GridSettings = Field(
        default_factory=lambda: GridSettings.model_validate({}),
        description="Grid detection, phase, rational cell counts, and purity.",
    )
    downsample: DownsampleSettings = Field(
        default_factory=lambda: DownsampleSettings.model_validate({}),
        description="Cell sampling and alpha policy.",
    )
    background: BackgroundSettings = Field(
        default_factory=lambda: BackgroundSettings.model_validate({}),
        description="Border-connected background removal.",
    )
    palette: PaletteSettings = Field(
        default_factory=lambda: PaletteSettings.model_validate({}),
        description="Palette locking, extraction, merging, and accent protection.",
    )
    cleanup: CleanupSettings = Field(
        default_factory=lambda: CleanupSettings.model_validate({}),
        description="Indexed component cleanup and protected indices.",
    )
    dither: DitherSettings = Field(
        default_factory=lambda: DitherSettings.model_validate({}),
        description="Optional ordered dithering.",
    )
    outline: OutlineSettings = Field(
        default_factory=lambda: OutlineSettings.model_validate({}),
        description="Explicit outline decision.",
    )
    gates: GateSettings = Field(
        default_factory=lambda: GateSettings.model_validate({}),
        description="Calibrated gate threshold overrides.",
    )
