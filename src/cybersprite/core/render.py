"""Integer normal blending, stable cel ordering, and indexed palette closure."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .errors import CyberSpriteError, invalid
from .limits import output_bytes
from .models import GroupLayer, ImageLayer, LinkCel, Project
from .pixels import pixels_from_rows, rgb_distance, rgba, tiles_from_rows
from .references import cel_at, cel_owner, resolve_layer, walk_layers


@dataclass
class RenderOptions:
    layers: list[str] | None = None
    include_hidden: bool = False
    background: int | str | None = None
    crop: dict[str, int] | None = None
    scale: int = 1
    apply_pixel_ratio: bool = False
    flatten: str = "strict"


@dataclass
class Draw:
    layer: object
    cel: object
    data: object
    effective_opacity: int
    order: int
    z_index: int


@dataclass
class RenderResult:
    pixels: np.ndarray
    warnings: list[dict] = field(default_factory=list)
    palette: list[str] | None = None


def mul255(a, b):
    return (a * b + 127) // 255


def source_over(source: np.ndarray, destination: np.ndarray) -> np.ndarray:
    """Straight RGBA source-over; int64 prevents cross-platform overflow."""
    s, d = source.astype(np.int64), destination.astype(np.int64)
    sa, da = s[..., 3:4], d[..., 3:4]
    ra = sa + mul255(da, 255 - sa)
    denominator = np.maximum(ra * 255, 1)
    color = (s[..., :3] * sa * 255 + d[..., :3] * da * (255 - sa) + (ra * 255) // 2) // denominator
    color = np.where(ra == 0, 0, color)
    return np.concatenate((np.minimum(color, 255), ra), axis=-1).astype(np.uint8)


def _options(project, frame, options):
    if type(frame) is not int or not 0 <= frame < len(project.frames):
        raise CyberSpriteError(
            "E_FRAME_OUT_OF_RANGE",
            f"Frame {frame} is outside the project.",
            "Use a zero-based frame number smaller than frame_count.",
            {"frame": frame, "frame_count": len(project.frames)},
        )
    opts = options or RenderOptions()
    if isinstance(opts, dict):
        try:
            opts = RenderOptions(**opts)
        except TypeError as error:
            raise invalid(str(error)) from error
    if type(opts.scale) is not int or not 1 <= opts.scale <= 64:
        raise CyberSpriteError(
            "E_LIMIT_EXCEEDED",
            "Render scale must be an integer from 1 to 64.",
            "Use --scale 1..64.",
            {"limit": 64, "requested": opts.scale},
        )
    if opts.flatten not in ("strict", "nearest"):
        raise invalid("flatten must be strict or nearest.")
    if opts.crop is not None:
        r = opts.crop
        if (
            set(r) != {"x", "y", "w", "h"}
            or any(type(v) is not int for v in r.values())
            or r["w"] < 1
            or r["h"] < 1
            or r["x"] < 0
            or r["y"] < 0
            or r["x"] + r["w"] > project.canvas.width
            or r["y"] + r["h"] > project.canvas.height
        ):
            raise invalid("crop must be a positive integer rectangle contained within the canvas.")
    output_dimensions(project, opts)
    return opts


def output_dimensions(project, options):
    """Check the final crop, scale and pixel ratio before rendering or repeating."""
    w = options.crop["w"] if options.crop else project.canvas.width
    h = options.crop["h"] if options.crop else project.canvas.height
    w *= options.scale * (project.canvas.pixel_ratio.w if options.apply_pixel_ratio else 1)
    h *= options.scale * (project.canvas.pixel_ratio.h if options.apply_pixel_ratio else 1)
    output_bytes(w, h)
    return w, h


def _draws(project, frame, options):
    selected = (
        None
        if options.layers is None
        else {resolve_layer(project, ref).id for ref in options.layers}
    )
    draws = []
    warnings = []
    fallback = []
    for order, (layer, ancestors) in enumerate(walk_layers(project.layers)):
        if isinstance(layer, GroupLayer):
            continue
        if not options.include_hidden and not all(node.visible for node in (*ancestors, layer)):
            continue
        if selected is not None and not any(node.id in selected for node in (*ancestors, layer)):
            continue
        cel = cel_at(layer, frame)
        if cel is None:
            continue
        owner = cel_owner(layer, cel)
        if owner is None or isinstance(owner, LinkCel):
            raise CyberSpriteError(
                "E_INVALID_PROJECT",
                "Cel has no direct data owner.",
                "Validate and normalize links before rendering.",
                {"layer": layer.id, "frame": frame},
            )
        opacity = owner.opacity
        for node in (layer, *reversed(ancestors)):
            opacity = mul255(opacity, node.opacity)
        draws.append(Draw(layer, cel, owner, opacity, order, cel.z_index))
        if layer.blend_mode != "normal":
            fallback.append(layer.id)
    if fallback:
        warnings.append(
            {
                "code": "W_BLEND_FALLBACK",
                "layers": fallback,
                "message": "Unsupported blend modes were rendered as normal.",
            }
        )
    return sorted(draws, key=lambda draw: (draw.order + draw.z_index, draw.z_index)), warnings


def _parts(project, draw):
    cel, layer = draw.data, draw.layer
    if isinstance(layer, ImageLayer):
        yield cel.x, cel.y, pixels_from_rows(cel.pixels, cel.w, cel.h)
    else:
        ts = next(ts for ts in project.tilesets if ts.id == layer.tileset)
        rows = tiles_from_rows(cel.tiles, cel.w, cel.h)
        for row, refs in enumerate(rows):
            for col, ref in enumerate(refs):
                if ref.index == 0:
                    continue
                pixels = pixels_from_rows(ts.tiles[ref.index].pixels, ts.tile_w, ts.tile_h)
                if ref.d and ts.tile_w == ts.tile_h:
                    pixels = pixels.T
                if ref.x:
                    pixels = pixels[:, ::-1]
                if ref.y:
                    pixels = pixels[::-1]
                yield cel.x + col * ts.tile_w, cel.y + row * ts.tile_h, pixels


def frame_signature(project, frame):
    """Exact immutable compositing inputs for local, bounded reuse only."""
    draws, _ = _draws(project, frame, RenderOptions())
    parts = []
    for draw in draws:
        cel, layer = draw.data, draw.layer
        data = tuple(cel.pixels) if isinstance(layer, ImageLayer) else tuple(cel.tiles)
        tileset = (
            None
            if isinstance(layer, ImageLayer)
            else next(ts.model_dump_json() for ts in project.tilesets if ts.id == layer.tileset)
        )
        parts.append(
            (
                layer.id,
                layer.type,
                layer.blend_mode,
                getattr(layer, "background", False),
                draw.effective_opacity,
                draw.order,
                draw.z_index,
                cel.x,
                cel.y,
                cel.w,
                cel.h,
                data,
                tileset,
            )
        )
    return (
        project.canvas.width,
        project.canvas.height,
        tuple(project.palette.colors),
        project.palette.transparent_index,
        tuple(parts),
    )


def _clip(x, y, pixels, width, height):
    h, w = pixels.shape
    left, top, right, bottom = max(0, x), max(0, y), min(width, x + w), min(height, y + h)
    if left >= right or top >= bottom:
        return None
    return (slice(top, bottom), slice(left, right)), pixels[
        top - y : bottom - y, left - x : right - x
    ]


def _background(project, options):
    value = options.background
    if value is None:
        return None
    if type(value) is int:
        if not 0 <= value < len(project.palette.colors):
            raise CyberSpriteError(
                "E_INDEX_OUT_OF_RANGE",
                "Background index is outside the palette.",
                "Use an existing palette index.",
                {"palette_size": len(project.palette.colors)},
            )
        return (*rgba(project.palette.colors[value])[:3], 255)
    color = rgba(value)
    if len(value) != 7:
        raise invalid("Render background hex colors must use #rrggbb.")
    return color


def _finish(project, pixels, options):
    output_dimensions(project, options)
    if options.crop:
        r = options.crop
        pixels = pixels[r["y"] : r["y"] + r["h"], r["x"] : r["x"] + r["w"]]
    sx = options.scale * (project.canvas.pixel_ratio.w if options.apply_pixel_ratio else 1)
    sy = options.scale * (project.canvas.pixel_ratio.h if options.apply_pixel_ratio else 1)
    if sx != 1:
        pixels = np.repeat(pixels, sx, axis=1)
    if sy != 1:
        pixels = np.repeat(pixels, sy, axis=0)
    return pixels.copy()


def render_result(
    project: Project, frame: int = 0, options: RenderOptions | dict | None = None
) -> RenderResult:
    opts = _options(project, frame, options)
    width, height = project.canvas.width, project.canvas.height
    pixels = np.zeros((height, width, 4), dtype=np.uint8)
    bg = _background(project, opts)
    if bg is not None:
        pixels[:] = bg
    palette = np.array([rgba(color) for color in project.palette.colors], dtype=np.uint8)
    draws, warnings = _draws(project, frame, opts)
    for draw in draws:
        background = isinstance(draw.layer, ImageLayer) and draw.layer.background
        for x, y, part in _parts(project, draw):
            clipped = _clip(x, y, part, width, height)
            if clipped is None:
                continue
            region, indices = clipped
            src = palette[indices].copy()
            if background:
                src[..., 3] = 255
            else:
                src[indices == project.palette.transparent_index, 3] = 0
            src[..., 3] = mul255(src[..., 3].astype(np.int64), draw.effective_opacity).astype(
                np.uint8
            )
            pixels[region] = source_over(src, pixels[region])
    return RenderResult(_finish(project, pixels, opts), warnings)


def render(
    project: Project,
    frame: int = 0,
    options: RenderOptions | dict | None = None,
    *,
    warnings: list | None = None,
) -> np.ndarray:
    result = render_result(project, frame, options)
    if warnings is not None:
        warnings.extend(result.warnings)
    return result.pixels


def indexed_result(
    project: Project, frame: int = 0, options: RenderOptions | dict | None = None
) -> RenderResult:
    opts = _options(project, frame, options)
    if opts.flatten == "nearest":
        rgba_result = render_result(project, frame, opts)
        opaque = [
            (i, rgba(c))
            for i, c in enumerate(project.palette.colors)
            if rgba(c)[3] == 255 and i != project.palette.transparent_index
        ]
        output = np.full(
            rgba_result.pixels.shape[:2], project.palette.transparent_index, dtype=np.uint8
        )
        cache = {}
        for y, row in enumerate(rgba_result.pixels):
            for x, color in enumerate(row):
                if color[3] >= 128:
                    if not opaque:
                        raise CyberSpriteError(
                            "E_NOT_PALETTE_CLOSED",
                            "Palette has no opaque color.",
                            "Add an alpha-255 palette entry before flattening.",
                        )
                    key = tuple(int(c) for c in color[:3])
                    if key not in cache:
                        cache[key] = min(
                            opaque, key=lambda item: (rgb_distance(key, item[1]), item[0])
                        )[0]
                    output[y, x] = cache[key]
        palette = list(project.palette.colors)
        palette[project.palette.transparent_index] = "#00000000"
        return RenderResult(output, rgba_result.warnings, palette)
    draws, warnings = _draws(project, frame, opts)
    ti = project.palette.transparent_index
    width, height = project.canvas.width, project.canvas.height
    result = np.full((height, width), ti, dtype=np.uint8)
    palette = list(project.palette.colors)
    palette[ti] = "#00000000"
    causes = []
    bg = _background(project, opts)
    if bg is not None:
        matches = [i for i, c in enumerate(palette) if rgba(c) == bg]
        if not matches:
            causes.append(
                {
                    "background": opts.background,
                    "reason": "Background is not an opaque palette color.",
                }
            )
        else:
            result[:] = min(matches)
    for draw in draws:
        background = isinstance(draw.layer, ImageLayer) and draw.layer.background
        used: set[int] = set()
        parts = list(_parts(project, draw))
        for _x, _y, part in parts:
            used.update(int(v) for v in np.unique(part))
        bad_colors = [
            i for i in sorted(used) if i != ti and rgba(project.palette.colors[i])[3] != 255
        ]
        if (
            draw.effective_opacity != 255
            or draw.layer.blend_mode != "normal"
            or (bad_colors and not background)
        ):
            causes.append(
                {
                    "layer": draw.layer.id,
                    "frame": frame,
                    "colors": bad_colors,
                    "effective_opacity": draw.effective_opacity,
                    "blend_mode": draw.layer.blend_mode,
                }
            )
        if background:
            # This palette is an export view, never a change to the authoritative palette.
            for i in sorted(used):
                palette[i] = (
                    palette[i][:7] + "ff" if i != ti else project.palette.colors[i][:7] + "ff"
                )
        for x, y, part in parts:
            clipped = _clip(x, y, part, width, height)
            if clipped is not None:
                region, indices = clipped
                if background:
                    result[region] = indices
                else:
                    np.copyto(result[region], indices, where=indices != ti)
    if causes:
        raise CyberSpriteError(
            "E_NOT_PALETTE_CLOSED",
            "Frame is not palette closed.",
            "Use RGBA rendering or explicitly request flatten='nearest'.",
            {"causes": causes},
        )
    return RenderResult(_finish(project, result, opts), warnings, palette)


def render_indexed(
    project: Project,
    frame: int = 0,
    options: RenderOptions | dict | None = None,
    *,
    warnings: list | None = None,
) -> np.ndarray:
    result = indexed_result(project, frame, options)
    if warnings is not None:
        warnings.extend(result.warnings)
    return result.pixels
