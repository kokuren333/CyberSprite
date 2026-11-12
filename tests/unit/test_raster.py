"""Independent small expectations, seeded properties and portable raster vectors."""

from __future__ import annotations

import ast
import importlib.util
import json
import random
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_file(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r = load_file("raster_under_test", ROOT / "src/cybersprite/core/raster.py")
vectors = load_file("raster_vector_generator", ROOT / "tools/gen_raster_vectors.py")


def mask(*rows: str) -> np.ndarray:
    return np.array([[c == "#" for c in row] for row in rows], dtype=bool)


def point_set(array: np.ndarray) -> set[tuple[int, int]]:
    return {(x, y) for y, row in enumerate(array) for x, selected in enumerate(row) if selected}


# These small expectations are reasoned directly from SPEC, not generated.
@pytest.mark.parametrize(
    "end,expected",
    [
        ((2, 1), [(0, 0), (1, 0), (2, 1)]),  # Strict e2 < dx leaves the tie at y=0.
        ((1, 2), [(0, 0), (0, 1), (1, 2)]),
        ((-2, 1), [(0, 0), (-1, 0), (-2, 1)]),
        ((0, 0), [(0, 0)]),
        ((-2, 0), [(-2, 0), (-1, 0), (0, 0)]),
    ],
)
def test_line_hand_computed(end, expected):
    assert r.line_points(0, 0, *end) == expected
    assert r.line_points(*end, 0, 0) == expected


def test_rectangle_hand_computed():
    assert r.rect_points(-1, 2, 2, 2, True) == [(-1, 2), (0, 2), (-1, 3), (0, 3)]
    assert r.rect_points(0, 0, 3, 3, False) == [
        (0, 0),
        (1, 0),
        (2, 0),
        (0, 1),
        (2, 1),
        (0, 2),
        (1, 2),
        (2, 2),
    ]
    assert r.rect_points(2, 3, 1, 3, False) == [(2, 3), (2, 4), (2, 5)]


def test_ellipse_hand_computed():
    # At 3x3 the corner's LHS is 72 <= 81, so every pixel is inside.
    np.testing.assert_array_equal(r.ellipse_mask(3, 3), np.ones((3, 3), dtype=bool))
    assert set(r.ellipse_points(0, 0, 3, 3, False)) == {
        (0, 0),
        (1, 0),
        (2, 0),
        (0, 1),
        (2, 1),
        (0, 2),
        (1, 2),
        (2, 2),
    }
    # At 4x4 a corner's LHS is 288 > 256, while an adjacent pixel has 160.
    np.testing.assert_array_equal(r.ellipse_mask(4, 4), mask(".##.", "####", "####", ".##."))
    assert r.ellipse_points(-2, 4, 1, 1, False) == [(-2, 4)]


def test_polygon_hand_computed():
    square = [(0, 0), (2, 0), (2, 2), (0, 2)]
    assert r.polygon_points(square, True, True) == r.rect_points(0, 0, 3, 3, True)
    assert r.polygon_points(square, True, False) == r.rect_points(0, 0, 3, 3, False)
    assert r.polygon_points([(0, 0), (2, 0), (2, 2)], False, False) == [
        (0, 0),
        (1, 0),
        (2, 0),
        (2, 1),
        (2, 2),
    ]
    triangle = [(0, 0), (4, 0), (0, 4)]
    assert set(r.polygon_points(triangle, True, True)) == {
        (x, y) for y in range(5) for x in range(5 - y)
    }
    # Crossing diagonals plus top/bottom rows; even-odd excludes side centres.
    bow = [(0, 0), (4, 4), (0, 4), (4, 0)]
    expected = mask("#####", ".###.", "..#..", ".###.", "#####")
    assert set(r.polygon_points(bow, True, True)) == point_set(expected)


def test_stroke_hand_computed():
    stairs = [(0, 0), (1, 0), (1, 1), (2, 1), (2, 2), (3, 2), (3, 3)]
    assert r.stroke_path(stairs, False) == stairs
    assert r.stroke_path(stairs, True) == [(0, 0), (1, 1), (2, 2), (3, 3)]
    assert r.stroke_path([(2, 1), (0, 0)], False) == [(2, 1), (1, 0), (0, 0)]
    assert r.stroke_path([(1, 1), (1, 1), (1, 1)]) == [(1, 1)]
    revisit = [(0, 0), (1, 0), (0, 0)]
    assert r.stroke_path(revisit) == revisit
    # Force-accept after a discarded corner, then resume with the retained predecessor.
    assert r.stroke_path([(0, 0), (1, 0), (1, 1), (0, 1), (0, 2)], True) == [
        (0, 0),
        (1, 1),
        (0, 2),
    ]


def test_brush_hand_computed():
    assert r.brush_offsets(2, "square") == [(-1, -1), (0, -1), (-1, 0), (0, 0)]
    assert r.brush_offsets(2, "circle") == r.brush_offsets(2, "square")
    assert r.brush_offsets(4, "circle") == [
        (-1, -2),
        (0, -2),
        (-2, -1),
        (-1, -1),
        (0, -1),
        (1, -1),
        (-2, 0),
        (-1, 0),
        (0, 0),
        (1, 0),
        (-1, 1),
        (0, 1),
    ]
    assert r.stamp([(0, 0), (1, 0), (0, 0)], {"size": 2, "shape": "square"}) == [
        (-1, -1),
        (0, -1),
        (-1, 0),
        (0, 0),
        (1, -1),
        (1, 0),
    ]


def test_flood_hand_computed():
    image = np.array([[1, 0, 1], [0, 1, 0], [1, 0, 1]], dtype=np.uint8)
    np.testing.assert_array_equal(r.flood_fill_mask(image, 0, 0, 4), mask("#..", "...", "..."))
    np.testing.assert_array_equal(r.flood_fill_mask(image, 0, 0, 8), mask("#.#", ".#.", "#.#"))
    assert r.flood_fill_mask(np.ones((100, 100), dtype=np.uint8), 0, 0).all()


@pytest.mark.parametrize(
    "connectivity,expected",
    [
        (4, mask(".#.", "#.#", ".#.")),
        (8, mask("###", "#.#", "###")),
    ],
)
def test_outline_hand_computed(connectivity, expected):
    np.testing.assert_array_equal(
        r.outline_mask(mask("...", ".#.", "..."), "outside", connectivity), expected
    )
    # The centre sees a diagonal hole only with 8-connectivity.
    opaque = mask(".##", "###", "###")
    expected_inside = mask(".##", "#.#", "###") if connectivity == 4 else opaque
    np.testing.assert_array_equal(r.outline_mask(opaque, "inside", connectivity), expected_inside)
    np.testing.assert_array_equal(r.outline_mask(mask("#"), "inside", connectivity), mask("#"))


def test_regions_hand_computed():
    image = np.array([[1, 0, 1], [0, 1, 0], [0, 0, 2]], dtype=np.uint8)
    np.testing.assert_array_equal(r.region_mask({"type": "all"}, 3, 3), np.ones((3, 3), dtype=bool))
    np.testing.assert_array_equal(
        r.region_mask({"type": "rect", "x": -1, "y": 1, "w": 3, "h": 4}, 3, 3),
        mask("...", "##.", "##."),
    )
    np.testing.assert_array_equal(
        r.region_mask({"type": "mask", "x": -1, "y": -1, "rows": ["###", ".##", "#.#"]}, 3, 3),
        mask("##.", ".#.", "..."),
    )
    np.testing.assert_array_equal(
        r.region_mask({"type": "color", "color": 1}, 3, 3, image), mask("#.#", ".#.", "...")
    )
    np.testing.assert_array_equal(
        r.region_mask({"type": "wand", "x": 0, "y": 0}, 3, 3, lambda: image),
        mask("#..", "...", "..."),
    )
    np.testing.assert_array_equal(
        r.region_mask({"type": "wand", "x": 0, "y": 0, "connectivity": 8}, 3, 3, image),
        mask("#.#", ".#.", "..."),
    )


def test_region_image_is_requested_only_when_needed():
    def unavailable():
        pytest.fail("Geometric region requested the layer image")

    assert r.region_mask({"type": "all"}, 2, 2, unavailable).all()
    for x, y in ((10, 0), (0, 10), (-10, 0), (0, -10)):
        for region in (
            {"type": "rect", "x": x, "y": y, "w": 2, "h": 2},
            {"type": "mask", "x": x, "y": y, "rows": ["##", "##"]},
        ):
            assert not r.region_mask(region, 3, 3, unavailable).any()


@pytest.mark.parametrize(
    "flip,rotate,expected,selected",
    [
        (None, 0, [[1, 2, 3], [4, 5, 6]], ["#..", ".##"]),
        (None, 90, [[4, 1], [5, 2], [6, 3]], [".#", "#.", "#."]),
        (None, 180, [[6, 5, 4], [3, 2, 1]], ["##.", "..#"]),
        (None, 270, [[3, 6], [2, 5], [1, 4]], [".#", ".#", "#."]),
        ("h", 0, [[3, 2, 1], [6, 5, 4]], ["..#", "##."]),
        ("v", 0, [[4, 5, 6], [1, 2, 3]], [".##", "#.."]),
        ("h", 90, [[6, 3], [5, 2], [4, 1]], ["#.", "#.", ".#"]),
        ("v", 90, [[1, 4], [2, 5], [3, 6]], ["#.", ".#", ".#"]),
    ],
)
def test_transform_hand_computed(flip, rotate, expected, selected):
    pixels = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.uint8)
    selection = mask("#..", ".##")
    actual, actual_mask = r.transform_block(pixels, selection, flip, rotate)
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(actual_mask, mask(*selected))
    assert actual.dtype == np.uint8 and actual_mask.dtype == np.bool_
    assert not np.shares_memory(actual, pixels)
    assert not np.shares_memory(actual_mask, selection)
    np.testing.assert_array_equal(pixels, [[1, 2, 3], [4, 5, 6]])
    np.testing.assert_array_equal(selection, mask("#..", ".##"))


