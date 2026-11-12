"""Bounded diagnostic sheets preserving actual pixels and integer zoom factors."""

from math import isqrt

import numpy as np

from .color import rgb_to_oklab_fixed_numpy
from .errors import CyberSpriteError, invalid
from .previews import _label, checker, preview_rect
from .render import render


def playback_frames(p, selected):
    """Mirror finite tag legs; show one complete cycle for infinite tags."""
    wanted, covered, strips = set(selected), set(), []
    for tag in p.tags:
        if not any(tag.from_ <= f <= tag.to for f in wanted):
            continue
        base = list(range(tag.from_, tag.to + 1))
        if tag.direction in ("reverse", "pingpong_reverse"):
            base.reverse()
        if len(base) == 1:
            order, count = base, 1
        elif tag.direction in ("pingpong", "pingpong_reverse"):
            if tag.repeat:
                count = len(base) + (tag.repeat - 1) * max(0, len(base) - 1)
            else:
                count = max(1, 2 * len(base) - 2)
            cycle = base + base[-2:0:-1]
            if count > 4096:
                _limit("Tag playback exceeds 4096 frames; reduce repeat.", requested=count)
            order = [cycle[i % len(cycle)] for i in range(count)]
        else:
            count = len(base) * (tag.repeat or 1)
            if count > 4096:
                _limit("Tag playback exceeds 4096 frames; reduce repeat.", requested=count)
            order = base * (tag.repeat or 1)
        if count > 4096:
            _limit("Tag playback exceeds 4096 frames; reduce repeat.", requested=count)
        order = [f for f in order if f in wanted]
        if order:
            strips.append((tag.id, order))
            covered.update(order)
    remaining = [f for f in selected if f not in covered]
    if remaining:
        strips.append((None, remaining))
    if sum(len(order) for _, order in strips) > 4096:
        _limit("Review playback exceeds 4096 frames; select a smaller range.")
    return strips


def _limit(message, **details):
    raise CyberSpriteError(
        "E_LIMIT_EXCEEDED", message, "Reduce frames, review scale, screen or rect.", details
    )


def luminance(image):
    result = image.copy()
    lightness = rgb_to_oklab_fixed_numpy(image[:, :, :3])[..., 0]
    gray = np.clip((lightness * 255 + 32768) // 65536, 0, 255).astype(np.uint8)
    result[:, :, :3] = gray[:, :, None]
    return result


def review_sheet(p, fs, *, design=None, guide=None, scale="auto", rect=None, layers=None, **_):
    """Return a single neutral sheet and machine-readable panel coordinates."""
    if not fs:
        raise invalid("Review layout requires at least one frame.")
    x0, y0, w, h = preview_rect(p, rect)
    platform = p.platform
    backgrounds = (platform.defaults.preview.backgrounds if platform else []) or ["checker"]
    factor = scale
    if scale == "auto":
        factor = (platform.defaults.export.review_scale if platform else None) or 4
    if guide and guide.get("scale") not in (None, factor):
        raise invalid("Review guide scale must equal the review zoom scale; omit guide.scale.")
    screen = platform.system.screen if platform else None
    sw, sh = max(w, screen.w if screen else w), max(h, screen.h if screen else h)
    # Plans contain sizes and recipes, never full intermediate zoomed images.
    plans = []
    for background in backgrounds:
        plans.append(dict(kind="actual", w=sw + 2, h=sh + 2, scale=1, background=background))
    for kind in ("zoom", "silhouette", "luminance"):
        plans.append(dict(kind=kind, w=w * factor, h=h * factor, scale=factor))
    if design is not None:
        plans.append(
            dict(
                kind="design", w=design.shape[1] * factor, h=design.shape[0] * factor, scale=factor
            )
        )
        # Place the design immediately after the enlarged project panel.
        plans.insert(len(backgrounds) + 1, plans.pop())
    strips = playback_frames(p, fs) if len(p.frames) > 1 else []
    for tag, order in strips:
        plans.append(
            dict(
                kind="playback", w=len(order) * (w + 2) - 2, h=h + 7, scale=1, tag=tag, frames=order
            )
        )
    # Square-ish neutral rows; playback strips occupy their own rows.
    columns = isqrt(len(plans) - len(strips) - 1) + 1
    row: list[dict] = []
    rows: list[list[dict]] = []
    width = 0
    for plan in plans:
        if (
            plan["kind"] == "playback"
            or len(row) == columns
            or plan["kind"] == "zoom"
            and design is not None
            and len(row) >= columns - 1
        ):
            if row:
                rows.append(row)
                row = []
        row.append(plan)
        if plan["kind"] == "playback":
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    height = 2
    for row in rows:
        xx = 2
        for plan in row:
            plan.update(x=xx, y=height + 7)
            xx += plan["w"] + 2
        width = max(width, xx)
        height += max(plan["h"] for plan in row) + 11
    if max(width, height) > 8192 or width * height > 16777216:
        _limit("Review sheet exceeds its pixel budget.", width=width, height=height)
    output = np.full((height, width, 4), (240, 240, 240, 255), dtype=np.uint8)
    data = render(p, fs[0], {"layers": layers})[y0 : y0 + h, x0 : x0 + w]
    panels = []
    for number, plan in enumerate(plans, 1):
        x, y = plan["x"], plan["y"]
        _label(output, x, y - 7, number)
        kind = plan["kind"]
        if kind == "actual":
            image = np.zeros((sh, sw, 4), dtype=np.uint8)
            dx, dy = (sw - w) // 2, (sh - h) // 2
            image[dy : dy + h, dx : dx + w] = data
            output[y : y + sh + 2, x : x + sw + 2] = (96, 96, 96, 255)
            output[y + 1 : y + sh + 1, x + 1 : x + sw + 1] = checker(image, plan["background"], p)
        elif kind == "playback":
            for column, frame in enumerate(plan["frames"]):
                start = x + column * (w + 2)
                _label(output, start, y, frame)
                image = render(p, frame, {"layers": layers})[y0 : y0 + h, x0 : x0 + w]
                output[y + 7 : y + 7 + h, start : start + w] = checker(image)
        else:
            image = design if kind == "design" else data
            if kind == "silhouette":
                image = data.copy()
                image[:, :, :3] = 32
                image[:, :, 3] = np.where(data[:, :, 3] != 0, 255, 0)
            elif kind == "luminance":
                image = luminance(data)
            image = checker(image)
            output[y : y + plan["h"], x : x + plan["w"]] = np.repeat(
                np.repeat(image, factor, axis=0), factor, axis=1
            )
        panels.append({"number": number, **plan})
    return output, factor, panels
