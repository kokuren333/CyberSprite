"""Transient external input for CLI --input; never persists projects or provenance."""

from pathlib import Path

import numpy as np

from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.models import Frame, ImageCel
from cybersprite.core.normalize import normalize_cels
from cybersprite.core.pixels import pixels_to_rows
from cybersprite.core.projects import new_project


def quantize_arrays(images, options):
    """Flatten unequal cel/tile sizes for the shared M6 pure one-time quantizer."""
    from cybersprite.pipeline._common import PipelineError
    from cybersprite.pipeline.quantize import quantize

    images = list(images)
    if not images:
        raise invalid("No image pixels are available to quantize.")
    flat = np.concatenate([image.reshape(1, -1, 4) for image in images], axis=1)
    try:
        config = {"max_colors": 255, **options}
        if isinstance(config.get("source"), str):
            from cybersprite.core.pixels import rgba

            from .palette_files import read_palette

            config["source"] = [rgba(c) for c in read_palette(config["source"])]
        frames, palette, _ = quantize([flat], **config)
    except PipelineError as error:
        raise CyberSpriteError(error.code, error.message, error.hint, error.details) from error
    except TypeError as error:
        raise invalid("Invalid quantize options.", reason=str(error)) from error
    outputs, offset = [], 0
    for image in images:
        h, w = image.shape[:2]
        outputs.append(frames[0][0, offset : offset + w * h].reshape(h, w).copy())
        offset += w * h
    return outputs, palette


def load_external(path, options=None):
    path, options = Path(path), options or {}
    if path.suffix.lower() in (".ase", ".aseprite"):
        from .aseprite_io import read_aseprite

        return read_aseprite(path, options)[0]
    from cybersprite.pipeline._common import PipelineError
    from cybersprite.pipeline.decode import decode_raster

    try:
        images, info = decode_raster(path)
    except PipelineError as error:
        raise CyberSpriteError(error.code, error.message, error.hint, error.details) from error
    indices, palette = quantize_arrays(images, {"mode": "exact"})
    h, w = images[0].shape[:2]
    p = new_project(
        width=w,
        height=h,
        frames=len(images),
        name=path.stem,
        palette=["#" + bytes(c).hex() for c in palette],
    )
    p.frames = [Frame(duration_ms=max(1, min(65535, d or 100))) for d in info["durations_ms"]]
    p.layers[0].cels = [
        ImageCel(frame=n, x=0, y=0, w=w, h=h, pixels=pixels_to_rows(data))
        for n, data in enumerate(indices)
    ]
    return normalize_cels(p)
