"""Functional preview overlays; these arrays never enter project data or exports."""

from math import isqrt

import numpy as np

from .errors import invalid
from .limits import output_bytes
from .pixels import pixels_from_rows, resolve_color, rgba
from .references import resolve_tag
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
        color = (
            rgba(background)
            if isinstance(background, str) and len(background) == 7 and background.startswith("#")
            else rgba(p.palette.colors[resolve_color(p.palette, background)])
        )
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
    pad = 18 if rulers else 0
    output_bytes(p.canvas.width * scale + pad, p.canvas.height * scale + pad)
    data = render(p, frame, {"layers": layers})
    image = checker(np.zeros_like(data), background, p)
    if onion:
        start, end = 0, len(p.frames) - 1
        loop_tag = onion.get("loop_tag")
        if loop_tag:
            tag = resolve_tag(p, loop_tag)
            start, end = tag.from_, tag.to
            if not start <= frame <= end:
                raise invalid(
                    "Onion target frame must lie within loop_tag.", frame=frame, tag=tag.id
                )
        ghosts = []
        for key, direction, tint in (("prev", -1, (224, 96, 96)), ("next", 1, (96, 128, 224))):
            for offset in range(onion.get(key, 0), 0, -1):
                f = frame + direction * offset
                if loop_tag:
                    f = start + (f - start) % (end - start + 1)
                if start <= f <= end and f != frame:
                    ghosts.append((f, tint))
        for f, tint in ghosts:
            ghost = render(p, f, {"layers": layers})
            ghost[:, :, :3] = tint
            ghost[:, :, 3] = ((ghost[:, :, 3].astype(np.int32) + 1) // 2).astype(np.uint8)
            image = _over(ghost, image)
    image = _over(data, image)
    image = np.repeat(np.repeat(image, scale, 0), scale, 1)
    if grid:
        if scale >= 4:
            mask = np.zeros(image.shape[:2], dtype=bool)
            mask[::scale, :] = True
            mask[:, ::scale] = True
            image[mask, :3] = ((image[mask, :3].astype(np.int32) * 3 + 160 + 2) // 4).astype(
                np.uint8
            )
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


def _over(foreground, background):
    """Composite a decoration onto an opaque preview, with integer rounding."""
    alpha = foreground[:, :, 3:4].astype(np.int32)
    result = background.copy()
    result[:, :, :3] = (
        (
            foreground[:, :, :3].astype(np.int32) * alpha
            + background[:, :, :3].astype(np.int32) * (255 - alpha)
            + 127
        )
        // 255
    ).astype(np.uint8)
    return result


def composite_preview(p, fs, *, layout, scale="auto", **options):
    """Compose bounded thumbnails sequentially, avoiding a full-size frame stack."""

    def thumbnail(frame, factor, step):
        image, _ = preview_array(p, frame, scale=factor, inline=False, **options)
        return image[::step, ::step]

    return _contact_sheet(
        p.canvas.width,
        p.canvas.height,
        fs,
        thumbnail,
        layout=layout,
        scale=scale,
        pad=18 if options.get("rulers") else 0,
    )


def tileset_preview(p, ts, *, scale="auto", background="checker"):
    """Use existing preview decoration and data indices for a tileset contact sheet."""
    palette = np.array([rgba(color) for color in p.palette.colors], dtype=np.uint8)
    palette[p.palette.transparent_index, 3] = 0

    def thumbnail(index, factor, step):
        # Sample the repeated pixels directly, so large scales do not allocate huge tiles.
        yy = np.arange(0, ts.tile_h * factor, step, dtype=np.int32) // factor
        xx = np.arange(0, ts.tile_w * factor, step, dtype=np.int32) // factor
        if index == 0:
            return checker(np.zeros((len(yy), len(xx), 4), dtype=np.uint8))
        image = checker(
            palette[pixels_from_rows(ts.tiles[index].pixels, ts.tile_w, ts.tile_h)], background, p
        )
        return image[yy[:, None], xx]

    return _contact_sheet(
        ts.tile_w, ts.tile_h, list(range(len(ts.tiles))), thumbnail, layout="grid", scale=scale
    )


def _contact_sheet(tile_w, tile_h, fs, thumbnail, *, layout, scale, pad=0):
    columns = len(fs) if layout == "strip" else isqrt(len(fs) - 1) + 1
    rows = (len(fs) + columns - 1) // columns
    label_width = 4 * len(str(max(fs))) - 1

    def dimensions(factor, step=1):
        w = max(label_width, (tile_w * factor + pad + step - 1) // step)
        h = (tile_h * factor + pad + step - 1) // step + 7
        return w, h, columns * (w + 2) - 2, rows * (h + 2) - 2

    if scale == "auto":
        scale = 1
        for candidate in range(1, 17):
            if max(dimensions(candidate)[2:]) <= 1024:
                scale = candidate
    available_w = max(1, (1024 + 2) // columns - 2)
    available_h = max(1, (1024 + 2) // rows - 9)
    step = max(
        1,
        (tile_w * scale + pad + available_w - 1) // available_w,
        (tile_h * scale + pad + available_h - 1) // available_h,
    )
    w, h, width, height = dimensions(scale, step)
    output_bytes(width, height)
    output = np.full((height, width, 4), (240, 240, 240, 255), dtype=np.uint8)
    for index, frame in enumerate(fs):
        image = thumbnail(frame, scale, step)
        x, y = index % columns * (w + 2), index // columns * (h + 2)
        _label(output, x, y, frame)
        output[y + 7 : y + 7 + image.shape[0], x : x + image.shape[1]] = image
    if max(output.shape[:2]) > 1024:
        step = (max(output.shape[:2]) + 1023) // 1024
        output = output[::step, ::step].copy()
    return output, scale
