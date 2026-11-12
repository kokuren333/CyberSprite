"""Model-free integer rasterization defined by SPEC section 6.4.

Coordinates are (x, y); arrays are indexed [y, x]. Geometry is not clipped:
the Op layer stamps brushes and clips writes to its canvas. Point sets from
rectangles, ellipses and polygons are unique and ordered by (y, x). Lines use
the specification's normalized endpoint order. Strokes follow the input path
(including nonconsecutive revisits); stamps retain first occurrence order,
visiting each brush in row order. No input array or point sequence is mutated.

region_mask accepts a canvas-sized uint8 image or a zero-argument image
callback. It only requests the image for color and wand regions. Region colors
must already be resolved to palette indices by the Op layer.

transform_block takes an already extracted bounding-box block and its selection
mask. The caller places the returned block at the original bounding-box top
left plus (dx, dy), regardless of the changed dimensions after rotation. Moving,
transparent-pixel policy, clipping and project transactions belong to that caller.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping, Sequence
from numbers import Integral

import numpy as np

Point = tuple[int, int]


class RasterError(ValueError):
    """Temporary model-independent error; unify with core errors on integration."""

    def __init__(self, code: str, message: str, hint: str):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


def _invalid(message: str, hint: str) -> RasterError:
    return RasterError("E_INVALID_ARGS", message, hint)


def _integer(value: int, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise _invalid(f"{name} must be an integer.", f"Pass an integer for {name}.")
    return int(value)


def _dimensions(w: int, h: int) -> tuple[int, int]:
    w, h = _integer(w, "w"), _integer(h, "h")
    if w < 1 or h < 1:
        raise _invalid("w and h must be positive.", "Use w >= 1 and h >= 1.")
    return w, h


def _points(points: Sequence[Point], minimum: int) -> list[Point]:
    if len(points) < minimum:
        raise _invalid(
            f"At least {minimum} point(s) are required.",
            f"Supply at least {minimum} coordinate pairs.",
        )
    result = []
    for point in points:
        if len(point) != 2:
            raise _invalid("Each point needs two coordinates.", "Use [x, y] pairs.")
        result.append((_integer(point[0], "x"), _integer(point[1], "y")))
    return result


def _array(image: np.ndarray, dtype: type, name: str) -> None:
    if not isinstance(image, np.ndarray) or image.ndim != 2 or image.dtype != dtype:
        raise _invalid(
            f"{name} must be a two-dimensional {np.dtype(dtype).name} array.",
            f"Pass a NumPy array with dtype {np.dtype(dtype).name} and two axes.",
        )


def _neighbours(connectivity: int) -> tuple[Point, ...]:
    connectivity = _integer(connectivity, "connectivity")
    if connectivity == 4:
        return ((0, -1), (-1, 0), (1, 0), (0, 1))
    if connectivity == 8:
        return ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))
    raise _invalid("connectivity must be 4 or 8.", "Choose connectivity=4 or 8.")


def _mask_points(mask: np.ndarray, x: int = 0, y: int = 0) -> list[Point]:
    rows, cols = np.nonzero(mask)
    return [(int(i) + x, int(j) + y) for j, i in zip(rows, cols, strict=True)]


def line_points(x0: int, y0: int, x1: int, y1: int) -> list[Point]:
    """Return both endpoints using the exact strict comparisons in section 6.4.3."""
    x0, y0 = _integer(x0, "x0"), _integer(y0, "y0")
    x1, y1 = _integer(x1, "x1"), _integer(y1, "y1")
    if (y0, x0) > (y1, x1):
        x0, y0, x1, y1 = x1, y1, x0, y0
    dx, dy = abs(x1 - x0), y1 - y0
    sx = 1 if x1 >= x0 else -1
    err = dx - dy
    x, y = x0, y0
    result = []
    while True:
        result.append((x, y))
        if (x, y) == (x1, y1):
            return result
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += 1


def rect_points(x: int, y: int, w: int, h: int, filled: bool = False) -> list[Point]:
    """Return the full rectangle or its one-pixel perimeter in row order."""
    x, y = _integer(x, "x"), _integer(y, "y")
    w, h = _dimensions(w, h)
    return [
        (x + i, y + j)
        for j in range(h)
        for i in range(w)
        if filled or i == 0 or j == 0 or i == w - 1 or j == h - 1
    ]


def ellipse_mask(w: int, h: int) -> np.ndarray:
    """Evaluate the pixel-centre inequality with signed 64-bit integer arrays."""
    w, h = _dimensions(w, h)
    # Check the largest intermediate in Python integers before allocating int64.
    maximum = max(w * w * h * h, (w - 1) ** 2 * h * h + (h - 1) ** 2 * w * w)
    if maximum > (1 << 63) - 1:
        raise RasterError(
            "E_LIMIT_EXCEEDED",
            "Ellipse arithmetic exceeds signed 64-bit range.",
            "Reduce w and h; canvas dimensions up to 8192 are supported.",
        )
    i = np.arange(w, dtype=np.int64)[None, :]
    j = np.arange(h, dtype=np.int64)[:, None]
    return (2 * i + 1 - w) ** 2 * (h * h) + (2 * j + 1 - h) ** 2 * (w * w) <= w * w * h * h


def ellipse_points(
    x: int,
    y: int,
    w: int,
    h: int,
    filled: bool = False,
) -> list[Point]:
    """Return ellipse interior, or interior pixels bordering its complement."""
    x, y = _integer(x, "x"), _integer(y, "y")
    mask = ellipse_mask(w, h)
    if not filled:
        mask = outline_mask(mask, "inside", 4)
    return _mask_points(mask, x, y)


def polygon_points(
    points: Sequence[Point],
    closed: bool = True,
    filled: bool = False,
) -> list[Point]:
    """Union line outlines with the exact integer even-odd interior test."""
    vertices = _points(points, 2)
    if filled and not closed:
        raise _invalid("A filled polygon must be closed.", "Set closed=True or filled=False.")
    edges = list(zip(vertices[:-1], vertices[1:], strict=True))
    if closed:
        edges.append((vertices[-1], vertices[0]))
    result = set()
    for a, b in edges:
        result.update(line_points(*a, *b))
    if filled:
        min_x, max_x = min(p[0] for p in vertices), max(p[0] for p in vertices)
        min_y, max_y = min(p[1] for p in vertices), max(p[1] for p in vertices)
        ascending = [(a, b) if a[1] < b[1] else (b, a) for a, b in edges if a[1] != b[1]]
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                odd = False
                for (xa, ya), (xb, yb) in ascending:
                    if ya <= y < yb and (x - xa) * (yb - ya) < (y - ya) * (xb - xa):
                        odd = not odd
                if odd:
                    result.add((x, y))
    return sorted(result, key=lambda p: (p[1], p[0]))


def check_pixel_perfect(pixel_perfect: bool, brush_size: int = 1) -> None:
    """Reject a pixel-perfect stroke unless its brush size is exactly one."""
    brush_size = _integer(brush_size, "brush_size")
    _brush_size(brush_size)
    if pixel_perfect and brush_size != 1:
        raise _invalid(
            "pixel_perfect requires brush size 1.",
            "Set brush size to 1 or disable pixel_perfect.",
        )


def stroke_path(
    points: Sequence[Point],
    pixel_perfect: bool = False,
    *,
    brush_size: int = 1,
) -> list[Point]:
    """Build the directed path, then discard L corners and force-accept successors.

    The previous pixel in an L test is the last retained pixel. Endpoints are
    retained; a removed corner's successor is appended without a corner test.
    """
    vertices = _points(points, 1)
    check_pixel_perfect(pixel_perfect, brush_size)
    path = [vertices[0]]
    for a, b in zip(vertices[:-1], vertices[1:], strict=True):
        segment = line_points(*a, *b)
        if segment[0] != a:
            segment.reverse()
        path.extend(segment[1:])
    if not pixel_perfect or len(path) < 3:
        return path
    result = [path[0]]
    i = 1
    while i < len(path) - 1:
        p, c, n = result[-1], path[i], path[i + 1]
        if (
            (p[0] == c[0] or p[1] == c[1])
            and (n[0] == c[0] or n[1] == c[1])
            and p[0] != n[0]
            and p[1] != n[1]
        ):
            result.append(n)
            i += 2
        else:
            result.append(c)
            i += 1
    if i == len(path) - 1:
        result.append(path[i])
    return result


def _brush_size(size: int) -> int:
    size = _integer(size, "size")
    if size < 1:
        raise _invalid("Brush size must be positive.", "Choose a brush size from 1 to 64.")
    if size > 64:
        raise RasterError(
            "E_LIMIT_EXCEEDED",
            f"Brush size {size} exceeds the limit of 64.",
            "Choose a brush size from 1 to 64.",
        )
    return size


def brush_offsets(size: int = 1, shape: str = "square") -> list[Point]:
    """Return brush offsets in row order, anchored at negative size div 2."""
    size = _brush_size(size)
    if shape not in ("square", "circle"):
        raise _invalid("Unknown brush shape.", "Choose shape='square' or 'circle'.")
    mask = np.ones((size, size), dtype=bool) if shape == "square" else ellipse_mask(size, size)
    return _mask_points(mask, -(size // 2), -(size // 2))


def stamp(points: Sequence[Point], brush: Mapping | None = None) -> list[Point]:
    """Stamp a brush; return unique pixels in first occurrence order."""
    points = _points(points, 0)
    brush = {} if brush is None else brush
    offsets = brush_offsets(brush.get("size", 1), brush.get("shape", "square"))
    result, seen = [], set()
    for x, y in points:
        for dx, dy in offsets:
            point = (x + dx, y + dy)
            if point not in seen:
                seen.add(point)
                result.append(point)
    return result


def flood_fill_mask(
    image: np.ndarray,
    x: int,
    y: int,
    connectivity: int = 4,
) -> np.ndarray:
    """Find the seed's uniform connected component using an iterative FIFO queue."""
    _array(image, np.uint8, "image")
    x, y = _integer(x, "x"), _integer(y, "y")
    neighbours = _neighbours(connectivity)
    h, w = image.shape
    if not (0 <= x < w and 0 <= y < h):
        raise RasterError(
            "E_OUT_OF_CANVAS",
            f"Seed ({x}, {y}) is outside canvas {w}x{h}.",
            f"Choose a seed with 0 <= x < {w} and 0 <= y < {h}.",
        )
    selected = np.zeros(image.shape, dtype=bool)
    target = image[y, x]
    queue = deque([(x, y)])
    selected[y, x] = True
    while queue:
        px, py = queue.popleft()
        for dx, dy in neighbours:
            nx, ny = px + dx, py + dy
            if 0 <= nx < w and 0 <= ny < h and not selected[ny, nx] and image[ny, nx] == target:
                selected[ny, nx] = True
                queue.append((nx, ny))
    return selected


