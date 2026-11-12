"""Functional preview overlays; these arrays never enter project data or exports."""

import numpy as np

from .pixels import resolve_color, rgba
from .render import render

# Original 3x5 digits, solely for coordinate labels.
DIGITS = (
    (7, 5, 5, 5, 7),
    (2, 6, 2, 2, 7),
    (7, 1, 7, 4, 7),
    (7, 1, 7, 1, 7),
    (5, 5, 7, 1, 1),
    (7, 4, 7, 1, 7),
    (7, 4, 7, 5, 7),
    (7, 1, 1, 1, 1),
    (7, 5, 7, 5, 7),
    (7, 5, 7, 1, 7),
)


def scale_for(p, scale="auto", inline=False):
    maximum = max(p.canvas.width, p.canvas.height)
    scale = max(1, min(16, 512 // maximum)) if scale == "auto" else scale
    if inline:
        scale = min(scale, max(1, 1024 // maximum))
    return scale


def checker(image, background="checker", p=None):
    h, w = image.shape[:2]
    yy, xx = np.indices((h, w), dtype=np.int32)
    if background == "checker":
        shade = np.where(((xx // 4 + yy // 4) % 2) != 0, 224, 192).astype(np.int32)
        base = np.stack([shade, shade, shade], axis=2)
    else:
        color = rgba(p.palette.colors[resolve_color(p.palette, background)])
        base = np.full((h, w, 3), color[:3], dtype=np.int32)
    alpha = image[:, :, 3:4].astype(np.int32)
    rgb = (image[:, :, :3].astype(np.int32) * alpha + base * (255 - alpha) + 127) // 255
    return np.concatenate([rgb.astype(np.uint8), np.full((h, w, 1), 255, dtype=np.uint8)], axis=2)


def _label(image, x, y, number):
    h, w = image.shape[:2]
    for char in str(number):
        for j, row in enumerate(DIGITS[int(char)]):
            for i in range(3):
                if row & (1 << (2 - i)) and 0 <= y + j < h and 0 <= x + i < w:
                    image[y + j, x + i] = (32, 32, 32, 255)
        x += 4


def preview_array(
    p,
    frame,
    *,
    scale="auto",
    grid=False,
    rulers=False,
    onion=None,
    background="checker",
    layers=None,
    inline=False,
):
    scale = scale_for(p, scale, inline)
    data = render(p, frame, {"layers": layers})
    if onion:
        ghosts = []
        for offset in range(onion.get("prev", 0), 0, -1):
            if frame - offset >= 0:
                ghosts.append((frame - offset, (224, 96, 96)))
        for offset in range(onion.get("next", 0), 0, -1):
            if frame + offset < len(p.frames):
                ghosts.append((frame + offset, (96, 128, 224)))
        for f, tint in ghosts:
            ghost = render(p, f, {"layers": layers})
            visible = (ghost[:, :, 3] != 0) & (data[:, :, 3] == 0)
            data[visible, :3] = tint
            data[visible, 3] = 64
    image = checker(data, background, p)
    image = np.repeat(np.repeat(image, scale, 0), scale, 1)
    if grid:
        if scale >= 4:
            image[::scale, :] = (160, 160, 160, 255)
            image[:, ::scale] = (160, 160, 160, 255)
        g = p.canvas.grid
        for y in range(g.y % g.h, p.canvas.height, g.h):
            image[y * scale : y * scale + 2, :] = (96, 96, 96, 255)
        for x in range(g.x % g.w, p.canvas.width, g.w):
            image[:, x * scale : x * scale + 2] = (96, 96, 96, 255)
    if rulers:
        pad = 18
        h, w = image.shape[:2]
        bordered = np.full((h + pad, w + pad, 4), (240, 240, 240, 255), dtype=np.uint8)
        bordered[pad:, pad:] = image
        for value in range(0, p.canvas.width, 8):
            x = pad + value * scale
            bordered[pad - 3 : pad, x] = (32, 32, 32, 255)
            _label(bordered, x, 3, value)
        for value in range(0, p.canvas.height, 8):
            y = pad + value * scale
            bordered[y, pad - 3 : pad] = (32, 32, 32, 255)
            _label(bordered, 1, y, value)
        image = bordered
    if inline and max(image.shape[:2]) > 1024:
        step = (max(image.shape[:2]) + 1023) // 1024
        image = image[::step, ::step].copy()
    return image, scale
