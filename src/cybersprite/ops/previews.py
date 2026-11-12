"""PNG transport for preview arrays and revision comparisons."""

import base64
from pathlib import Path
from typing import Any

import numpy as np

from cybersprite.core import history
from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.previews import checker, composite_preview, preview_array, tileset_preview
from cybersprite.core.quality import bbox
from cybersprite.core.render import render, render_indexed
from cybersprite.formats.png import encode_png

from .common import frame_index


def previews(
    p, fs, root, *, dry=False, inline=False, retain=True, layout="frames", tileset=None, **options
):
    if tileset is not None:
        from .tiles import resolve_tileset

        ts = resolve_tileset(p, tileset)
        data, scale = tileset_preview(
            p,
            ts,
            scale=options.get("scale", "auto"),
            background=options.get("background", "checker"),
        )
        folder = Path(root) / ".cybersprite/previews"
        if dry:
            folder /= "dry"
        path = folder / f"r{p.revision:06d}_tileset_{ts.id}.png"
        raw = encode_png(data)
        history.atomic_write(path, raw)
        if not dry and retain:
            history.retain_previews(root)
        result = {
            "paths": [path.relative_to(root).as_posix()],
            "scale": scale,
            "width": data.shape[1],
            "height": data.shape[0],
        }
        if inline:
            result["images"] = [base64.b64encode(raw).decode("ascii")]
        return result
    if not fs and layout != "frames":
        raise invalid("Preview requires at least one frame.")
    limit = 8 if layout == "frames" else 4096
    if len(fs) > limit:
        message = (
            "Preview accepts at most 8 frames per call; use layout=strip or a smaller range."
            if layout == "frames"
            else "Preview accepts at most 4096 frames per call."
        )
        raise CyberSpriteError(
            "E_LIMIT_EXCEEDED",
            message,
            "Reduce frames or change layout.",
            {"limit": limit, "requested": len(fs)},
        )
    for frame in fs:
        frame_index(p, frame)
    folder = Path(root) / ".cybersprite/previews"
    if dry:
        folder /= "dry"
    paths, images = [], []
    scale = 1
    width = height = 0
    for frame in fs if layout == "frames" else [None]:
        if frame is None:
            data, scale = composite_preview(p, fs, layout=layout, **options)
        else:
            data, scale = preview_array(p, frame, inline=inline, **options)
        data_bytes = encode_png(data)
        suffix = f"f{frame}" if frame is not None else layout
        path = folder / f"r{p.revision:06d}_{suffix}.png"
        history.atomic_write(path, data_bytes)
        paths.append(path.relative_to(root).as_posix())
        if inline:
            images.append(base64.b64encode(data_bytes).decode("ascii"))
        height, width = data.shape[:2]
    if not dry and retain:
        history.retain_previews(root)
    result = {"paths": paths, "scale": scale, "width": width, "height": height}
    if images:
        result["images"] = images
    return result


def transaction_previews(p, changed, root, mode, dry):
    fs = [item["frame"] for item in changed["frames"] if item["frame"] < len(p.frames)]
    result = previews(p, fs[:4], root, dry=dry, inline=mode == "inline", retain=False)
    result["omitted_frames"] = fs[4:]
    sets = [ts for ts in changed["tilesets"] if any(t.id == ts for t in p.tilesets)]
    for ts in sets[:4]:
        tile_view = previews(
            p, [], root, tileset=ts, dry=dry, inline=mode == "inline", retain=False
        )
        result["paths"].extend(tile_view["paths"])
        if "images" in tile_view:
            result.setdefault("images", []).extend(tile_view["images"])
        if not fs:
            for key in ("scale", "width", "height"):
                result[key] = tile_view[key]
    if len(sets) > 4:
        result["omitted_tilesets"] = sets[4:]
    return result


def diff(p, root, from_revision, to_revision, fs=None, inline=True):
    from cybersprite.core.limits import output_bytes

    before = history.restore(root, from_revision)
    after = p if to_revision == p.revision else history.restore(root, to_revision)
    candidates = fs if fs is not None else list(range(max(len(before.frames), len(after.frames))))
    results: list[dict[str, Any]] = []
    paths, images, omitted = [], [], []
    for f in candidates:
        if not 0 <= f < max(len(before.frames), len(after.frames)):
            from .common import fail

            fail("E_FRAME_OUT_OF_RANGE", "Diff frame is outside both revisions.", frame=f)
        w, h = (
            max(before.canvas.width, after.canvas.width),
            max(before.canvas.height, after.canvas.height),
        )
        scale = max(1, min(16, 512 // max(w * 3, h)))
        output_bytes(w * 3 * scale, h * scale)
        old = np.zeros((h, w, 4), dtype=np.uint8)
        new = old.copy()
        for project, destination in ((before, old), (after, new)):
            if f < len(project.frames):
                data = render(project, f)
                destination[: data.shape[0], : data.shape[1]] = data
        mask = np.any(old != new, axis=2)
        count = int(np.count_nonzero(mask))
        if fs is None and not count:
            continue
        if len(results) >= 4:
            omitted.append(f)
            continue
        info = {"frame": f, "pixels_changed": count, "bbox": bbox(mask)}
        if (
            count <= 256
            and f < min(len(before.frames), len(after.frames))
            and (
                before.canvas.width == after.canvas.width
                and before.canvas.height == after.canvas.height
            )
        ):
            try:
                left, right = render_indexed(before, f), render_indexed(after, f)
                info["changes"] = [
                    [int(x), int(y), int(left[y, x]), int(right[y, x])]
                    for y, x in zip(*np.nonzero(mask), strict=True)
                ]
            except CyberSpriteError as error:
                if error.code != "E_NOT_PALETTE_CLOSED":
                    raise
        highlight = checker(new)
        highlight[:, :, :3] = ((highlight[:, :, :3].astype(np.int32) + 255) // 2).astype(np.uint8)
        highlight[mask] = (255, 0, 255, 255)
        output = np.concatenate([checker(old), checker(new), highlight], axis=1)
        scale = max(1, min(16, 512 // max(w * 3, h)))
        output = np.repeat(np.repeat(output, scale, 0), scale, 1)
        if inline and max(output.shape[:2]) > 1024:
            step = (max(output.shape[:2]) + 1023) // 1024
            output = output[::step, ::step].copy()
        png_data = encode_png(output)
        path = (
            Path(root)
            / f".cybersprite/previews/diff_r{from_revision:06d}_r{to_revision:06d}_f{f}.png"
        )
        history.atomic_write(path, png_data)
        paths.append(path.relative_to(root).as_posix())
        if inline:
            images.append(base64.b64encode(png_data).decode("ascii"))
        results.append(info)
    result = {"frames": results, "paths": paths, "omitted_frames": omitted}
    if images:
        result["images"] = images
    return result
