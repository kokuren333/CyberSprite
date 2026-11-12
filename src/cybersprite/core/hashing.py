"""CSPX1 pixel identity (independent of image encoders)."""

import hashlib
import struct

import numpy as np

from .errors import invalid


def pixel_sha256(pixels: np.ndarray) -> str:
    if (
        pixels.dtype != np.uint8
        or not (pixels.ndim == 2 or pixels.ndim == 3 and pixels.shape[2] == 4)
        or min(pixels.shape[:2]) < 1
    ):
        raise invalid("Pixel hashing requires a nonempty uint8 indexed or RGBA array.")
    height, width = pixels.shape[:2]
    header = b"CSPX1" + struct.pack("<IIB", width, height, 0 if pixels.ndim == 2 else 1)
    return hashlib.sha256(header + pixels.tobytes(order="C")).hexdigest()
