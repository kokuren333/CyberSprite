"""The sole Pillow boundary: input raster decoding only (§8.1)."""

from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from ._common import PipelineError, require


def decode_raster(path):
    """Decode coalesced RGBA frames; report depth/mode/profile reductions."""
    try:
        with Image.open(Path(path)) as image:
            require(
                image.format in ("PNG", "GIF", "BMP", "JPEG", "WEBP"),
                "Unsupported raster format.",
                "Use PNG, GIF, BMP, JPEG or WebP.",
            )
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
                warnings.append(
                    {"code": "W_DROPPED_ON_IMPORT", "detail": f"Converted {detail} to 8-bit RGBA."}
                )
            if image.info.get("icc_profile"):
                warnings.append(
                    {
                        "code": "W_DROPPED_ON_IMPORT",
                        "detail": "Embedded ICC profile was discarded during 8-bit RGBA decoding.",
                    }
                )
            for frame in range(getattr(image, "n_frames", 1)):
                image.seek(frame)
                frames.append(np.array(image.convert("RGBA"), dtype=np.uint8, copy=True))
                durations.append(int(image.info.get("duration", 100)))
            require(
                all(f.shape == frames[0].shape for f in frames),
                "Decoded frame dimensions must match.",
            )
            return frames, {"format": image.format, "durations_ms": durations, "warnings": warnings}
    except (OSError, UnidentifiedImageError) as exc:
        raise PipelineError(
            "E_IO",
            f"Cannot decode raster: {Path(path).name}.",
            "Check that the file exists and is a valid supported raster.",
            path=str(path),
        ) from exc


def split_sheet(images, sheet):
    """Split a static raster into complete row-major cells for both input surfaces."""
    if sheet is None:
        return images
    keys = {"cell_w", "cell_h", "offset_x", "offset_y", "spacing"}
    require(
        isinstance(sheet, dict) and not set(sheet) - keys,
        "sheet must contain integer cell dimensions, offsets, and spacing.",
    )
    require(all(type(v) is int for v in sheet.values()), "sheet values must be integers.")
    w, h = sheet.get("cell_w", 0), sheet.get("cell_h", 0)
    ox, oy, gap = (sheet.get(k, 0) for k in ("offset_x", "offset_y", "spacing"))
    require(
        w > 0 and h > 0 and min(ox, oy, gap) >= 0,
        "Use positive sheet cell sizes and nonnegative offsets and spacing.",
    )
    require(len(images) == 1, "sheet requires exactly one static input image.")
    image = images[0]
    xs = range(ox, image.shape[1] - w + 1, w + gap)
    ys = range(oy, image.shape[0] - h + 1, h + gap)
    require(
        0 < len(xs) * len(ys) <= 4096,
        "Use sheet sizes and offsets yielding 1..4096 complete cells.",
    )
    return [image[y : y + h, x : x + w].copy() for y in ys for x in xs]
