"""Optional generation backends. Importing this package never imports torch or Diffusers."""

from typing import TYPE_CHECKING

from .contracts import (
    Availability,
    GeneratedImage,
    GenerationBackend,
    GenerationRequest,
    ModelInfo,
)

if TYPE_CHECKING:
    from .service import accept_license


def __getattr__(name):
    if name == "accept_license":
        from .service import accept_license

        return accept_license
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Availability",
    "GeneratedImage",
    "GenerationBackend",
    "GenerationRequest",
    "ModelInfo",
    "accept_license",
]
