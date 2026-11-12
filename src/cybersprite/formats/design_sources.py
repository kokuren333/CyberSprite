"""Decode design references outside the indexed core, checking headers before load."""

from io import BytesIO

import numpy as np
from PIL import Image, UnidentifiedImageError

from cybersprite.core.errors import CyberSpriteError


def decode_design(data: bytes) -> np.ndarray:
    """Decode the first image only; original bytes remain the provenance artifact."""
    try:
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
            if max(width, height) > 8192 or width * height > 67_108_864:
                raise CyberSpriteError(
                    "E_LIMIT_EXCEEDED",
                    "Design source exceeds the input image limit.",
                    "Use an image <= 8192 pixels per side and <= 67108864 pixels.",
                    {"width": width, "height": height},
                )
            return np.array(image.convert("RGBA"), dtype=np.uint8)
    except Image.DecompressionBombError as error:
        raise CyberSpriteError(
            "E_LIMIT_EXCEEDED",
            "Design source exceeds the image decoder's pixel limit.",
            "Use an image <= 8192 pixels per side and <= 67108864 pixels.",
        ) from error
    except (OSError, ValueError, UnidentifiedImageError) as error:
        raise CyberSpriteError(
            "E_IO",
            f"Cannot decode design source: {error}",
            "Use a readable PNG, GIF, BMP, JPEG, or WebP image.",
        ) from error
