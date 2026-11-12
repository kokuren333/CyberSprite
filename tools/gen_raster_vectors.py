"""Generate initial language-neutral raster vectors, or check existing bytes.

Run ``python tools/gen_raster_vectors.py`` from any directory. Existing vectors
with changed bytes are never overwritten: review changes and use the project's
golden update workflow when integrating later algorithm changes.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "cybersprite_raster_vectors", ROOT / "src/cybersprite/core/raster.py",
)
assert _spec is not None and _spec.loader is not None
raster = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(raster)


def rows(mask: np.ndarray) -> list[str]:
    """Encode boolean rows without language-specific NumPy values."""
    return ["".join("#" if value else "." for value in row) for row in mask]


def point_rows(points: list[tuple[int, int]], w: int, h: int) -> list[str]:
    mask = np.zeros((h, w), dtype=bool)
    for x, y in points:
        mask[y, x] = True
    return rows(mask)


def build_vectors() -> dict[str, bytes]:
    """Return filename-to-bytes vectors in memory; never write from tests."""
    groups = {}

    def add(kind: str, name: str, inputs: dict, expected: dict) -> None:
        groups.setdefault(kind, []).append({"name": name, "input": inputs, "expected": expected})

    endpoints = [(7, 3), (3, 7), (-3, 7), (-7, 3),
                 (-7, -3), (-3, -7), (3, -7), (7, -3)]
    for octant, (x, y) in enumerate(endpoints):
        for swapped in (False, True):
            args = (x, y, 0, 0) if swapped else (0, 0, x, y)
            add("line", f"octant_{octant}_swap_{int(swapped)}",
                dict(zip(("x0", "y0", "x1", "y1"), args, strict=True)),
                {"points": raster.line_points(*args)})
    for name, args in (("point", (2, -1, 2, -1)), ("horizontal", (3, 2, -2, 2)),
                       ("vertical", (2, 3, 2, -2)), ("tie", (0, 0, 2, 1))):
        add("line", name, dict(zip(("x0", "y0", "x1", "y1"), args, strict=True)),
            {"points": raster.line_points(*args)})

    for w, h in ((1, 1), (1, 4), (4, 1), (4, 3)):
        for filled in (False, True):
            inputs = {"x": -1, "y": 2, "w": w, "h": h, "filled": filled}
            add("rect", f"{w}x{h}_filled_{int(filled)}", inputs,
                {"points": raster.rect_points(**inputs)})

    for w in range(1, 17):
        for h in range(1, 17):
            for filled in (False, True):
                inputs = {"x": 0, "y": 0, "w": w, "h": h, "filled": filled}
                add("ellipse", f"{w}x{h}_filled_{int(filled)}", inputs,
                    {"rows": point_rows(raster.ellipse_points(**inputs), w, h)})

    polygons = {
        "convex": [(0, 0), (6, 0), (3, 5)],
        "concave": [(0, 0), (5, 0), (5, 5), (3, 2), (0, 5)],
        "self_intersecting": [(0, 0), (5, 5), (0, 5), (5, 0)],
        "two_vertices": [(1, 1), (4, 2)],
    }
    for name, points in polygons.items():
        for closed, filled in ((False, False), (True, False), (True, True)):
            inputs = {"points": points, "closed": closed, "filled": filled}
            add("polygon", f"{name}_closed_{int(closed)}_filled_{int(filled)}", inputs,
                {"points": raster.polygon_points(**inputs)})

    paths = {
        "single": [(2, 1)],
        "repeated": [(0, 0), (0, 0), (1, 0), (1, 0), (1, 1)],
        "zigzag": [(0, 0), (3, 0), (3, 3), (0, 3), (0, 0)],
        "staircase": [(0, 0), (1, 0), (1, 1), (2, 1), (2, 2), (3, 2), (3, 3)],
        "descending": [(6, 5), (0, 1), (3, -2)],
        "revisit": [(0, 0), (1, 0), (0, 0), (0, 1)],
    }
    for name, points in paths.items():
        for perfect in (False, True):
            inputs = {"points": points, "pixel_perfect": perfect}
            add("stroke", f"{name}_perfect_{int(perfect)}", inputs,
                {"points": raster.stroke_path(**inputs)})

    for size in range(1, 9):
        for shape in ("square", "circle"):
            brush = {"size": size, "shape": shape}
            points = [(0, 0), (1, 0), (0, 0)]
            add("brush", f"{shape}_{size}", {"brush": brush, "points": points},
                {"offsets": raster.brush_offsets(**brush), "points": raster.stamp(points, brush)})

    image = np.array([[1, 0, 0, 1], [0, 1, 0, 1], [0, 0, 1, 0], [2, 2, 0, 1]], dtype=np.uint8)
    for connectivity in (4, 8):
        inputs = {"image": image.tolist(), "x": 0, "y": 0, "connectivity": connectivity}
        add("flood_fill", f"diagonal_{connectivity}", inputs,
            {"rows": rows(raster.flood_fill_mask(image, 0, 0, connectivity))})

    shapes = {
        "centre": np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]], dtype=bool),
        "full": np.ones((3, 4), dtype=bool),
        "hole": np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], dtype=bool),
        "empty": np.zeros((2, 3), dtype=bool),
    }
    for name, opaque in shapes.items():
        for placement in ("inside", "outside"):
            for connectivity in (4, 8):
                inputs = {"opaque": rows(opaque), "placement": placement, "connectivity": connectivity}
                add("outline", f"{name}_{placement}_{connectivity}", inputs,
                    {"rows": rows(raster.outline_mask(opaque, placement, connectivity))})

    regions = [
        ("all", {"type": "all"}),
        ("rect_clipped", {"type": "rect", "x": -1, "y": 2, "w": 3, "h": 5}),
        ("rect_off_canvas", {"type": "rect", "x": 5, "y": 0, "w": 2, "h": 2}),
        ("mask_clipped", {"type": "mask", "x": -1, "y": -1, "rows": [".#.#", "##..", ".###"]}),
        ("color", {"type": "color", "color": 1}),
        ("color_zero", {"type": "color", "color": 0}),
        ("wand_4", {"type": "wand", "x": 0, "y": 0, "connectivity": 4}),
        ("wand_8", {"type": "wand", "x": 0, "y": 0, "connectivity": 8}),
    ]
    for name, region in regions:
        add("region", name,
            {"region": region, "canvas_w": 4, "canvas_h": 4, "image": image.tolist()},
            {"rows": rows(raster.region_mask(region, 4, 4, image))})

    pixels = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.uint8)
    mask = np.array([[1, 0, 1], [0, 1, 1]], dtype=bool)
    for flip in (None, "h", "v"):
        for rotate in (0, 90, 180, 270):
            block, selection = raster.transform_block(pixels, mask, flip, rotate)
            add("transform", f"flip_{flip}_rotate_{rotate}",
                {"pixels": pixels.tolist(), "mask": rows(mask), "flip": flip, "rotate": rotate},
                {"pixels": block.tolist(), "rows": rows(selection)})

    return {
        f"{kind}.json": (json.dumps({"kind": kind, "cases": groups[kind]},
                                   ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        for kind in sorted(groups)
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check bytes without writing files.")
    args = parser.parse_args()
    destination = ROOT / "tests/vectors/raster"
    vectors = build_vectors()
    changed = [name for name, data in vectors.items()
               if (destination / name).exists() and (destination / name).read_bytes() != data]
    missing = [name for name in vectors if not (destination / name).exists()]
    unexpected = sorted(p.name for p in destination.glob("*.json") if p.name not in vectors)
    if changed or unexpected or (args.check and missing):
        parser.exit(1, f"Vector mismatch: changed={changed}, missing={missing}, unexpected={unexpected}. "
                    "Review differences before using tools/update_goldens.py.\n")
    if not args.check:
        destination.mkdir(parents=True, exist_ok=True)
        for name in missing:
            (destination / name).write_bytes(vectors[name])
    count = sum(len(json.loads(data)["cases"]) for data in vectors.values())
    print(f"{'Checked' if args.check else 'Generated'} {count} cases in {len(vectors)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
