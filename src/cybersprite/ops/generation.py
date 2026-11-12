"""Registry definitions for source-only generation and backend inspection."""

from typing import Literal

from pydantic import Field

from cybersprite.core.errors import invalid
from cybersprite.core.models import Model
from cybersprite.core.registry import EmptyResult, Op
from cybersprite.generate.contracts import GenerationRequest
from cybersprite.generate.registry import BackendRegistry


class BackendResult(Model):
    backends: list[dict] = Field(
        description="Backends with availability reasons, models and schemas."
    )


class GenerationResult(Model):
    sources: list[str] = Field(description="Generated source IDs for a later import_image call.")
    files: list[str] = Field(description="Project-relative generated original file paths.")
    use: Literal["design", "canvas"]
    model_terms: list[dict] = Field(
        description="License badges and messages for models, adapters and bases."
    )
    message: str = Field(description="Plain-text terms for the GUI generation result.")


def _top_only(_ctx, _args):
    raise invalid("generate_image must be invoked as a top-level call.")


def register_generators(registry):
    registry.register(
        Op(
            "list_generators",
            EmptyResult,
            lambda _ctx, _args: BackendRegistry().describe(),
            BackendResult,
            "query",
            "R",
            description="List configured generators, models and availability reasons. "
            "No generation or plugin loading occurs.",
        )
    )
    registry.register(
        Op(
            "generate_image",
            GenerationRequest,
            _top_only,
            GenerationResult,
            "ingest",
            "G",
            description="Generate originals with accepted model terms "
            "and provenance in source/. Canvas placement requires a separate import_image "
            "call; unavailable backends and unaccepted licenses fail explicitly.",
        )
    )
