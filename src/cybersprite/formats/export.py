"""Format exporters. All pixels originate in the authoritative core renderer."""

import json
from pathlib import Path

import numpy as np

from cybersprite.core.canonical import json_bytes
from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.limits import OUTPUT_BYTES, check_limit, output_bytes
from cybersprite.core.models import Frame, ImageCel, ImageLayer
from cybersprite.core.pixels import rgba
from cybersprite.core.projects import new_project
from cybersprite.core.references import resolve_layer, resolve_tag
from cybersprite.core.render import _options, indexed_result, output_dimensions, render_result

from .animation import decode_apng, decode_gif, encode_apng, encode_gif, gif_durations
from .common import (
    animation_sequence,
    bounds,
    fail,
    format_name,
    frame_sequence,
    gate,
    name_values,
    preflight,
    rgba_pixels,
    sequence_pixel_sha256,
    slice_bounds,
    write_verified,
)
from .export_args import SheetArgs
from .png import decode_png, encode_png
from .sheet import Item, build_sheet, enumerate_items, shared_palette, sheet_data


def _png_file(path, pixels, palette, compression):
    palette = [c.lower() for c in palette] if palette is not None else None
    expected = rgba_pixels(pixels, palette)

    def verify(data):
        decoded = decode_png(data)
        return (
            np.array_equal(decoded.pixels, pixels)
            and decoded.palette == palette
            and np.array_equal(decoded.rgba(), expected)
        )

    return write_verified(
        path, encode_png(pixels, palette, compression=compression), verify, pixels=pixels
    )


def export_image(p, a, root=None):
    result = gate(p, a, root)
    sequence = frame_sequence(p, a.frames)
    selected_layer = resolve_layer(p, a.layers[0]) if a.layers and len(a.layers) == 1 else None
    selected_tag = (
        resolve_tag(p, a.frames.removeprefix("tag:"))
        if isinstance(a.frames, str) and a.frames != "all" and not a.frames[:1].isdigit()
        else None
    )
    if a.crop is not None and a.slice is not None:
        raise invalid("Specify either crop or slice, not both.")
    names = [
        format_name(
            a.out,
            **name_values(
                p,
                frame,
                layer=selected_layer,
                tag=selected_tag,
                slice=slice_bounds(p, a.slice, frame)[0] if a.slice else None,
            ),
        )
        for frame in sequence
    ]
    paths = preflight(names, a.overwrite)
    # Resolve and render every item before writing so option errors cannot leave partial output.
    images = []
    held_bytes = 0
    for frame in sequence:
        crop = (
            slice_bounds(p, a.slice, frame)[1]
            if a.slice
            else a.crop.model_dump()
            if a.crop
            else None
        )
        size = output_bytes(
            *output_dimensions(
                p,
                _options(
                    p, frame, dict(crop=crop, scale=a.scale, apply_pixel_ratio=a.apply_pixel_ratio)
                ),
            )
        )
        held_bytes += size
        check_limit(
            "output_bytes",
            held_bytes,
            OUTPUT_BYTES,
            "Export fewer frames or reduce scale/crop dimensions.",
        )
        rendered = (indexed_result if a.color_mode == "indexed" else render_result)(
            p,
            frame,
            dict(
                layers=a.layers,
                crop=crop,
                scale=a.scale,
                background=a.background,
                apply_pixel_ratio=a.apply_pixel_ratio,
                flatten=a.flatten,
            ),
        )
        pixels = rendered.pixels
        if a.trim:
            x, y, w, h, _ = bounds(pixels, rendered.palette)
            pixels = pixels[y : y + h, x : x + w].copy()
        images.append((pixels, rendered.palette))
        result["warnings"].extend(rendered.warnings)
    for path, (pixels, palette) in zip(paths, images, strict=True):
        result["files"].append(_png_file(path, pixels, palette, a.compression))
    return result


def export_sheet(p, a, root=None):
    result = gate(p, a, root)
    items, warnings = enumerate_items(p, a)
    result["warnings"].extend(warnings)
    pixels, palette = build_sheet(p, a, items)
    paths = preflight([a.out, *([a.data_out] if a.data_out else [])], a.overwrite)
    h, w = pixels.shape[:2]
    data = sheet_data(p, a, items, w, h, Path(a.out).name) if a.data_out else None
    result["files"].append(_png_file(paths[0], pixels, palette, a.compression))
    if data is not None:
        result["files"].append(
            write_verified(paths[1], json_bytes(data), lambda raw: json.loads(raw) == data)
        )
    result.update(sheet=dict(width=w, height=h), items=len(items))
    return result


