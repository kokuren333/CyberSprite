"""Bounded diagnostic sheets preserving actual pixels and integer zoom factors."""

from math import isqrt

import numpy as np

from .color import rgb_to_oklab_fixed_numpy
from .errors import CyberSpriteError, invalid
from .previews import DIGITS, checker, preview_rect
from .render import render

# Decoration only (never exported). Original 3x5 capitals; rows are 3-bit masks like DIGITS.
LETTERS = {
    "A": (2, 5, 7, 5, 5),
    "B": (6, 5, 6, 5, 6),
    "C": (3, 4, 4, 4, 3),
    "D": (6, 5, 5, 5, 6),
    "E": (7, 4, 6, 4, 7),
    "F": (7, 4, 6, 4, 4),
    "G": (3, 4, 5, 5, 3),
    "H": (5, 5, 7, 5, 5),
    "I": (7, 2, 2, 2, 7),
    "J": (1, 1, 1, 5, 2),
    "K": (5, 5, 6, 5, 5),
    "L": (4, 4, 4, 4, 7),
    "M": (5, 7, 7, 5, 5),
    "N": (6, 5, 5, 5, 5),
    "O": (2, 5, 5, 5, 2),
    "P": (6, 5, 6, 4, 4),
    "Q": (2, 5, 5, 6, 3),
    "R": (6, 5, 6, 5, 5),
    "S": (3, 4, 2, 1, 6),
    "T": (7, 2, 2, 2, 2),
    "U": (5, 5, 5, 5, 7),
    "V": (5, 5, 5, 5, 2),
    "W": (5, 5, 7, 7, 5),
    "X": (5, 5, 2, 5, 5),
    "Y": (5, 5, 2, 2, 2),
    "Z": (7, 1, 2, 4, 7),
    "-": (0, 0, 7, 0, 0),
    "_": (0, 0, 0, 0, 7),
    "/": (1, 1, 2, 4, 4),
    ".": (0, 0, 0, 0, 2),
    "#": (5, 7, 5, 7, 5),
    " ": (0, 0, 0, 0, 0),
    **{str(i): rows for i, rows in enumerate(DIGITS)},
}
INK, FRAME, PAPER = (32, 32, 32, 255), (96, 96, 96, 255), (240, 240, 240, 255)
MARGIN, GAP, LABEL = 6, 8, 9  # outer margin, space between panels, label band above a panel


def label_text(text):
    """Upper-case text restricted to the sheet font; other characters are dropped."""
    return "".join(c for c in str(text).upper() if c in LETTERS)


def _text(image, x, y, text, limit=None):
    """Draw 3x5 glyphs at a 4 px pitch, clipped to `limit` pixels of width."""
    h, w = image.shape[:2]
    right = w if limit is None else min(w, x + limit)
    for char in label_text(text):
        if x + 3 > right:
            break
        for j, row in enumerate(LETTERS[char]):
            for i in range(3):
                if row & (1 << (2 - i)) and 0 <= y + j < h and 0 <= x + i < w:
                    image[y + j, x + i] = INK
        x += 4


def _frame(image, x, y, w, h):
    """One-pixel neutral frame just outside a panel's image area."""
    image[y - 1, x - 1 : x + w + 1] = FRAME
    image[y + h, x - 1 : x + w + 1] = FRAME
    image[y : y + h, x - 1] = FRAME
    image[y : y + h, x + w] = FRAME


def _inset(kind):
    return 1 if kind in ("zoom", "design", "silhouette", "luminance") else 0


def caption(plan, tags):
    kind, scale = plan["kind"], plan["scale"]
    if kind == "actual":
        background = plan["background"]
        return "SCREEN 1X" + ("" if background == "checker" else f" {background}")
    if kind == "zoom":
        return f"ZOOM {scale}X"
    if kind == "design":
        return f"GUIDE {scale}X"
    if kind == "silhouette":
        return "SILHOUETTE"
    if kind == "luminance":
        return "LIGHTNESS"
    name = tags.get(plan["tag"], "") if plan.get("tag") else ""
    return "PLAY 1X" + (f" {label_text(name) or plan['tag']}" if plan.get("tag") else "")


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
    if screen and (w > screen.w or h > screen.h):
        raise invalid(
            "Review rect exceeds the actual-size screen frame; select a smaller rect.",
            screen={"w": screen.w, "h": screen.h},
            rect={"w": w, "h": h},
        )
    sw, sh = (screen.w, screen.h) if screen else (w, h)
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
                kind="playback",
                w=len(order) * (w + 2) - 2,
                h=h + 7,
                scale=1,
                tag=tag,
                frames=order,
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
    # Every panel gets a label band. Enlarged panels get a one-pixel frame outside their
    # image area; actual-size panels carry it inside and playback strips have none.
    height = MARGIN
    for row in rows:
        xx = MARGIN
        for plan in row:
            inset = _inset(plan["kind"])
            plan.update(x=xx + inset, y=height + LABEL + inset)
            xx += plan["w"] + 2 * inset + GAP
        width = max(width, xx - GAP + MARGIN)
        height += LABEL + max(plan["h"] + 2 * _inset(plan["kind"]) for plan in row) + GAP
    height += MARGIN - GAP
    if max(width, height) > 8192 or width * height > 16777216:
        _limit("Review sheet exceeds its pixel budget.", width=width, height=height)
    output = np.full((height, width, 4), PAPER, dtype=np.uint8)
    tags = {tag.id: tag.name for tag in p.tags}
    data = render(p, fs[0], {"layers": layers})[y0 : y0 + h, x0 : x0 + w]
    panels = []
    for number, plan in enumerate(plans, 1):
        x, y = plan["x"], plan["y"]
        inset = _inset(plan["kind"])
        _text(
            output, x - inset, y - inset - LABEL, f"{number} {caption(plan, tags)}", plan["w"] + GAP
        )
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
                _text(output, start, y, f"F{frame}", w + 2)
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
            # A flat white ground keeps the silhouette's outer contour free of checker edges.
            image = checker(image, "#ffffff" if kind == "silhouette" else "checker")
            output[y : y + plan["h"], x : x + plan["w"]] = np.repeat(
                np.repeat(image, factor, axis=0), factor, axis=1
            )
            _frame(output, x, y, plan["w"], plan["h"])
        panels.append({"number": number, **plan})
    return output, factor, panels