def test_seeded_line_properties():
    rng = random.Random(251)
    for _ in range(1000):
        x0, y0, x1, y1 = (rng.randrange(-40, 41) for _ in range(4))
        path = r.line_points(x0, y0, x1, y1)
        assert path == r.line_points(x1, y1, x0, y0)
        assert path[0] == min(((x0, y0), (x1, y1)), key=lambda p: (p[1], p[0]))
        assert (x0, y0) in path and (x1, y1) in path
        assert len(path) == max(abs(x1 - x0), abs(y1 - y0)) + 1
        assert len(path) == len(set(path))
        assert all(
            max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1
            for a, b in zip(path, path[1:], strict=False)
        )


def is_l_corner(p, c, n):
    return (
        (p[0] == c[0] or p[1] == c[1])
        and (n[0] == c[0] or n[1] == c[1])
        and p[0] != n[0]
        and p[1] != n[1]
    )


def test_seeded_stroke_properties():
    rng = random.Random(252)
    for _ in range(500):
        vertices = [
            (rng.randrange(-10, 11), rng.randrange(-10, 11)) for _ in range(rng.randrange(1, 15))
        ]
        plain = r.stroke_path(vertices, False)
        perfect = r.stroke_path(vertices, True)
        assert perfect[0] == vertices[0] and perfect[-1] == vertices[-1]
        cursor = iter(plain)
        assert all(any(p == candidate for candidate in cursor) for p in perfect)
        assert not any(is_l_corner(*perfect[i : i + 3]) for i in range(len(perfect) - 2))