def outline_mask(
    opaque: np.ndarray,
    placement: str = "outside",
    connectivity: int = 4,
) -> np.ndarray:
    """Return the inner or outer border; all off-array pixels are nonopaque."""
    _array(opaque, np.bool_, "opaque")
    neighbours = _neighbours(connectivity)
    if placement not in ("inside", "outside"):
        raise _invalid("Unknown outline placement.", "Choose placement='inside' or 'outside'.")
    h, w = opaque.shape
    padded = np.pad(opaque, 1, constant_values=False)
    adjacent = np.zeros(opaque.shape, dtype=bool)
    for dx, dy in neighbours:
        neighbour = padded[1 + dy : 1 + dy + h, 1 + dx : 1 + dx + w]
        adjacent |= ~neighbour if placement == "inside" else neighbour
    return adjacent & (opaque if placement == "inside" else ~opaque)


def check_region_tree(region: dict) -> None:
    """Bound recursion before model parsing or allocating any region arrays."""
    pending = [(region, 1)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if depth > 16 or count > 256:
            raise RasterError(
                "E_LIMIT_EXCEEDED",
                "Region exceeds depth 16 or 256 nodes.",
                "Simplify the region tree to depth <= 16 and total nodes <= 256.",
            )
        if not isinstance(node, dict):
            raise _invalid("Each region must be an object.", "Supply a typed region object.")
        if node.get("type") in ("and", "or", "not"):
            children = node.get("of")
            if (
                not isinstance(children, list)
                or not children
                or (node["type"] == "not" and len(children) != 1)
            ):
                raise _invalid(
                    "and/or require at least one child; not requires exactly one child.",
                    "Use a nonempty of array, with exactly one region for not.",
                )
            if count + len(pending) + len(children) > 256:
                raise RasterError(
                    "E_LIMIT_EXCEEDED",
                    "Region exceeds 256 nodes.",
                    "Reduce the total number of region nodes to 256.",
                )
            pending.extend((child, depth + 1) for child in children)


def region_mask(
    region: dict,
    canvas_w: int,
    canvas_h: int,
    layer_image_fn: Callable[[], np.ndarray] | np.ndarray | None = None,
) -> np.ndarray:
    """Resolve a bounded region tree to a clipped canvas-sized boolean mask."""
    check_region_tree(region)
    return _region_mask(region, canvas_w, canvas_h, layer_image_fn)


def _region_mask(region, canvas_w, canvas_h, layer_image_fn):
    w, h = _dimensions(canvas_w, canvas_h)
    if w > 8192 or h > 8192 or w * h > 16_777_216:
        raise RasterError(
            "E_LIMIT_EXCEEDED",
            "Canvas exceeds the dimension or area limit.",
            "Use dimensions <= 8192 and area <= 16777216.",
        )
    kind = region.get("type")
    if kind in ("and", "or", "not"):
        selected = _region_mask(region["of"][0], w, h, layer_image_fn)
        if kind == "not":
            return ~selected
        for child in region["of"][1:]:
            other = _region_mask(child, w, h, layer_image_fn)
            if kind == "and":
                selected &= other
            else:
                selected |= other
        return selected
    if kind in ("ellipse", "polygon"):
        if kind == "ellipse":
            rw, rh = _dimensions(region["w"], region["h"])
        else:
            vertices = _points(region["points"], 2)
            rw = max(x for x, _ in vertices) - min(x for x, _ in vertices) + 1
            rh = max(y for _, y in vertices) - min(y for _, y in vertices) + 1
        if max(rw, rh) > 8192 or rw * rh > 16_777_216:
            raise RasterError(
                "E_LIMIT_EXCEEDED",
                "Region shape exceeds dimension or area limits.",
                "Use a bounding box <= 8192 per side and area <= 16777216.",
            )
        coords = (
            ellipse_points(region["x"], region["y"], rw, rh, True)
            if kind == "ellipse"
            else polygon_points(vertices, True, True)
        )
        selected = np.zeros((h, w), dtype=bool)
        for x, y in coords:
            if 0 <= x < w and 0 <= y < h:
                selected[y, x] = True
        return selected
    if kind == "all":
        return np.ones((h, w), dtype=bool)
    if kind in ("color", "wand"):
        image = layer_image_fn() if callable(layer_image_fn) else layer_image_fn
        if image is None:
            raise _invalid(
                "Color and wand regions require a layer image.",
                "Supply a canvas-sized uint8 image or an image callback.",
            )
        _array(image, np.uint8, "layer image")
        if image.shape != (h, w):
            raise _invalid(
                "Layer image must match the canvas.", f"Supply an image of shape ({h}, {w})."
            )
        if kind == "color":
            color = _integer(region["color"], "color")
            if not 0 <= color <= 255:
                raise _invalid(
                    "color must be a palette index.", "Resolve color to an index in 0..255."
                )
            return image == color
        return flood_fill_mask(image, region["x"], region["y"], region.get("connectivity", 4))
    if kind not in ("rect", "mask"):
        raise _invalid(
            "Unknown region type.",
            "Choose all, rect, ellipse, polygon, mask, color, wand, and, or, or not.",
        )
    x, y = _integer(region["x"], "x"), _integer(region["y"], "y")
    selected = np.zeros((h, w), dtype=bool)
    if kind == "rect":
        rw, rh = _dimensions(region["w"], region["h"])
        left, right = max(x, 0), min(x + rw, w)
        top, bottom = max(y, 0), min(y + rh, h)
        if left < right and top < bottom:
            selected[top:bottom, left:right] = True
    else:
        rows = region["rows"]
        if (
            not rows
            or not all(isinstance(row, str) for row in rows)
            or not rows[0]
            or any(len(row) != len(rows[0]) for row in rows)
            or any(c not in ".#" for row in rows for c in row)
        ):
            raise _invalid(
                "Mask rows must be a nonempty rectangle of '.' and '#'.",
                "Supply equal-length, nonempty strings containing only '.' and '#'.",
            )
        for j in range(max(0, -y), min(len(rows), h - y)):
            for i in range(max(0, -x), min(len(rows[0]), w - x)):
                selected[y + j, x + i] = rows[j][i] == "#"
    return selected


def transform_block(
    pixels: np.ndarray,
    mask: np.ndarray,
    flip: str | None = None,
    rotate: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Flip then rotate clockwise; return independent block and mask copies."""
    _array(pixels, np.uint8, "pixels")
    _array(mask, np.bool_, "mask")
    if pixels.shape != mask.shape:
        raise _invalid(
            "Block and mask shapes differ.", "Extract pixels and mask from the same bounding box."
        )
    if flip not in (None, "h", "v"):
        raise _invalid("Unknown flip direction.", "Choose flip=None, 'h' or 'v'.")
    rotate = _integer(rotate, "rotate")
    if rotate not in (0, 90, 180, 270):
        raise _invalid(
            "rotate must be 0, 90, 180 or 270.", "Choose a clockwise quarter-turn angle."
        )
    if flip == "h":
        pixels, mask = pixels[:, ::-1], mask[:, ::-1]
    elif flip == "v":
        pixels, mask = pixels[::-1, :], mask[::-1, :]
    return (np.rot90(pixels, -(rotate // 90)).copy(), np.rot90(mask, -(rotate // 90)).copy())
