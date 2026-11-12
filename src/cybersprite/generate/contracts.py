"""Generation-only contracts; no canvas or project mutation is available here."""

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Protocol

from pydantic import Field

from cybersprite.core.models import Model


class Availability(Model):
    available: bool
    reason: str = ""


class ModelInfo(Model):
    id: str
    license: str
    alias: str | None = None
    source_url: str = ""
    local_path: str = ""
    base_model: str | None = None
    sha256: str = ""
    adapters: list["ModelInfo"] = Field(default_factory=list)


class GenerationRequest(Model):
    backend: str = Field(description="Configured backend name: diffusers or command:<name>.")
    prompt: str = Field(description="Image generation prompt, passed as one argument.")
    negative_prompt: str = Field("", description="Content to avoid in generation.")
    width: Annotated[int, Field(ge=1, le=16384, description="Requested width in pixels.")]
    height: Annotated[int, Field(ge=1, le=16384, description="Requested height in pixels.")]
    seed: Annotated[int | None, Field(ge=0, le=2**63 - 1)] = Field(
        None, description="Generation seed; omitted seeds are chosen and recorded by the backend."
    )
    count: Annotated[int, Field(ge=1, le=4)] = Field(
        1, description="Number of images, at most four."
    )
    model: str | None = Field(
        None, description="Configured model alias; arbitrary IDs are refused."
    )
    params: dict = Field(default_factory=dict, description="Backend parameters from its schema.")
    accept_model_license: bool = Field(
        False, description="Accept configured model and adapter terms."
    )


class GeneratedImage(Model):
    path: Path
    seed: int
    model: ModelInfo
    params: dict


class GenerationBackend(Protocol):
    name: str
    params_schema: type[Model]

    def availability(self) -> Availability: ...
    def list_models(self) -> list[ModelInfo]: ...
    def generate(
        self, request: GenerationRequest, out_dir: Path, progress: Callable[[float, str], None]
    ) -> list[GeneratedImage]: ...