@pytest.mark.parametrize("w", range(1, 17))
def test_ellipse_symmetry_and_outline_subset(w):
    for h in range(1, 17):
        interior = r.ellipse_mask(w, h)
        np.testing.assert_array_equal(interior, interior[::-1, :])
        np.testing.assert_array_equal(interior, interior[:, ::-1])
        np.testing.assert_array_equal(interior, r.ellipse_mask(h, w).T)
        filled = set(r.ellipse_points(0, 0, w, h, True))
        outline = set(r.ellipse_points(0, 0, w, h, False))
        assert outline <= filled == point_set(interior)
        # Independent per-pixel neighbour definition, including off-array pixels.
        assert outline == {
            p
            for p in filled
            if any(
                (p[0] + dx, p[1] + dy) not in filled
                for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1))
            )
        }


def test_seeded_polygon_properties():
    rng = random.Random(253)
    for _ in range(100):
        points = [(rng.randrange(-5, 6), rng.randrange(-5, 6)) for _ in range(rng.randrange(2, 9))]
        outline = set(r.polygon_points(points, True, False))
        filled = r.polygon_points(points, True, True)
        assert outline <= set(filled)
        assert filled == sorted(set(filled), key=lambda p: (p[1], p[0]))
        assert filled == r.polygon_points(list(reversed(points)), True, True)
        shifted = [(x + 7, y - 9) for x, y in points]
        assert r.polygon_points(shifted, True, True) == [(x + 7, y - 9) for x, y in filled]


