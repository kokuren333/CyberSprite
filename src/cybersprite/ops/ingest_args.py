"""Ingestion contracts, independent of decoding and pipeline execution."""

from typing import Annotated, Literal

from pydantic import Field

from cybersprite.core.models import Model, Source, SourceModel
from cybersprite.pipeline.args import PipelineSettings

Nonnegative = Annotated[int, Field(ge=0)]
Positive = Annotated[int, Field(ge=1)]


class Provenance(Model):
    license: Annotated[str, Field(min_length=1)] = Field(
        description="Usage license identifier; use unknown when usage terms are unknown."
    )
    kind: Literal["imported", "generated"] = Field(
        "imported", description="Source origin: imported or generated."
    )
    provider: str = Field("file", description="Input provider name, for example file.")
    prompt: str = Field(
        "", description="Original generation prompt; empty for non-generated input."
    )
    negative_prompt: str = Field("", description="Original negative generation prompt, if any.")
    model: SourceModel | None = Field(
        None, description="Generator model identifier and version, if any."
    )
    url: str = Field("", description="Source attribution URL, if available.")
    rights_note: str = Field("", description="Additional usage-rights or attribution notes.")
    seed: int | None = Field(None, description="Original generation seed, if known.")
    params: dict = Field(
        default_factory=dict, description="Original generation parameters retained as provenance."
    )


class Target(Model):
    mode: Literal["new_layer", "layer"] = Field(
        "new_layer",
        description="Place in a new image layer or an explicitly referenced existing layer.",
    )
    layer: str | None = Field(None, description="Target layer ID, unique name, or group path.")
    name: Annotated[str, Field(min_length=1, max_length=255)] | None = Field(
        None, description="Human-readable resource name, at most 255 characters."
    )
    frame: Nonnegative = Field(0, description="Zero-based placement starting frame.")
    x: int = Field(0, description="Horizontal pixel coordinate from the canvas left edge.")
    y: int = Field(0, description="Vertical pixel coordinate from the canvas top edge.")
    add_frames: bool = Field(
        True, description="Extend the timeline when imported frames exceed its current length."
    )


class Sheet(Model):
    cell_w: Positive = Field(description="Sheet cell width in integer pixels.")
    cell_h: Positive = Field(description="Sheet cell height in integer pixels.")
    offset_x: Nonnegative = Field(0, description="Horizontal sheet margin before the first cell.")
    offset_y: Nonnegative = Field(0, description="Vertical sheet margin before the first cell.")
    spacing: Nonnegative = Field(0, description="Integer gap between neighboring sheet items.")


class ImportArgs(Model):
    files: str | Annotated[list[str], Field(min_length=1, max_length=4096)] | None = Field(
        None,
        description="One input raster path or a list of paths; mutually exclusive with source.",
    )
    sheet: Sheet | None = Field(
        None,
        description=(
            "Split one static input into complete cells using integer sizes, offsets, and spacing."
        ),
    )
    preset: Literal["ai", "exact", "upscaled", "photo"] = Field(
        "ai", description="Pipeline preset: ai, exact (lossless), upscaled, or photo."
    )
    pipeline: PipelineSettings = Field(
        default_factory=lambda: PipelineSettings.model_validate({}),
        description="Documented section overrides; unspecified fields inherit preset values.",
    )
    target: Target = Field(
        default_factory=lambda: Target.model_validate({}),
        description=(
            "Placement layer, zero-based starting frame, integer position, and "
            "frame-extension policy."
        ),
    )
    provenance: Provenance | None = Field(
        None,
        description=(
            "Input origin and usage terms; license is required for new files (use "
            "unknown when unknown)."
        ),
    )
    on_gate_fail: Literal["reject", "accept"] = Field(
        "reject",
        description=(
            "Reject failed gates or explicitly accept and record overridden gates; "
            "capacity/freeze limits remain enforced."
        ),
    )
    source: str | None = Field(
        None,
        description=(
            "Existing source ID to reconvert with its original provenance; mutually "
            "exclusive with files."
        ),
    )
    pipeline_only: bool = Field(
        False,
        description=(
            "Preview conversion only; requires dry_run=true and returns pipeline_accepted "
            "instead of would_commit. Placement and new-file provenance are not checked."
        ),
    )


class ImportResult(Model):
    source: str | None
    accepted: bool
    report_path: str
    stage_paths: list[str]
    gates: list[dict]
    placed: dict | None


class ListSourcesArgs(Model):
    pass


class ListSourcesResult(Model):
    sources: list[dict]


class GetSourceArgs(Model):
    id: str = Field(description="Stored source ID, such as SRC1.")
    include_report: bool = Field(
        False, description="Include the saved pipeline report in the source response."
    )


class GetSourceResult(Source):
    report: dict | None = None


class AddSourceArgs(Model):
    files: str | Annotated[list[str], Field(min_length=1, max_length=4096)] = Field(
        description="Design image paths to retain without placing pixels on the canvas.",
        json_schema_extra={"x-cybersprite-path": "input"},
    )
    provenance: Provenance = Field(description="Origin and license; use unknown if unknown.")


class AddSourceResult(Model):
    source: str | None
    files: list[str]
