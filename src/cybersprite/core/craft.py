"""Informational integer craft measurements, without image or file output."""

import re
from collections import deque

import numpy as np

from .color import rgb_to_oklab_fixed_numpy


def measure(image, ramps=(), indices=None):
    opaque = image[:, :, 3] != 0
    h, w = opaque.shape
    count = int(np.count_nonzero(opaque))
    padded = np.pad(opaque, 1)
    interior = padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]
    edge = opaque & ~interior
    distance = np.zeros((h, w), dtype=np.int32)
    queue = deque((int(y), int(x)) for y, x in np.argwhere(edge))
    distance[edge] = 1
    depth = 0
    while queue:
        y, x = queue.popleft()
        depth = max(depth, int(distance[y, x]))
        for ny, nx in ((y - 1, x), (y, x - 1), (y, x + 1), (y + 1, x)):
            if 0 <= ny < h and 0 <= nx < w and opaque[ny, nx] and not distance[ny, nx]:
                distance[ny, nx] = distance[y, x] + 1
                queue.append((ny, nx))
    flat = np.zeros((h, w), dtype=bool)
    if h >= 3 and w >= 3:
        center = image[1:-1, 1:-1]
        same = opaque[1:-1, 1:-1].copy()
        for dy in range(3):
            for dx in range(3):
                same &= np.all(center == image[dy : dy + h - 2, dx : dx + w - 2], axis=2)
        flat[1:-1, 1:-1] = same
    # A packed RGBA key keeps equality exact, including alpha.
    keys = np.zeros((h, w), dtype=np.int64)
    for channel in range(4):
        keys = (keys << 8) | image[:, :, channel].astype(np.int64)
    seen, regions = np.zeros((h, w), dtype=bool), 0
    for yy, xx in np.argwhere(opaque):
        y, x = int(yy), int(xx)
        if seen[y, x]:
            continue
        regions += 1
        seen[y, x] = True
        queue.append((y, x))
        while queue:
            cy, cx = queue.popleft()
            for ny, nx in ((cy - 1, cx), (cy, cx - 1), (cy, cx + 1), (cy + 1, cx)):
                if (
                    0 <= ny < h
                    and 0 <= nx < w
                    and opaque[ny, nx]
                    and not seen[ny, nx]
                    and keys[ny, nx] == keys[cy, cx]
                ):
                    seen[ny, nx] = True
                    queue.append((ny, nx))
    dark = 0
    if count:
        lightness = rgb_to_oklab_fixed_numpy(image[:, :, :3])[..., 0]
        dark = int(np.count_nonzero(edge & (lightness == int(lightness[opaque].min()))))
    result = dict(
        fill_permille=count * 1000 // (w * h),
        depth_max=depth,
        flat_permille=int(np.count_nonzero(flat)) * 1000 // max(count, 1),
        region_density_x100=regions * 100 // max(count, 1),
        outline={"dark_permille": dark * 1000 // max(int(np.count_nonzero(edge)), 1)},
    )
    if ramps and indices is not None:
        used = set(int(v) for v in np.unique(indices[opaque]))
        result["ramp_steps"] = {
            ramp.name: len(used.intersection(ramp.indices))
            for ramp in sorted(ramps, key=lambda r: r.name)
        }
    return result


def part_ratios(p, frame, names):
    dimensions: dict[str, list] = {}
    for slc in p.slices:
        if slc.name.startswith("part."):
            keys = [key for key in slc.keys if key.frame <= frame]
            if keys:
                key = max(keys, key=lambda k: k.frame)
                dimensions.setdefault(slc.name[5:], []).append(key)
    result = {}
    for ratio in sorted(names):
        match = re.fullmatch(r"(.+)\.([wh])/(.+)\.([wh])", ratio)
        value = None
        if match:
            a, axis_a, b, axis_b = match.groups()
            left, right = dimensions.get(a, []), dimensions.get(b, [])
            if len(left) == len(right) == 1 and getattr(right[0], axis_b):
                value = getattr(left[0], axis_a) * 1000 // getattr(right[0], axis_b)
        result[ratio] = value
    return result


def evaluate(p):
    from .errors import CyberSpriteError
    from .render import render, render_indexed

    craft = p.platform.craft
    measurements, issues = [], []
    for frame in range(len(p.frames)):
        ramps = getattr(p.palette, "ramps", [])
        indices = None
        if ramps:
            try:
                indices = render_indexed(p, frame)
            except CyberSpriteError as error:
                if error.code != "E_NOT_PALETTE_CLOSED":
                    raise
                indices = render_indexed(p, frame, {"flatten": "nearest"})
        values = measure(render(p, frame), ramps, indices)
        values["parts"] = part_ratios(p, frame, craft.parts)
        measurements.append({"frame": frame, **values})
        comparisons = [
            (key, values[key], getattr(craft, key))
            for key in ("fill_permille", "depth_max", "flat_permille", "region_density_x100")
        ]
        if craft.outline:
            comparisons.append(
                (
                    "outline.dark_permille",
                    values["outline"]["dark_permille"],
                    craft.outline.dark_permille,
                )
            )
        comparisons.extend(("parts." + k, v, craft.parts[k]) for k, v in values["parts"].items())
        comparisons.extend(
            ("ramp_steps." + k, v, craft.ramp_steps)
            for k, v in values.get("ramp_steps", {}).items()
        )
        if p.validation.severity.get("Q-CRF-01") == "off":
            continue
        for metric, value, bounds in comparisons:
            if value is not None and bounds is not None and not bounds[0] <= value <= bounds[1]:
                issues.append(
                    dict(
                        rule="Q-CRF-01",
                        level="info",
                        message=(
                            f"Craft {metric} is {value}; "
                            f"informational range is {bounds[0]}..{bounds[1]}."
                        ),
                        where=dict(
                            frames=[frame],
                            layer=None,
                            bbox=None,
                            points=[],
                            metric=metric,
                            actual=value,
                            expected=bounds,
                        ),
                    )
                )
    return issues, {"frames": measurements}