def test_seeded_flood_properties():
    rng = random.Random(254)
    for _ in range(100):
        w, h = rng.randrange(1, 15), rng.randrange(1, 15)
        image = np.array([[rng.randrange(3) for _ in range(w)] for _ in range(h)], dtype=np.uint8)
        original = image.copy()
        x, y = rng.randrange(w), rng.randrange(h)
        for connectivity in (4, 8):
            selected = r.flood_fill_mask(image, x, y, connectivity)
            component = point_set(selected)
            assert (x, y) in component and (image[selected] == image[y, x]).all()
            # Independent set expansion proves connectivity and maximality.
            offsets = [
                (dx, dy)
                for dy in (-1, 0, 1)
                for dx in (-1, 0, 1)
                if (dx or dy) and (connectivity == 8 or abs(dx) + abs(dy) == 1)
            ]
            reached = {(x, y)}
            while True:
                expanded = reached | {
                    (px + dx, py + dy)
                    for px, py in reached
                    for dx, dy in offsets
                    if (px + dx, py + dy) in component
                }
                if expanded == reached:
                    break
                reached = expanded
            assert reached == component
            for px, py in component:
                for dx, dy in offsets:
                    nx, ny = px + dx, py + dy
                    if 0 <= nx < w and 0 <= ny < h and image[ny, nx] == image[y, x]:
                        assert (nx, ny) in component
        np.testing.assert_array_equal(image, original)


def test_seeded_stamp_identity_and_union():
    rng = random.Random(255)
    for _ in range(100):
        points = [(rng.randrange(-5, 6), rng.randrange(-5, 6)) for _ in range(20)]
        expected = list(dict.fromkeys(points))
        assert r.stamp(points, {"size": 1, "shape": "square"}) == expected
        assert r.stamp(points, {"size": 1, "shape": "circle"}) == expected
        for shape in ("square", "circle"):
            size = rng.randrange(1, 9)
            actual = r.stamp(points, {"size": size, "shape": shape})
            assert len(actual) == len(set(actual))
            assert set(actual) == {
                (x + dx, y + dy) for x, y in points for dx, dy in r.brush_offsets(size, shape)
            }
    assert r.stamp([], {"size": 1}) == []


