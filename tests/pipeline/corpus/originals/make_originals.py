"""Calibration corpus, category (a): original indexed pixel art (SPEC §11.9).

Every image here is original work of the CyberSprite project (Apache-2.0).
Each image is a character grid: one character = one pixel, and the image's
``palette`` list maps characters to palette indices in order.  When an image
uses transparency, its first palette entry is ``(".", None)`` and becomes
index 0 = "#00000000".

A few images (dither ramp, orb, glyph sheet, flat field, walker strip) are
assembled from small hand-drawn grids or integer formulas; the assembly is
plain integer code, so the output is still fully deterministic.

Run (from the repository root):

    python tests/pipeline/corpus/originals/make_originals.py

Re-running reproduces identical PNG and JSON bytes (for a given Pillow/zlib).
The script verifies every written PNG by decoding it again.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parent

# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

IMAGES: list[dict] = []


def art(name, palette, rows, notes, tags):
    IMAGES.append({"name": name, "palette": palette, "rows": rows, "notes": notes, "tags": tags})


def hex_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# ----------------------------------------------------------------------------
# 1. heart_8x8 — smallest icon
# ----------------------------------------------------------------------------
art(
    "heart_8x8",
    [(".", None), ("1", "#3a1024"), ("2", "#d23a4f"), ("3", "#ff9aa8"), ("4", "#8e1f3a")],
    [
        ".11..11.",
        "13211221",
        "13222241",
        "12222241",
        ".122241.",
        "..1241..",
        "...11...",
        "........",
    ],
    "8x8 heart icon. Smallest size in the set; at 2x the whole image is 16 px.",
    ["icon", "tiny", "transparent"],
)

# ----------------------------------------------------------------------------
# 2. gem_10x10
# ----------------------------------------------------------------------------
art(
    "gem_10x10",
    [
        (".", None),
        ("1", "#12283a"),
        ("2", "#1f6f8b"),
        ("3", "#34b3c9"),
        ("4", "#8ff0e4"),
        ("5", "#f4fffb"),
        ("6", "#164a63"),
    ],
    [
        "..111111..",
        ".15443321.",
        "1544333221",
        "1444332261",
        "1333322661",
        ".13322661.",
        "..132661..",
        "...1261...",
        "....11....",
        "..........",
    ],
    "Faceted gem, cut facets give diagonal colour edges.",
    ["icon", "transparent", "diagonal-edges"],
)

# ----------------------------------------------------------------------------
# 3. key_16x8 — wide, non-square
# ----------------------------------------------------------------------------
art(
    "key_16x8",
    [(".", None), ("1", "#2b1a0e"), ("2", "#e0a526"), ("3", "#ffe08a"), ("4", "#9a5f12")],
    [
        "..1111..........",
        ".133221.........",
        "132..4211111111.",
        "12....4233333331",
        "12....4244444441",
        "142..4211141141.",
        ".144441...1..1..",
        "..1111..........",
    ],
    "Key with a transparent hole inside the bow. Non-square (2:1). Teeth are 1 px wide.",
    ["icon", "transparent", "non-square", "interior-hole", "1px-features"],
)

# ----------------------------------------------------------------------------
# 4. sword_16x16 — 45-degree diagonal
# ----------------------------------------------------------------------------
art(
    "sword_16x16",
    [
        (".", None),
        ("1", "#1b1626"),
        ("2", "#8a5f8e"),
        ("3", "#6f7f98"),
        ("4", "#b9c6d6"),
        ("5", "#f2f6ff"),
        ("6", "#d9a23a"),
        ("7", "#8a5a1c"),
        ("8", "#5a3a5e"),
        ("9", "#e04a5a"),
        ("a", "#ffb0b0"),
    ],
    [
        "..............1.",
        ".............151",
        "............1541",
        "...........15431",
        "..........15431.",
        ".........15431..",
        "....1...15431...",
        "...161.15431....",
        "...17615431.....",
        "....176431......",
        "....12761.......",
        "..11288761......",
        ".19a8811761.....",
        ".19991..11......",
        "..111...........",
        "................",
    ],
    "Diagonal sword: long 45-degree staircase edges, 3-tone blade, "
    "crossguard on the opposite diagonal, 1 px pommel highlight.",
    ["icon", "transparent", "diagonal-edges"],
)

# ----------------------------------------------------------------------------
# 5. potion_12x16 — tall, non-square
# ----------------------------------------------------------------------------
art(
    "potion_12x16",
    [
        (".", None),
        ("1", "#231a33"),
        ("2", "#e8f4ff"),
        ("3", "#9fb4cc"),
        ("4", "#4fd17a"),
        ("5", "#238a5a"),
        ("6", "#b6f59a"),
        ("7", "#b07a4a"),
        ("8", "#6e4527"),
    ],
    [
        "....1111....",
        "...177781...",
        "...178881...",
        "....1331....",
        "....1231....",
        "...123331...",
        "..12333331..",
        ".1233333331.",
        "123666666651",
        "124644444551",
        "124444444551",
        "134444444551",
        "134444445551",
        ".1444445551.",
        "..15555551..",
        "...111111...",
    ],
    "Potion bottle, 3:4. Glass highlight is a 1 px vertical line.",
    ["icon", "transparent", "non-square", "1px-features"],
)

# ----------------------------------------------------------------------------
# 6. hero_16x16 — small character
# ----------------------------------------------------------------------------
art(
    "hero_16x16",
    [
        (".", None),
        ("1", "#1d1a2b"),
        ("2", "#f2c29b"),
        ("3", "#c98a6a"),
        ("4", "#6b3a2a"),
        ("5", "#9c5a36"),
        ("6", "#3f7fd0"),
        ("7", "#2a4f8f"),
        ("8", "#e3b440"),
        ("9", "#4a3226"),
        ("a", "#ffffff"),
        ("b", "#5b5f73"),
    ],
    [
        ".....111111.....",
        "....15555541....",
        "...1554444551...",
        "...1544444441...",
        "...1422222241...",
        "...12a2222a21...",
        "...1212222121...",
        "...1322222231...",
        "....13333331....",
        "....17666671....",
        "...1766666671...",
        "..127888888721..",
        "...17bbbbbb71...",
        "....1bb11bb1....",
        "...1999119991...",
        "...1111..1111...",
    ],
    "Front-facing chibi character. Eye highlights are single white pixels "
    "surrounded by other colours.",
    ["character", "transparent", "single-pixel-detail"],
)

# ----------------------------------------------------------------------------
# 7. walker_48x24 — 3-frame walk cycle silhouette (16x24 each)
# ----------------------------------------------------------------------------
_WALK_UPPER = [
    "................",
    "......3333......",
    ".....322222.....",
    "....32222221....",
    "....32221111....",
    "....32221411....",
    "....32221111....",
    "....32222211....",
    ".....3222221....",
    "....322222221...",
    "...32222222221..",
    "...32222222221..",
    "...32222222221..",
    "..322222222221..",
    "..3222222222221.",
    "..3222222222221.",
    ".32222222222221.",
    "..11122222111...",
]
_WALK_LEGS_A = [
    "....11...22.....",
    "...11.....22....",
    "...11.....22....",
    "..11.......22...",
    "..111......2221.",
    "................",
]
_WALK_LEGS_C = [
    "....22...11.....",
    "...22.....11....",
    "...22.....11....",
    "..22.......11...",
    "..222......1111.",
    "................",
]
_WALK_LEGS_B = [
    "...1122222111...",
    "......122.......",
    "......122.......",
    "......122.......",
    "......122.......",
    "......122.......",
    "......12221.....",
    "................",
]
_frame_a = _WALK_UPPER + _WALK_LEGS_A
_frame_b = _WALK_UPPER[1:17] + _WALK_LEGS_B  # passing pose, body bobs up 1 px
_frame_c = _WALK_UPPER + _WALK_LEGS_C
art(
    "walker_48x24",
    [(".", None), ("1", "#22203a"), ("2", "#3d3a63"), ("3", "#7f7bc4"), ("4", "#ffd25a")],
    [a + b + c for a, b, c in zip(_frame_a, _frame_b, _frame_c)],
    "Sprite strip: 3 walk-cycle poses (16x24 each) of a hooded silhouette. "
    "Mostly two dark, close colours; a 1 px rim light and a single glowing "
    "eye pixel. Frame B bobs up by 1 px.",
    [
        "character",
        "animation-strip",
        "transparent",
        "non-square",
        "dark-low-contrast",
        "single-pixel-detail",
    ],
)

# ----------------------------------------------------------------------------
# 8. terrain_48x16 — grass / stone / water tiles, each 16x16 and wrap-seamless
# ----------------------------------------------------------------------------
_GRASS = [
    "GGGGgGGGGGGGGGGG",
    "GGGhGGGGGGGgGGGG",
    "GGhHhGGGGGGGGGGG",
    "GGGgGGGGGhGGGGGG",
    "GGGGGGGGhHhGGGGg",
    "GGGGGgGGGgGGGGGG",
    "GGGGGGGGGGGGGGGG",
    "GhGGGGGGGGGGhGGG",
    "hHhGGGGgGGGhHhGG",
    "GgGGGGGGGGGGgGGG",
    "GGGGGGhGGGGGGGGG",
    "GGGGGhHhGGGGGgGG",
    "GGgGGGgGGGGGGGGG",
    "GGGGGGGGGGGhGGGG",
    "GGGGGGGGGGhHhGGG",
    "GGGGgGGGGGGgGGGG",
]
_STONE = [
    "SSSSSSsmSSSSSSsm",
    "SssssskmSssGsskm",
    "skkkkkkmskkkkkkm",
    "mmmmmmmmmmmmmmmm",
    "SSsmSSSSSSsmSSSS",
    "sskmSssksskmSsss",
    "kkkmskkkkkkmskkk",
    "mmmmmmmmmmmmmmmm",
    "SSSSSSsmSSSSSSsm",
    "SsGssskmSssssskm",
    "skkkkkkmskkkkkkm",
    "mmmmmmmmmmmmmmmm",
    "SSsmSSSSSSsmSSSS",
    "sskmSssssskmSssk",
    "kkkmskkkkkkmskkk",
    "mmmmmmmmmmmmmmmm",
]
_WATER = [
    "WWWWWWWWWWWWWWWW",
    "WWvvvWWWWWWWWWWW",
    "WvWWWvWWWWWWwwWW",
    "WWWWWWWWWWWWWWWW",
    "WWWWWWWWWvvvWWWW",
    "WWwwWWWWvWWWvWWW",
    "WWWWWWWWWWWWWWWW",
    "WWWWWWWWWWWWWWWf",
    "vvWWWWWWWWWWWWvv",
    "WWvWWWWwwWWWWvWW",
    "WWWWWWWWWWWWWWWW",
    "WWWWWvvvWWWWWWWW",
    "WWWWvWWWvWWWwwWW",
    "WwwWWWWWWWWWWWWW",
    "WWWWWWWWWWWfWWWW",
    "WWWWWWWWWWWWWWWW",
]
art(
    "terrain_48x16",
    [
        ("g", "#2f6b2e"),
        ("G", "#4f9a3c"),
        ("h", "#86c95a"),
        ("H", "#c4e88a"),
        ("m", "#34363f"),
        ("k", "#5b5f6e"),
        ("s", "#7d8294"),
        ("S", "#a9aebd"),
        ("w", "#1f4f8f"),
        ("W", "#2f73c0"),
        ("v", "#5aa6e8"),
        ("f", "#c8ecff"),
    ],
    [g + s + w for g, s, w in zip(_GRASS, _STONE, _WATER)],
    "Tile set chunk: grass, stone brick and water tiles (16x16 each, each "
    "wraps seamlessly). Opaque, large mostly-uniform regions, periodic "
    "mortar lines with an 8/4 px rhythm that can alias with the cell size.",
    ["terrain", "opaque", "tileset", "periodic-structure", "single-pixel-detail"],
)

# ----------------------------------------------------------------------------
# 9. button_32x16 — UI button with bevel and text
# ----------------------------------------------------------------------------
_O = [".TTT.", "T...T", "T...T", "T...T", "T...T", "T...T", ".TTT."]
_K = ["T...T", "T..T.", "T.T..", "TT...", "T.T..", "T..T.", "T...T"]
_face = ["F" * 28 for _ in range(12)]
for _i in range(7):
    _row = list(_face[2 + _i])
    _glyphs = _O[_i] + "F" + _K[_i]
    for _j, _ch in enumerate(_glyphs):
        if _ch != ".":
            _row[8 + _j] = _ch
    _face[2 + _i] = "".join(_row).replace(".", "F")
art(
    "button_32x16",
    [
        (".", None),
        ("o", "#1a1c2c"),
        ("L", "#f0e6c8"),
        ("F", "#c8b48a"),
        ("D", "#8a7350"),
        ("T", "#3b2a1a"),
    ],
    ["." + "o" * 30 + "."]
    + ["o" + "L" * 29 + "F" + "o"]
    + ["o" + "L" + f + "D" + "o" for f in _face]
    + ["o" + "F" + "D" * 29 + "o"]
    + ["." + "o" * 30 + "."],
    "UI button: 1 px outline, bevel, 'OK' label, transparent corner pixels. "
    "Long straight edges, large flat face.",
    ["ui", "transparent", "non-square", "text", "1px-features"],
)

# ----------------------------------------------------------------------------
# 10. onebit_cat_24x16 — 1-bit, highest contrast
# ----------------------------------------------------------------------------
art(
    "onebit_cat_24x16",
    [("-", "#e8e4d8"), ("#", "#101418")],
    [
        "------------------------",
        "---------#---------###--",
        "------------------##----",
        "--------------#---#-----",
        "--#---#-----------##----",
        "--##-##------------###--",
        "--#####-----------------",
        "--#-#-#-----------------",
        "--#####--------------#--",
        "---###------------------",
        "--#####---------#-------",
        "-#######----------------",
        "-########----#----------",
        "-#########---#----------",
        "-#############----------",
        "########################",
    ],
    "1-bit (2 colours, opaque): sitting cat, crescent moon, isolated star "
    "pixels. Maximum contrast; eyes are 1 px holes.",
    ["1-bit", "opaque", "high-contrast", "single-pixel-detail"],
)

# ----------------------------------------------------------------------------
# 11. dither_ramp_32x16 — ordered (Bayer 4x4) dither between 4 colours
# ----------------------------------------------------------------------------
_BAYER4 = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
_DCH = "abcd"
_dither_rows = []
for _y in range(16):
    _r = []
    for _x in range(32):
        _level = (_x * 48) // 32  # 0..46
        _pair, _frac = divmod(_level, 16)
        _r.append(_DCH[_pair + 1] if _frac > _BAYER4[_y % 4][_x % 4] else _DCH[_pair])
    _dither_rows.append("".join(_r))
art(
    "dither_ramp_32x16",
    [("a", "#1b1d3a"), ("b", "#4a3f7a"), ("c", "#b0607f"), ("d", "#f2b26b")],
    _dither_rows,
    "Ordered-dither ramp (integer Bayer 4x4) across 4 colours; contains pure "
    "checkerboard columns. Hard case: the 1 px period of the dither "
    "competes with the true cell period during grid detection.",
    ["dither", "opaque", "checkerboard", "hard-grid"],
)

# ----------------------------------------------------------------------------
# 12. night_wires_24x24 — 1 px lines and isolated pixels
# ----------------------------------------------------------------------------
art(
    "night_wires_24x24",
    [
        ("-", "#121a2e"),
        ("*", "#fff6d5"),
        ("w", "#5d6a8a"),
        ("p", "#8a6a4a"),
        ("h", "#3c4a70"),
        ("g", "#26304a"),
    ],
    [
        "----------------*-------",
        "--*---------------------",
        "--------------------*---",
        "-----------*------------",
        "-----p------------------",
        "---ppppp--------------ww",
        "www--p--wwww------wwww--",
        "-----p------wwwwww------",
        "-----pw-----------------",
        "-----p-w------------*---",
        "-----p--w---------------",
        "-*---p---w--------------",
        "-----p----w---*---------",
        "-----p-----w------------",
        "-----p------w---------*-",
        "-----p-------w----------",
        "--*--p--------w---------",
        "-----p---------w--------",
        "-----p----------w-------",
        "-----p-----------w------",
        "hhhhhhhhhhhhhhhhhhhhhhhh",
        "gggggggggggggggggggggggg",
        "gggggggghggggggggggggggg",
        "gggggggggggggggggggggggg",
    ],
    "Night sky: 1 px pole, 1 px sagging wires, a 45-degree 1 px guy wire, "
    "isolated single-pixel stars and one isolated pixel in the ground. "
    "Cleanup with min_cluster >= 2 would destroy the stars.",
    ["opaque", "1px-lines", "single-pixel-detail", "isolated-pixels"],
)

# ----------------------------------------------------------------------------
# 13. flat_field_64x48 — huge flat area, tiny detail
# ----------------------------------------------------------------------------
_flat = [list("s" * 64) for _ in range(48)]
for _y, _line in ((14, "b-b"), (15, "-b-")):
    for _j, _ch in enumerate(_line):
        if _ch != "-":
            _flat[_y][41 + _j] = _ch
_flat[9][12] = "y"
art(
    "flat_field_64x48",
    [("s", "#6a8caf"), ("b", "#2a3040"), ("y", "#fff2b0")],
    ["".join(r) for r in _flat],
    "Largest image: a single flat colour with a 3x2 bird and one isolated "
    "pixel. Hard case: almost no edges, so the grid signal comes from "
    "only a handful of boundaries.",
    ["opaque", "flat", "few-edges", "hard-grid", "single-pixel-detail"],
)

# ----------------------------------------------------------------------------
# 14. sparse_firefly_32x32 — tiny sprite on a mostly transparent canvas
# ----------------------------------------------------------------------------
_sparse = [list("." * 32) for _ in range(32)]
for _i, _line in enumerate([".w.w.", ".wbw.", "..b..", ".gGg.", "..g.."]):
    for _j, _ch in enumerate(_line):
        if _ch != ".":
            _sparse[12 + _i][19 + _j] = _ch
_sparse[25][6] = "g"
art(
    "sparse_firefly_32x32",
    [
        (".", None),
        ("b", "#2b2a20"),
        ("w", "#c9d6e8"),
        ("g", "#8fbf3a"),
        ("G", "#e9ff6a"),
    ],
    ["".join(r) for r in _sparse],
    "A 5x5 firefly plus one stray glow pixel on a 32x32 transparent canvas "
    "(about 1% coverage). Hard case: very few edges; alpha edges dominate.",
    ["transparent", "sparse", "few-edges", "hard-grid", "isolated-pixels"],
)

# ----------------------------------------------------------------------------
# 15. glyphs_52x14 — original 3x5 pixel font with drop shadow
# ----------------------------------------------------------------------------
_FONT = {
    "A": [".#.", "#.#", "###", "#.#", "#.#"],
    "B": ["##.", "#.#", "##.", "#.#", "##."],
    "C": [".##", "#..", "#..", "#..", ".##"],
    "E": ["###", "#..", "##.", "#..", "###"],
    "I": ["###", ".#.", ".#.", ".#.", "###"],
    "L": ["#..", "#..", "#..", "#..", "###"],
    "P": ["##.", "#.#", "##.", "#..", "#.."],
    "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "S": [".##", "#..", ".#.", "..#", "##."],
    "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "X": ["#.#", "#.#", ".#.", "#.#", "#.#"],
    "Y": ["#.#", "#.#", ".#.", ".#.", ".#."],
    "0": [".#.", "#.#", "#.#", "#.#", ".#."],
    "2": ["##.", "..#", ".#.", "#..", "###"],
    "6": [".##", "#..", "##.", "#.#", ".#."],
    " ": ["...", "...", "...", "...", "..."],
}
_text = [list("." * 52) for _ in range(14)]
for _line, _top in (("PIXEL 2026", 1), ("CYBER SPRITE", 8)):
    for _pass, _ink, _off in (("shadow", "s", 1), ("ink", "#", 0)):
        for _n, _ch in enumerate(_line):
            for _gy, _grow in enumerate(_FONT[_ch]):
                for _gx, _px in enumerate(_grow):
                    if _px == "#":
                        _text[_top + _gy + _off][2 + _n * 4 + _gx + _off] = _ink
art(
    "glyphs_52x14",
    [(".", None), ("#", "#f4e9d8"), ("s", "#5a4a6e")],
    ["".join(r) for r in _text],
    "Two lines of text in an original 3x5 pixel font with a 1 px drop "
    "shadow. Many 1 px strokes and 1 px gaps at a regular 4 px pitch.",
    ["text", "transparent", "non-square", "1px-features", "periodic-structure"],
)

# ----------------------------------------------------------------------------
# 16. emblem_lowcontrast_16x16 — near-identical neighbouring colours
# ----------------------------------------------------------------------------
art(
    "emblem_lowcontrast_16x16",
    [("D", "#474f5a"), ("b", "#4d5560"), ("L", "#535b66")],
    [
        "bbbbbbbbbbbbbbbb",
        "bbbbbbbbbbbbbbbb",
        "bbbbbDDDDDDbbbbb",
        "bbbbDbbbbbbDbbbb",
        "bbbDbbbbbbbbDbbb",
        "bbDbbbbLLbbbbDbb",
        "bbDbbbLbbLbbbDbb",
        "bbDbbLbbbbLbbDbb",
        "bbDbbLbbbbLbbDbb",
        "bbDbbbLbbLbbbDbb",
        "bbDbbbbLLbbbbDbb",
        "bbbDbbbbbbbbDLbb",
        "bbbbDbbbbbbDLbbb",
        "bbbbbDDDDDDLbbbb",
        "bbbbbbLLLLLbbbbb",
        "bbbbbbbbbbbbbbbb",
    ],
    "Carved emblem in three greys that differ by 6 per channel. Hard case: "
    "neighbouring colours sit well inside purity_tolerance (16), and the "
    "edge signal is weak; exact palette mode must still keep all three.",
    ["opaque", "low-contrast", "near-identical-colours", "hard-grid"],
)


# ----------------------------------------------------------------------------
# 17. orb_24x24 — 31 shades + transparency (32-entry palette)
# ----------------------------------------------------------------------------
def _ramp(keys, n):
    """Integer piecewise-linear ramp through key colours, n entries."""
    out = []
    segs = len(keys) - 1
    for i in range(n):
        pos = i * segs * 1000 // (n - 1)
        s = min(pos // 1000, segs - 1)
        t = pos - s * 1000
        a, b = hex_rgb(keys[s]), hex_rgb(keys[s + 1])
        out.append(
            "#%02x%02x%02x" % tuple((a[c] * (1000 - t) + b[c] * t + 500) // 1000 for c in range(3))
        )
    return out


_ORB_KEYS = ["#140c2a", "#3a1f6b", "#1f6f8f", "#3fc3a3", "#d8f08a", "#fffbe6"]
_orb_colors = _ramp(_ORB_KEYS, 31)
_ORB_CH = "0123456789ABCDEFGHIJKLMNOPQRSTU"
_inside = []
for _y in range(24):
    for _x in range(24):
        _dx, _dy = 2 * _x + 1 - 24, 2 * _y + 1 - 24
        if _dx * _dx + _dy * _dy <= 22 * 22:
            _inside.append(((_dx + 9) ** 2 + (_dy + 9) ** 2, _y, _x))
_uniq = sorted({d for d, _, _ in _inside}, reverse=True)  # far from light = dark
_rank = {d: i for i, d in enumerate(_uniq)}
_orb = [list("." * 24) for _ in range(24)]
for _d, _y, _x in _inside:
    _orb[_y][_x] = _ORB_CH[_rank[_d] * 31 // len(_uniq)]
art(
    "orb_24x24",
    [(".", None)] + list(zip(_ORB_CH, _orb_colors)),
    ["".join(r) for r in _orb],
    "Shaded sphere using a 31-step hue-shifted ramp plus transparency "
    "(32 palette entries, the maximum here). Bands are 1-2 px wide and "
    "neighbouring shades are close. Shading computed with integer maths.",
    ["transparent", "many-colours", "near-identical-colours", "gradient-bands"],
)


# ----------------------------------------------------------------------------
# build
# ----------------------------------------------------------------------------
def build(spec):
    name, palette, rows = spec["name"], spec["palette"], spec["rows"]
    h, w = len(rows), len(rows[0])
    assert all(len(r) == w for r in rows), f"{name}: ragged rows {[len(r) for r in rows]}"
    chars = [c for c, _ in palette]
    assert len(set(chars)) == len(chars), f"{name}: duplicate palette char"
    transparent = palette[0][1] is None
    assert all(col is not None for _, col in palette[1:]), name
    index = {c: i for i, c in enumerate(chars)}
    rgba = []
    for c, col in palette:
        rgba.append((0, 0, 0, 0) if col is None else hex_rgb(col) + (255,))
    opaque = [p for p in rgba if p[3] == 255]
    assert len(set(opaque)) == len(opaque), f"{name}: duplicate colour"
    data = bytearray()
    used = set()
    for r in rows:
        for c in r:
            assert c in index, f"{name}: unknown char {c!r}"
            data.append(index[c])
            used.add(index[c])
    assert used == set(range(len(palette))), (
        f"{name}: unused palette entries {set(range(len(palette))) - used}"
    )

    img = Image.frombytes("P", (w, h), bytes(data))
    flat = []
    for p in rgba:
        flat.extend(p[:3])
    img.putpalette(flat, "RGB")
    png = OUT / f"{name}.png"
    if transparent:
        img.save(png, format="PNG", transparency=0, optimize=False)
    else:
        img.save(png, format="PNG", optimize=False)

    # verify by decoding the written file
    back = Image.open(png)
    assert back.mode == "P" and back.size == (w, h), name
    raw = back.convert("RGBA").tobytes()
    got = [tuple(raw[k : k + 4]) for k in range(0, len(raw), 4)]
    got = [(0, 0, 0, 0) if p[3] == 0 else p for p in got]
    want = [rgba[i] for i in data]
    assert got == want, f"{name}: decoded pixels differ"

    meta = {
        "name": name,
        "category": "a",
        "width": w,
        "height": h,
        "palette": ["#00000000" if p[3] == 0 else "#%02x%02x%02x%02x" % p for p in rgba],
        "transparent_index": 0 if transparent else None,
        "opaque_colors": len(opaque),
        "tags": spec["tags"],
        "notes": spec["notes"],
        "license": "Apache-2.0",
        "author": "CyberSprite project (original work)",
    }
    (OUT / f"{name}.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    return meta


def main():
    names = [s["name"] for s in IMAGES]
    assert len(set(names)) == len(names)
    for spec in IMAGES:
        m = build(spec)
        print(
            f"{m['name']:28s} {m['width']:3d}x{m['height']:<3d} colors={m['opaque_colors']:2d} "
            f"transparent={m['transparent_index'] is not None}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