def _canonical_transparency(pixels):
    result = pixels.copy()
    result[result[..., 3] == 0, :3] = 0
    return result


def export_animation(p, a, root=None):
    result = gate(p, a, root)
    format = a.format or Path(a.out).suffix.lower().removeprefix(".")
    if format == "png":
        format = "apng"
    if format not in ("gif", "apng"):
        raise invalid("Animation format must be gif or apng (or use an explicit format).")
    if format == "gif" and a.color_mode == "rgba":
        raise invalid("GIF requires indexed color_mode; use APNG for RGBA.")
    sequence = animation_sequence(p, a.frames, a.tag, a.loop, scale=a.scale)
    output_bytes(p.canvas.width * a.scale, p.canvas.height * a.scale, len(sequence))
    options = dict(layers=a.layers, scale=a.scale, flatten=a.flatten, background=a.background)
    indexed = format == "gif" or a.color_mode != "rgba"
    rendered = []
    if indexed:
        try:
            rendered = [indexed_result(p, frame, options) for frame in sequence]
            # A single animation palette must represent every frame consistently.
            palette = shared_palette(rendered, p.palette.colors)
        except CyberSpriteError as error:
            if error.code != "E_NOT_PALETTE_CLOSED" or format == "gif" or a.color_mode == "indexed":
                raise
            indexed = False
    if not indexed:
        rendered = [render_result(p, frame, options) for frame in sequence]
        palette = None
    images = [r.pixels for r in rendered]
    durations = [p.frames[f].duration_ms for f in sequence]
    for r in rendered:
        result["warnings"].extend(r.warnings)
    expected = [_canonical_transparency(rgba_pixels(im, palette)) for im in images]
    path = preflight([a.out], a.overwrite)[0]
    if format == "gif":
        transparent = [bool(np.any(im[..., 3] == 0)) for im in expected]
        # GIF only has a binary transparency flag; every used non-transparent entry is opaque.
        if any(np.any((im[..., 3] != 0) & (im[..., 3] != 255)) for im in expected):
            fail(
                "E_NOT_PALETTE_CLOSED",
                "GIF cannot represent partially transparent palette entries.",
            )
        raw = encode_gif(
            images,
            p.palette.colors,
            p.palette.transparent_index,
            durations,
            loop=a.loop,
            transparent=transparent,
        )
        rounded = gif_durations(durations)
        changed = [
            dict(frame=f, duration_ms=d, exported_ms=r)
            for f, d, r in zip(sequence, durations, rounded, strict=True)
            if d != r
        ]
        if changed:
            result["warnings"].append(
                dict(
                    code="W_GIF_DURATION_ROUNDED",
                    frames=changed,
                    message="GIF durations were rounded to 10 ms with a 20 ms minimum.",
                )
            )

        def verify(data):
            actual, times, plays = decode_gif(data)
            return (
                len(actual) == len(expected)
                and times == rounded
                and plays == a.loop
                and all(
                    np.array_equal(_canonical_transparency(x), y)
                    for x, y in zip(actual, expected, strict=True)
                )
            )
    else:
        raw = encode_apng(images, durations, palette, loop=a.loop, compression=a.compression)

        def verify(data):
            actual, times, plays = decode_apng(data)
            return (
                len(actual) == len(expected)
                and times == durations
                and plays == a.loop
                and all(
                    np.array_equal(x.pixels, im)
                    and np.array_equal(_canonical_transparency(x.rgba()), y)
                    for x, im, y in zip(actual, images, expected, strict=True)
                )
            )

    result["files"].append(write_verified(path, raw, verify, pixels=images[0]))
    result["files"][-1]["pixel_sha256"] = sequence_pixel_sha256(images)
    return result


def export_palette(p, a, root=None):
    from .palette_files import decode_palette, encode_palette

    result = gate(p, a, root)
    format = a.format or Path(a.out).suffix.lower().removeprefix(".")
    colors, names = p.palette.colors, p.palette.names
    raw = encode_palette(colors, names, format, p.name)
    expected = colors if format == "png" else [c[:7] + "ff" for c in colors]
    if format in ("gpl", "pal", "hex"):
        index = p.palette.transparent_index
        result["warnings"].append(
            {
                "code": "W_PALETTE_TRANSPARENT_ENTRY",
                "index": index,
                "message": f"Palette format {format} cannot express transparency at index {index}; "
                "the entry's stored RGB was written.",
            }
        )

    def verify(data):
        if format == "png":
            return np.array_equal(decode_png(data).rgba(), pixels)
        actual_colors, actual_names = decode_palette(data, format)
        return actual_colors == expected and (format != "gpl" or actual_names == names)

    path = preflight([a.out], a.overwrite)[0]
    pixels = np.array([[rgba(c) for c in expected]], dtype=np.uint8)
    result["files"].append(
        write_verified(path, raw, verify, pixels=pixels if format == "png" else None)
    )
    return result


