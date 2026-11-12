"""The sole Pillow boundary: input raster decoding only (§8.1)."""

from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from ._common import PipelineError, require


def decode_raster(path):
    """Decode coalesced RGBA frames; report depth/mode/profile reductions."""
    try:
        with Image.open(Path(path)) as image:
            require(image.format in ("PNG", "GIF", "BMP", "JPEG", "WEBP"),
                    "Unsupported raster format.", "Use PNG, GIF, BMP, JPEG or WebP.")
            warnings, frames, durations = [], [], []
            # Pillow exposes 16-bit RGB PNGs as RGB after decoding. Inspect
            # only the standard IHDR header so that this reduction is reported.
            png_16bit = False
            if image.format == "PNG":
                with Path(path).open("rb") as source:
                    header = source.read(25)
                png_16bit = len(header) == 25 and header[24] == 16
            if png_16bit or image.mode in ("CMYK", "I", "F", "I;16", "I;16B", "I;16L"):
                detail = "16-bit PNG" if png_16bit else image.mode
                warnings.append({"code": "W_DROPPED_ON_IMPORT", "detail": f"Converted {detail} to 8-bit RGBA."})
            if image.info.get("icc_profile"):
                warnings.append({"code": "W_DROPPED_ON_IMPORT", "detail": "Embedded ICC profile was discarded during 8-bit RGBA decoding."})
            for frame in range(getattr(image, "n_frames", 1)):
                image.seek(frame)
                frames.append(np.array(image.convert("RGBA"), dtype=np.uint8, copy=True))
                durations.append(int(image.info.get("duration", 100)))
            require(all(f.shape == frames[0].shape for f in frames), "Decoded frame dimensions must match.")
            return frames, {"format": image.format, "durations_ms": durations, "warnings": warnings}
    except (OSError, UnidentifiedImageError) as exc:
        raise PipelineError("E_IO", f"Cannot decode raster: {Path(path).name}.",
                            "Check that the file exists and is a valid supported raster.", path=str(path)) from exc