@pytest.mark.parametrize("size", [1, 2, 3, 4, 5, 6, 7, 8, 64])
def test_brush_bounds_and_circle(size):
    square = r.brush_offsets(size, "square")
    assert len(square) == size * size
    assert min(x for x, _ in square) == -(size // 2)
    assert max(x for x, _ in square) == size - 1 - size // 2
    circle = r.brush_offsets(size, "circle")
    expected = {
        (i - size // 2, j - size // 2)
        for j in range(size)
        for i in range(size)
        if (2 * i + 1 - size) ** 2 + (2 * j + 1 - size) ** 2 <= size * size
    }
    assert set(circle) == expected <= set(square)


@pytest.mark.parametrize(
    "call,code",
    [
        (lambda: r.polygon_points([(0, 0), (1, 1)], False, True), "E_INVALID_ARGS"),
        (lambda: r.polygon_points([(0, 0)]), "E_INVALID_ARGS"),
        (lambda: r.stroke_path([]), "E_INVALID_ARGS"),
        (lambda: r.stroke_path([(0, 0)], True, brush_size=2), "E_INVALID_ARGS"),
        (lambda: r.check_pixel_perfect(True, 64), "E_INVALID_ARGS"),
        (lambda: r.brush_offsets(0), "E_INVALID_ARGS"),
        (lambda: r.brush_offsets(65), "E_LIMIT_EXCEEDED"),
        (lambda: r.check_pixel_perfect(False, 65), "E_LIMIT_EXCEEDED"),
        (lambda: r.brush_offsets(1, "triangle"), "E_INVALID_ARGS"),
        (lambda: r.rect_points(0, 0, 0, 1), "E_INVALID_ARGS"),
        (lambda: r.ellipse_mask(1, -1), "E_INVALID_ARGS"),
        (lambda: r.ellipse_mask(100000, 100000), "E_LIMIT_EXCEEDED"),
        (lambda: r.line_points(0.5, 0, 1, 1), "E_INVALID_ARGS"),
        (lambda: r.line_points(True, 0, 1, 1), "E_INVALID_ARGS"),
        (lambda: r.flood_fill_mask(np.zeros((2, 2), dtype=np.uint8), -1, 0), "E_OUT_OF_CANVAS"),
        (lambda: r.flood_fill_mask(np.zeros((2, 2), dtype=np.uint8), 2, 0), "E_OUT_OF_CANVAS"),
        (lambda: r.flood_fill_mask(np.zeros((2, 2), dtype=np.uint8), 0, 2), "E_OUT_OF_CANVAS"),
        (lambda: r.flood_fill_mask(np.zeros((2, 2), dtype=np.uint8), 0, 0, 6), "E_INVALID_ARGS"),
        (lambda: r.flood_fill_mask(np.zeros((2, 2), dtype=np.int64), 0, 0), "E_INVALID_ARGS"),
        (lambda: r.outline_mask(np.ones((2, 2), dtype=bool), "invalid"), "E_INVALID_ARGS"),
        (lambda: r.outline_mask(np.ones((2, 2), dtype=bool), "inside", 5), "E_INVALID_ARGS"),
        (
            lambda: r.region_mask(
                {"type": "color", "color": 256}, 2, 2, np.zeros((2, 2), dtype=np.uint8)
            ),
            "E_INVALID_ARGS",
        ),
        (
            lambda: r.region_mask(
                {"type": "color", "color": "#ff0000"}, 2, 2, np.zeros((2, 2), dtype=np.uint8)
            ),
            "E_INVALID_ARGS",
        ),
        (
            lambda: r.region_mask(
                {"type": "wand", "x": -1, "y": 0}, 2, 2, np.zeros((2, 2), dtype=np.uint8)
            ),
            "E_OUT_OF_CANVAS",
        ),
        (
            lambda: r.region_mask(
                {"type": "color", "color": 0}, 2, 2, np.zeros((1, 1), dtype=np.uint8)
            ),
            "E_INVALID_ARGS",
        ),
        (lambda: r.region_mask({"type": "color", "color": 0}, 2, 2), "E_INVALID_ARGS"),
        (lambda: r.region_mask({"type": "unknown"}, 2, 2), "E_INVALID_ARGS"),
        (lambda: r.region_mask({"type": "all"}, 8193, 1), "E_LIMIT_EXCEEDED"),
        (lambda: r.region_mask({"type": "all"}, 8192, 8192), "E_LIMIT_EXCEEDED"),
        (lambda: r.transform_block(np.zeros((1, 2), dtype=np.uint8), mask("#")), "E_INVALID_ARGS"),
        (
            lambda: r.transform_block(np.zeros((1, 1), dtype=np.uint8), mask("#"), rotate=45),
            "E_INVALID_ARGS",
        ),
        (
            lambda: r.transform_block(np.zeros((1, 1), dtype=np.uint8), mask("#"), flip="both"),
            "E_INVALID_ARGS",
        ),
    ],
)
def test_coded_errors(call, code):
    with pytest.raises(r.RasterError) as caught:
        call()
    assert isinstance(caught.value, ValueError)
    assert caught.value.code == code
    assert caught.value.message and caught.value.hint


@pytest.mark.parametrize("rows", [[], [""], ["#", "##"], ["x"], [1]])
def test_invalid_mask_rows(rows):
    with pytest.raises(r.RasterError) as caught:
        r.region_mask({"type": "mask", "x": 0, "y": 0, "rows": rows}, 2, 2)
    assert caught.value.code == "E_INVALID_ARGS"


def test_no_float_or_unapproved_import_in_raster():
    tree = ast.parse((ROOT / "src/cybersprite/core/raster.py").read_text(encoding="utf-8"))
    allowed = {"__future__", "collections", "numbers", "numpy"}
    for node in ast.walk(tree):
        assert not (isinstance(node, ast.Constant) and isinstance(node.value, float))
        assert not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div))
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] in allowed for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module.split(".")[0] in allowed or node.module in (
                "cybersprite.core.errors",
                "cybersprite.core.limits",
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "float"


def test_vectors_match_committed_bytes():
    generated = vectors.build_vectors()
    directory = ROOT / "tests/vectors/raster"
    assert sorted(generated) == sorted(p.name for p in directory.glob("*.json"))
    for name, expected in generated.items():
        assert (directory / name).read_bytes() == expected, name
        assert b"\r" not in expected and expected.endswith(b"\n")


def test_vectors_cover_required_cases():
    generated = {name: json.loads(data) for name, data in vectors.build_vectors().items()}
    assert len(generated) == 10
    ellipses = generated["ellipse.json"]["cases"]
    assert {
        (case["input"]["w"], case["input"]["h"], case["input"]["filled"]) for case in ellipses
    } == {(w, h, filled) for w in range(1, 17) for h in range(1, 17) for filled in (False, True)}
    assert {case["input"]["region"]["type"] for case in generated["region.json"]["cases"]} == {
        "all",
        "rect",
        "mask",
        "color",
        "wand",
    }
