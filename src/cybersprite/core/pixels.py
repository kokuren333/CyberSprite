"""Language-neutral row encodings and palette argument resolution."""

import re
from dataclasses import dataclass
from difflib import get_close_matches

import numpy as np

from .color import dist2, rgb_to_oklab_fixed
from .errors import CyberSpriteError, invalid
from .models import Palette


def pixels_from_rows(rows: list[str], w: int, h: int) -> np.ndarray:
    if len(rows) != h or any(
        len(row) != w * 2 or not re.fullmatch(r"[0-9a-fA-F]*", row) for row in rows
    ):
        raise invalid("Pixel rows must contain h rows of exactly 2*w hexadecimal digits.", w=w, h=h)
    return np.frombuffer(bytes.fromhex("".join(rows)), dtype=np.uint8).reshape(h, w).copy()


def pixels_to_rows(pixels: np.ndarray) -> list[str]:
    if pixels.dtype != np.uint8 or pixels.ndim != 2:
        raise invalid("Pixels must be a two-dimensional uint8 array.")
    return [row.tobytes().hex() for row in pixels]


@dataclass(frozen=True)
class TileRef:
    index: int
    x: bool = False
    y: bool = False
    d: bool = False


def parse_tile(token: str) -> TileRef:
    match = re.fullmatch(r"(0|[1-9][0-9]*)(x?)(y?)(d?)", token)
    if match is None:
        raise invalid(
            "Tile references must be a decimal index followed by flags x, y, d in order.",
            value=token,
        )
    ref = TileRef(int(match[1]), bool(match[2]), bool(match[3]), bool(match[4]))
    if ref.index == 0 and (ref.x or ref.y or ref.d):
        raise invalid("Empty tile 0 must not carry flip flags.", value=token)
    return ref


def tiles_from_rows(rows: list[str], w: int, h: int) -> list[list[TileRef]]:
    result = [[parse_tile(token) for token in row.split()] for row in rows]
    if len(result) != h or any(len(row) != w for row in result):
        raise invalid("Tile rows must contain h rows of exactly w references.", w=w, h=h)
    return result


def tiles_to_rows(rows: list[list[TileRef]]) -> list[str]:
    def token(ref: TileRef) -> str:
        value = (
            str(ref.index)
            + ("x" if ref.x else "")
            + ("y" if ref.y else "")
            + ("d" if ref.d else "")
        )
        parse_tile(value)
        return value

    return [" ".join(token(ref) for ref in row) for row in rows]


def rgba(color: str) -> tuple[int, int, int, int]:
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?", color):
        raise invalid("Color must be #rrggbb or #rrggbbaa.", color=color)
    raw = bytes.fromhex(color[1:])
    return raw[0], raw[1], raw[2], raw[3] if len(raw) == 4 else 255


def rgb_distance(a: tuple, b: tuple) -> int:
    """Compatibility name: Appendix B distance, alpha excluded."""
    return dist2(rgb_to_oklab_fixed(a[:3]), rgb_to_oklab_fixed(b[:3]))


def resolve_color(palette: Palette, value: int | str) -> int:
    if type(value) is int:
        if 0 <= value < len(palette.colors):
            return value
        raise CyberSpriteError(
            "E_INDEX_OUT_OF_RANGE",
            "Palette index is out of range.",
            "Use an index from 0 through palette_size - 1.",
            {"index": value, "palette_size": len(palette.colors)},
        )
    if not isinstance(value, str):
        raise invalid("Color must be a palette index or a #rrggbb/#rrggbbaa string.")
    if value.startswith("@"):
        name = value[1:]
        if ":" in name:
            material, step = name.rsplit(":", 1)
            ramps = [r for r in palette.ramps if r.name == material]
            if (
                len(ramps) != 1
                or not re.fullmatch(r"0|[1-9][0-9]*", step)
                or len(step) > 3
                or int(step) >= len(ramps[0].indices)
            ):
                raise invalid(
                    "Unknown ramp or step; use @ramp:k with a valid zero-based step.",
                    ramp=material,
                    step=step,
                    candidates=[r.name for r in sorted(palette.ramps, key=lambda r: r.name)],
                )
            return ramps[0].indices[int(step)]
        matches = sorted(int(i) for i, n in palette.names.items() if n == name)
        if len(matches) > 1:
            raise CyberSpriteError(
                "E_AMBIGUOUS_REF",
                f"Color name {value!r} matches multiple palette entries.",
                "Use an explicit palette index or give the entries unique names.",
                {"name": name, "candidates": matches},
            )
        if matches:
            return resolve_color(palette, matches[0])
        names = sorted(set(palette.names.values()))
        raise CyberSpriteError(
            "E_INVALID_ARGS",
            f"Unknown color name {value!r}.",
            "Use get_palette to find an existing name or assign one with set_palette_color.",
            {"name": name, "candidates": get_close_matches(name, names, n=8, cutoff=0)},
        )
    target = rgba(value)
    colors = [rgba(color) for color in palette.colors]
    for index, color in enumerate(colors):
        if color == target:
            return index
    nearest = sorted(
        (i for i, c in enumerate(colors) if c[3] == 255 and i != palette.transparent_index),
        key=lambda i: (rgb_distance(colors[i], target), i),
    )[:3]
    raise CyberSpriteError(
        "E_COLOR_NOT_IN_PALETTE",
        f"Color {value} is not in the palette.",
        "Use a palette index, or add the exact color with add_palette_colors first.",
        {"nearest": [{"index": i, "color": palette.colors[i]} for i in nearest]},
    )
