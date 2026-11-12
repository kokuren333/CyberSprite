"""Optional generation backends. Importing this package never imports torch or Diffusers."""

from .contracts import (
    Availability,
    GeneratedImage,
    GenerationBackend,
    GenerationRequest,
    ModelInfo,
)
from .service import accept_license

__all__ = [
    "Availability",
    "GeneratedImage",
    "GenerationBackend",
    "GenerationRequest",
    "ModelInfo",
    "accept_license",
]
