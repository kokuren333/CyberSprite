"""Apply explicit outline settings and report caller/preset choices (§11.7)."""

import numpy as np

from ._common import PipelineError, integer, neighbors, require
from .cleanup import indexed_image
from .quantize import BAYER


def outline_and_dither(images, palette, *, transparent_index=0, outline=None,
                       dither=None, chosen_by=None):
    outline = {"mode": "keep", **(outline or {})}
    dither = {"type": "none", "strength": 255, **(dither or {})}
    require(outline["mode"] in ("keep", "add"), "Outline mode must be keep or add.")
    require(dither["type"] == "none" or dither["type"] in BAYER, "Unknown dither type.")
    integer(dither["strength"], "dither strength", 0, 255)
    locked, outputs, added = [tuple(c) for c in palette], [], []
    if isinstance(images, np.ndarray):
        images = [images]
    images = list(images)
    require(bool(images), "At least one index frame is required.")
    for image in images:
        indexed_image(image, locked, transparent_index)
    if outline["mode"] == "add":
        require("color" in outline, "Adding an outline requires a palette index or RGBA color.")
        color = outline["color"]
        if isinstance(color, (int, np.integer)):
            color = integer(color, "outline index", 0, len(locked) - 1)
        else:
            require(len(color) in (3, 4), "Outline color must be RGB or RGBA.")
            color = tuple(integer(v, "outline channel", 0, 255) for v in color)
            if len(color) == 3:
                color = (*color, 255)
            require(color[3] == 255, "An added outline color must be opaque.")
            if not any(c == color and i != transparent_index for i, c in enumerate(locked)):
                if len(locked) >= 256:
                    raise PipelineError("E_LIMIT_EXCEEDED", "No palette slot remains for the outline color.",
                                        "Choose an existing palette index or reduce extracted colors.",
                                        gate="palette_budget", palette_size=len(locked) + 1,
                                        palette_added=[color])
                locked.append(color)
                added.append(color)
            color = next(i for i, c in enumerate(locked) if c == color and i != transparent_index)
        require(color != transparent_index and locked[color][3] == 255,
                "Outline index must refer to an opaque nontransparent entry.")
        connectivity = outline.get("connectivity", 8)
        integer(connectivity, "outline connectivity", 4, 8)
        require(connectivity in (4, 8), "Outline connectivity must be 4 or 8.")
        for image in images:
            out = image.copy()
            h, w = image.shape
            for y, x in np.argwhere(image != transparent_index):
                for xx, yy in neighbors(int(x), int(y), w, h, connectivity):
                    if image[yy, xx] == transparent_index:
                        out[yy, xx] = color
            outputs.append(out)
        outline = {**outline, "color_index": color, "connectivity": connectivity}
    else:
        outputs = [image.copy() for image in images]
    owners = {"outline": "preset", "dither": "preset", **(chosen_by or {})}
    require(all(owner in ("preset", "caller") for owner in owners.values()),
            "Choice owner must be preset or caller.")
    return outputs, locked, {"outline": outline, "dither": dither, "chosen_by": owners,
                             "palette_added": added}