def export_tileset(p, a, root=None):
    result = gate(p, a, root)
    matches = [t for t in p.tilesets if t.id == a.tileset]
    if not matches:
        matches = [t for t in p.tilesets if t.name == a.tileset]
    if not matches:
        fail("E_TILESET_NOT_FOUND", "Export tileset was not found.", reference=a.tileset)
    if len(matches) != 1:
        fail("E_AMBIGUOUS_REF", "Tileset name is ambiguous; use its ID.", reference=a.tileset)
    ts = matches[0]
    indices = list(range(0 if a.include_empty else 1, len(ts.tiles)))
    output_bytes(ts.tile_w * a.scale, ts.tile_h * a.scale, len(indices))
    # Tiles are exposed to exactly the same renderer through a transient indexed project.
    q = new_project(
        width=ts.tile_w,
        height=ts.tile_h,
        frames=1,
        palette=p.palette.colors,
        name=p.name,
    )
    q.palette.transparent_index = p.palette.transparent_index
    q.frames = [Frame()]
    tile_layer = ImageLayer(id="L1", name=ts.name, cels=[])
    q.layers = [tile_layer]
    sheet_args = SheetArgs.model_validate(
        {
            k: getattr(a, k)
            for k in (
                "out",
                "layout",
                "columns",
                "rows",
                "width",
                "height",
                "spacing",
                "border",
                "inner",
                "scale",
                "power_of_two",
                "compression",
                "allow_invalid",
                "overwrite",
            )
        }
    )
    items = []
    for frame, index in enumerate(indices):
        tile_layer.cels = [
            ImageCel(frame=0, x=0, y=0, w=ts.tile_w, h=ts.tile_h, pixels=ts.tiles[index].pixels)
        ]
        rendered = indexed_result(q, 0, dict(scale=a.scale))
        h, w = rendered.pixels.shape[:2]
        items.append(
            Item(
                str(index),
                frame,
                None,
                None,
                None,
                rendered.pixels,
                rendered.palette,
                dict(x=0, y=0, w=w, h=h),
                dict(w=w, h=h),
                False,
                100,
            )
        )
    pixels, palette = build_sheet(q, sheet_args, items)
    paths = preflight([a.out, *([a.data_out] if a.data_out else [])], a.overwrite)
    result["files"].append(_png_file(paths[0], pixels, palette, a.compression))
    if a.data_out:
        data = dict(
            format="cybersprite-tileset",
            schema_version=1,
            image=Path(a.out).name,
            tileset=ts.id,
            name=ts.name,
            tile_w=ts.tile_w,
            tile_h=ts.tile_h,
            base_index=ts.base_index,
            size=dict(w=pixels.shape[1], h=pixels.shape[0]),
            tiles=[
                dict(
                    index=index,
                    display_index=index + ts.base_index,
                    rect=item.rect,
                    user_data=ts.tiles[index].user_data.model_dump()
                    if ts.tiles[index].user_data
                    else None,
                )
                for index, item in zip(indices, items, strict=True)
            ],
        )
        result["files"].append(
            write_verified(
                paths[1],
                json_bytes(data),
                lambda raw: json.loads(raw) == data,
            )
        )
    return result


def export_aseprite(p, a, root=None):
    from .aseprite_io import decode_aseprite, encode_aseprite, equivalent

    result = gate(p, a, root)
    path = preflight([a.out], a.overwrite)[0]
    raw = encode_aseprite(p)

    def verify(data):
        other, _ = decode_aseprite(data, name=p.name)
        # Common export verification is mandatory even when semantic comparison is disabled.
        return (not a.verify or equivalent(p, other)) and all(
            np.array_equal(render_result(p, f).pixels, render_result(other, f).pixels)
            for f in range(len(p.frames))
        )

    result["files"].append(write_verified(path, raw, verify, pixels=render_result(p, 0).pixels))
    result["files"][-1]["pixel_sha256"] = sequence_pixel_sha256(
        [render_result(p, frame).pixels for frame in range(len(p.frames))]
    )
    return result


EXPORTERS = {
    name: value
    for name, value in list(globals().items())
    if name.startswith("export_") and callable(value)
}
