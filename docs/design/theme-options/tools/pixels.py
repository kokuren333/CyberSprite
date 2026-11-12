"""Hand-drawn pixel assets for the Circuit White theme mockups.

Everything here is original work for CyberSprite (Apache-2.0): the 5x7 silk-screen
font, the 16x16 UI icons and the sample sprite. Nothing is traced or copied from
another product. Assets are emitted as inline SVG made of 1px rectangles so they
stay pixel-crisp at integer zoom.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def runs_path(pixels: set[tuple[int, int]]) -> str:
    """Merge pixels into horizontal runs and return an SVG path string."""
    rows: dict[int, list[int]] = {}
    for x, y in pixels:
        rows.setdefault(y, []).append(x)
    parts = []
    for y in sorted(rows):
        xs = sorted(rows[y])
        start = prev = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == prev + 1:
                prev = x
                continue
            parts.append(f"M{start} {y}h{prev - start + 1}v1h-{prev - start + 1}z")
            if x is not None:
                start = prev = x
    return "".join(parts)


def grid_to_layers(rows: list[str], w: int = 16, h: int = 16) -> dict[str, set]:
    assert len(rows) == h, f"need {h} rows, got {len(rows)}"
    layers: dict[str, set] = {}
    for y, row in enumerate(rows):
        assert len(row) == w, f"row {y} has width {len(row)}: {row!r}"
        for x, ch in enumerate(row):
            if ch != ".":
                layers.setdefault(ch, set()).add((x, y))
    return layers


def flood(rows: list[str], seeds, ch: str) -> list[str]:
    g = [list(r) for r in rows]
    h, w = len(g), len(g[0])
    stack = list(seeds)
    while stack:
        x, y = stack.pop()
        if 0 <= x < w and 0 <= y < h and g[y][x] == ".":
            g[y][x] = ch
            stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return ["".join(r) for r in g]


def overlay(rows: list[str], pts, ch: str) -> list[str]:
    g = [list(r) for r in rows]
    for x, y in pts:
        g[y][x] = ch
    return ["".join(r) for r in g]


def blank(w=16, h=16):
    return ["." * w for _ in range(h)]


def outline_shape(mask: dict[tuple[int, int], str], w=16, h=16) -> list[str]:
    """mask: pixel -> fill char. Pixels on the 4-neighbour edge become '#'."""
    g = blank(w, h)
    g = [list(r) for r in g]
    for (x, y), ch in mask.items():
        edge = any((x + dx, y + dy) not in mask for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        g[y][x] = "#" if edge else ch
    return ["".join(r) for r in g]


# tone char -> CSS custom property used as fill
TONES = {"#": "--ic1", "+": "--ic2", "*": "--ic3", "@": "--ic4"}


def svg_symbol(name: str, rows: list[str], w=16, h=16) -> str:
    layers = grid_to_layers(rows, w, h)
    paths = []
    for ch in ("*", "+", "@", "#"):
        if ch in layers:
            paths.append(f'<path style="fill:var({TONES[ch]})" d="{runs_path(layers[ch])}"/>')
    return f'<symbol id="i-{name}" viewBox="0 0 {w} {h}">{"".join(paths)}</symbol>'


# --------------------------------------------------------------------------
# 5x7 silk-screen font (variable width, uppercase + digits + a few marks)
# --------------------------------------------------------------------------

FONT = {
    "A": [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
    "C": [" ### ", "#   #", "#    ", "#    ", "#    ", "#   #", " ### "],
    "D": ["#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "],
    "E": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    "F": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
    "G": [" ### ", "#   #", "#    ", "# ###", "#   #", "#   #", " ####"],
    "H": ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "I": ["###", " # ", " # ", " # ", " # ", " # ", "###"],
    "J": ["  ###", "   # ", "   # ", "   # ", "#  # ", "#  # ", " ##  "],
    "K": ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    "M": ["#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"],
    "N": ["#   #", "##  #", "# # #", "# # #", "#  ##", "#   #", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "P": ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
    "Q": [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"],
    "R": ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    "S": [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "],
    "W": ["#   #", "#   #", "#   #", "# # #", "# # #", "# # #", " # # "],
    "X": ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"],
    "Y": ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "Z": ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"],
    "0": [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    "1": [" # ", "## ", " # ", " # ", " # ", " # ", "###"],
    "2": [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    "3": ["#### ", "    #", "    #", " ### ", "    #", "    #", "#### "],
    "4": ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    "5": ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    "6": [" ### ", "#    ", "#    ", "#### ", "#   #", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "],
    "8": [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    "9": [" ### ", "#   #", "#   #", " ####", "    #", "    #", " ### "],
    "-": ["   ", "   ", "   ", "###", "   ", "   ", "   "],
    ":": [" ", "#", " ", " ", " ", "#", " "],
    ".": [" ", " ", " ", " ", " ", " ", "#"],
    "/": ["    #", "   # ", "   # ", "  #  ", " #   ", " #   ", "#    "],
    "_": ["    ", "    ", "    ", "    ", "    ", "    ", "####"],
    " ": ["  ", "  ", "  ", "  ", "  ", "  ", "  "],
}


def silk(text: str, cls: str = "silk", scale: int = 1) -> str:
    """Render text in the pixel font as an inline SVG (fill = currentColor)."""
    px = set()
    x = 0
    for ch in text.upper():
        glyph = FONT[ch]
        gw = len(glyph[0])
        for y, row in enumerate(glyph):
            assert len(row) == gw, (ch, row)
            for i, c in enumerate(row):
                if c == "#":
                    px.add((x + i, y))
        x += gw + 1
    w = max(x - 1, 1)
    return (
        f'<svg class="{cls}" width="{w * scale}" height="{7 * scale}" viewBox="0 0 {w} 7" '
        f'aria-label="{text}" role="img"><path fill="currentColor" d="{runs_path(px)}"/></svg>'
    )


# --------------------------------------------------------------------------
# 16x16 icons. '#'=line (--ic1), '+'=accent fill (--ic2), '*'=light fill (--ic3)
# --------------------------------------------------------------------------


def _diag_tool(segments) -> list[str]:
    """Build a 45-degree tool. segments: list of (vmin, vmax, halfwidth, fillchar).

    u = x + y measures across the axis (centre line u = 15), v = x - y along it
    (positive towards the upper right)."""
    mask = {}
    for y in range(16):
        for x in range(16):
            u, v = x + y, x - y
            for vmin, vmax, hw, ch in segments:
                if vmin <= v <= vmax and abs(u - 15) <= hw:
                    mask[(x, y)] = ch
                    break
    return outline_shape(mask)


def icon_pencil():
    g = _diag_tool([
        (9, 12, 2, "+"),     # eraser cap
        (7, 8, 2, "#"),      # metal band
        (-7, 6, 2, "*"),     # wooden body
        (-9, -8, 1, "*"),    # cone
        (-12, -10, 0, "#"),  # graphite tip
    ])
    return g


def icon_eraser():
    g = _diag_tool([
        (2, 9, 4, "*"),
        (-6, 1, 4, "+"),
    ])
    # surface line under the eraser
    g = overlay(g, [(x, 15) for x in range(1, 10)], "#")
    return g


def icon_eyedropper():
    g = _diag_tool([
        (9, 13, 3, "+"),     # bulb
        (7, 8, 3, "#"),      # collar
        (-8, 6, 1, "*"),     # glass tube
        (-11, -9, 0, "#"),   # tip
    ])
    return g


def icon_line():
    g = blank()
    pts = [(2 + i, 13 - i) for i in range(12)]
    g = overlay(g, pts, "#")
    for cx, cy in ((2, 13), (13, 2)):
        sq = [(cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        g = overlay(g, sq, "#")
        g = overlay(g, [(cx, cy)], "*")
    return g


ICON_RECT = [
    "................",
    "................",
    "..############..",
    "..#..........#..",
    "..#..........#..",
    "..#..........#..",
    "..#..........#..",
    "..#..........#..",
    "..#..........#..",
    "..#..........#..",
    "..#..........#..",
    "..#..........#..",
    "..#..........#..",
    "..############..",
    "................",
    "................",
]

ICON_ELLIPSE = [
    "................",
    "................",
    ".....######.....",
    "...##......##...",
    "..#..........#..",
    "..#..........#..",
    ".#............#.",
    ".#............#.",
    ".#............#.",
    ".#............#.",
    "..#..........#..",
    "..#..........#..",
    "...##......##...",
    ".....######.....",
    "................",
    "................",
]

ICON_FILL = [
    "..........#.....",
    ".........#+#....",
    "........#+++#...",
    "........#+++#...",
    ".........###....",
    "................",
    "..############..",
    "..#..........#..",
    "..#..........#..",
    "..#..........#..",
    "..#..........#..",
    "..#..........#..",
    "..#..........#..",
    "..############..",
    "................",
    "................",
]


def icon_fill():
    return flood(ICON_FILL, [(5, 9)], "+")


def icon_select():
    g = blank()
    per = []
    x0, y0, x1, y1 = 2, 2, 13, 13
    for x in range(x0, x1 + 1):
        per.append((x, y0))
    for y in range(y0 + 1, y1 + 1):
        per.append((x1, y))
    for x in range(x1 - 1, x0 - 1, -1):
        per.append((x, y1))
    for y in range(y1 - 1, y0, -1):
        per.append((x0, y))
    on = [p for i, p in enumerate(per) if (i // 2) % 2 == 0]
    return overlay(g, on, "#")


ICON_MOVE = [
    "................",
    ".......##.......",
    "......####......",
    ".....######.....",
    ".......##.......",
    "...#...##...#...",
    "..##...##...##..",
    ".##############.",
    ".##############.",
    "..##...##...##..",
    "...#...##...#...",
    ".......##.......",
    ".....######.....",
    "......####......",
    ".......##.......",
    "................",
]

ICON_HAND = [
    "................",
    ".......#........",
    ".....##*##......",
    "....#*#*#*#.....",
    "...##*#*#*#.....",
    "..#*#*#*#*#.....",
    "..#*#*#*#*#.##..",
    "..#*#*#*#*##**#.",
    "..#********#*#..",
    "..#**********#..",
    "..#*********#...",
    "...#*******#....",
    "....#*****#.....",
    ".....#####......",
    "................",
    "................",
]

ICON_ZOOM_RING = [
    "................",
    "....####........",
    "..##....##......",
    ".#........#.....",
    ".#........#.....",
    ".#........#.....",
    ".#........#.....",
    ".#........#.....",
    ".#........#.....",
    "..##....##......",
    "....####........",
    "................",
    "................",
    "................",
    "................",
    "................",
]


def icon_zoom():
    g = flood(ICON_ZOOM_RING, [(5, 5)], "*")
    plus = [(x, y) for x in range(3, 9) for y in (5, 6)] + [(x, y) for x in (5, 6) for y in range(3, 9)]
    g = overlay(g, plus, "#")
    handle = []
    for i in range(5):
        handle += [(9 + i, 10 + i), (10 + i, 10 + i), (9 + i, 11 + i) if 11 + i < 16 else (9 + i, 10 + i)]
    handle = [(x, y) for x, y in handle if x < 16 and y < 16]
    return overlay(g, handle, "#")


ICON_EYE = [
    "................",
    "................",
    "................",
    "................",
    ".....######.....",
    "...##......##...",
    "..#....##....#..",
    ".#....####....#.",
    ".#....####....#.",
    "..#....##....#..",
    "...##......##...",
    ".....######.....",
    "................",
    "................",
    "................",
    "................",
]

ICON_EYE_OFF = [
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    ".#............#.",
    "..##........##..",
    "....########....",
    "...#..#..#..#...",
    "..#...#..#...#..",
    "................",
    "................",
    "................",
    "................",
    "................",
]

ICON_LOCK = [
    "................",
    "......####......",
    ".....#....#.....",
    "....#......#....",
    "....#......#....",
    "....#......#....",
    "..############..",
    "..#**********#..",
    "..#****##****#..",
    "..#****##****#..",
    "..#****##****#..",
    "..#*****#****#..",
    "..#**********#..",
    "..############..",
    "................",
    "................",
]

ICON_UNLOCK = [
    "................",
    "........####....",
    ".......#....#...",
    "......#......#..",
    "......#......#..",
    "......#.........",
    "..############..",
    "..#**********#..",
    "..#****##****#..",
    "..#****##****#..",
    "..#****##****#..",
    "..#*****#****#..",
    "..#**********#..",
    "..############..",
    "................",
    "................",
]

ICON_CHECK = [
    "................",
    "................",
    "................",
    "................",
    "............##..",
    "...........##...",
    "..........##....",
    "..##.....##.....",
    "...##...##......",
    "....##.##.......",
    ".....###........",
    "......#.........",
    "................",
    "................",
    "................",
    "................",
]

ICON_WARN = [
    "................",
    ".......##.......",
    ".......##.......",
    "......#..#......",
    "......#..#......",
    ".....#.##.#.....",
    ".....#.##.#.....",
    "....#..##..#....",
    "....#..##..#....",
    "...#...##...#...",
    "...#........#...",
    "..#....##....#..",
    "..#....##....#..",
    ".##############.",
    "................",
    "................",
]


def icon_warn():
    g = ICON_WARN
    seeds = [(x, y) for y in range(16) for x in range(16)
             if g[y][x] == "." and 3 <= y <= 12 and 4 <= x <= 11]
    # fill only the inside of the triangle
    inside = []
    for y in range(16):
        row = g[y]
        idx = [i for i, c in enumerate(row) if c == "#"]
        if len(idx) >= 2 and 3 <= y <= 12:
            left, right = idx[0], idx[-1]
            inside += [(x, y) for x in range(left + 1, right) if row[x] == "."]
    return overlay(g, inside, "+")


ICON_ERROR = [
    "................",
    "................",
    "....########....",
    "...#........#...",
    "..#..........#..",
    "..#..#....#..#..",
    "..#...#..#...#..",
    "..#....##....#..",
    "..#....##....#..",
    "..#...#..#...#..",
    "..#..#....#..#..",
    "..#..........#..",
    "...#........#...",
    "....########....",
    "................",
    "................",
]


def icon_error():
    g = ICON_ERROR
    inside = []
    for y in range(16):
        row = g[y]
        idx = [i for i, c in enumerate(row) if c == "#"]
        if len(idx) >= 2 and 3 <= y <= 12:
            inside += [(x, y) for x in range(idx[0] + 1, idx[-1]) if row[x] == "."]
    return overlay(g, inside, "+")


ICON_AGENT = [
    "................",
    "......####......",
    ".......##.......",
    ".......##.......",
    "...##########...",
    "...#********#...",
    ".###*##**##*###.",
    ".#.#*##**##*#.#.",
    ".###********###.",
    "...#**####**#...",
    "...#********#...",
    "...##########...",
    "................",
    "................",
    "................",
    "................",
]

ICON_HUMAN = [
    "................",
    "......####......",
    ".....#****#.....",
    ".....#****#.....",
    ".....#****#.....",
    "......####......",
    "................",
    "....########....",
    "...#********#...",
    "..#**********#..",
    "..#**********#..",
    "..############..",
    "................",
    "................",
    "................",
    "................",
]

ICON_LINK = [
    "................",
    "................",
    "................",
    "................",
    "................",
    "..####....####..",
    ".#....#..#....#.",
    ".#..########..#.",
    ".#....#..#....#.",
    "..####....####..",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
]


def _tri(direction: str, x0: int, rows=range(3, 14), centre=8, fill="+"):
    mask = {}
    for y in rows:
        w = 6 - abs(y - centre)
        for i in range(w):
            x = x0 + i if direction == "r" else x0 - i
            mask[(x, y)] = fill
    return mask


def icon_play():
    return outline_shape(_tri("r", 5))


def icon_next():
    m = _tri("r", 3)
    for y in range(3, 14):
        m[(11, y)] = "#"
        m[(12, y)] = "#"
    return outline_shape(m)


def icon_prev():
    m = _tri("l", 12)
    for y in range(3, 14):
        m[(3, y)] = "#"
        m[(4, y)] = "#"
    return outline_shape(m)


def icon_first():
    m = _tri("l", 13)
    m2 = _tri("l", 9)
    m.update(m2)
    for y in range(3, 14):
        m[(2, y)] = "#"
        m[(3, y)] = "#"
    return outline_shape(m)


def icon_last():
    m = _tri("r", 2)
    m.update(_tri("r", 6))
    for y in range(3, 14):
        m[(12, y)] = "#"
        m[(13, y)] = "#"
    return outline_shape(m)


def icon_onion():
    g = blank()
    back = []
    for x in range(1, 10):
        back += [(x, 1), (x, 9)]
    for y in range(1, 10):
        back += [(1, y), (9, y)]
    back = [(x, y) for x, y in back if (x + y) % 2 == 0]
    g = overlay(g, back, "#")
    front = {}
    for x in range(5, 15):
        for y in range(5, 15):
            front[(x, y)] = "+"
    fr = outline_shape(front)
    out = []
    for y in range(16):
        out.append("".join(fr[y][x] if fr[y][x] != "." else g[y][x] for x in range(16)))
    return out


ICON_PLUS = [
    "................",
    "................",
    "................",
    "................",
    ".......##.......",
    ".......##.......",
    ".......##.......",
    "....########....",
    "....########....",
    ".......##.......",
    ".......##.......",
    ".......##.......",
    "................",
    "................",
    "................",
    "................",
]

ICON_MINUS = [
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "....########....",
    "....########....",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
]

ICON_CLOSE = [
    "................",
    "................",
    "................",
    "................",
    "....##....##....",
    ".....##..##.....",
    "......####......",
    ".......##.......",
    "......####......",
    ".....##..##.....",
    "....##....##....",
    "................",
    "................",
    "................",
    "................",
    "................",
]

ICON_SWAP = [
    "................",
    "................",
    "......#.........",
    ".....##.........",
    "....#########...",
    ".....##.....#...",
    "......#.....#...",
    "............#...",
    "...#........#...",
    "...#.....#......",
    "...#.....##.....",
    "...#########....",
    ".........##.....",
    ".........#......",
    "................",
    "................",
]

ICON_LOOP = [
    "................",
    "................",
    "................",
    "....#######.....",
    "...#.......#....",
    "..#.........#...",
    "..#.......#####.",
    "..#........###..",
    "..#.........#...",
    "...#............",
    "....#######.....",
    "................",
    "................",
    "................",
    "................",
    "................",
]

ICON_CHIP = [
    "................",
    "....#.#.#.#.....",
    "....#.#.#.#.....",
    "..###########...",
    "..#.++++++++#...",
    "###+++++++++###.",
    "..#+**+++**+#...",
    "###+**+++**+###.",
    "..#+++++++++#...",
    "###+*******+###.",
    "..#+++++++++#...",
    "..###########...",
    "....#.#.#.#.....",
    "....#.#.#.#.....",
    "................",
    "................",
]

ICON_GRID = [
    "................",
    "................",
    "..#...#...#...#.",
    "..#...#...#...#.",
    ".##############.",
    "..#...#...#...#.",
    "..#...#...#...#.",
    "..#...#...#...#.",
    ".##############.",
    "..#...#...#...#.",
    "..#...#...#...#.",
    "..#...#...#...#.",
    ".##############.",
    "..#...#...#...#.",
    "................",
    "................",
]

ICON_DIFF = [
    "................",
    "................",
    ".######..######.",
    ".#****#..#++++#.",
    ".#****#..#++++#.",
    ".#****#..#++++#.",
    ".#****#..#++++#.",
    ".#****#..#++++#.",
    ".#****#..#++++#.",
    ".######..######.",
    "................",
    "......#..#......",
    ".....##..##.....",
    "....###..###....",
    ".....##..##.....",
    "......#..#......",
]

ICON_SOURCE = [
    "................",
    "..#########.....",
    "..#*******##....",
    "..#*******#*#...",
    "..#*******####..",
    "..#**********#..",
    "..#*##****##*#..",
    "..#*#+#**#+#*#..",
    "..#**#+##+#**#..",
    "..#***#++#***#..",
    "..#****##****#..",
    "..#**********#..",
    "..#**********#..",
    "..############..",
    "................",
    "................",
]

ICON_REVERT = [
    "................",
    "................",
    "................",
    ".....#..........",
    "....##..........",
    "...##########...",
    "....##.......#..",
    ".....#........#.",
    "..............#.",
    "..............#.",
    ".............#..",
    "....#########...",
    "................",
    "................",
    "................",
    "................",
]

ICON_SQUARE_BRUSH = [
    "................",
    "................",
    "................",
    "................",
    "....########....",
    "....#++++++#....",
    "....#++++++#....",
    "....#++++++#....",
    "....#++++++#....",
    "....#++++++#....",
    "....#++++++#....",
    "....########....",
    "................",
    "................",
    "................",
    "................",
]

ICON_ROUND_BRUSH = [
    "................",
    "................",
    "................",
    "................",
    "......####......",
    ".....#++++#.....",
    "....#++++++#....",
    "....#++++++#....",
    "....#++++++#....",
    "....#++++++#....",
    ".....#++++#.....",
    "......####......",
    "................",
    "................",
    "................",
    "................",
]

ICON_VIA = [".###.", "#***#", "#***#", "#***#", ".###."]
ICON_VIA4 = [".##.", "#**#", "#**#", ".##."]
ICON_CARET = [
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "....#######.....",
    ".....#####......",
    "......###.......",
    ".......#........",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
]


def all_icons() -> dict[str, list[str]]:
    return {
        "pencil": icon_pencil(),
        "eraser": icon_eraser(),
        "line": icon_line(),
        "rect": ICON_RECT,
        "ellipse": ICON_ELLIPSE,
        "fill": icon_fill(),
        "eyedropper": icon_eyedropper(),
        "select": icon_select(),
        "move": ICON_MOVE,
        "hand": ICON_HAND,
        "zoom": icon_zoom(),
        "eye": ICON_EYE,
        "eye-off": ICON_EYE_OFF,
        "lock": ICON_LOCK,
        "unlock": ICON_UNLOCK,
        "check": ICON_CHECK,
        "warn": icon_warn(),
        "error": icon_error(),
        "agent": ICON_AGENT,
        "human": ICON_HUMAN,
        "link": ICON_LINK,
        "play": icon_play(),
        "next": icon_next(),
        "prev": icon_prev(),
        "first": icon_first(),
        "last": icon_last(),
        "onion": icon_onion(),
        "plus": ICON_PLUS,
        "minus": ICON_MINUS,
        "close": ICON_CLOSE,
        "swap": ICON_SWAP,
        "loop": ICON_LOOP,
        "chip": ICON_CHIP,
        "grid": ICON_GRID,
        "diff": ICON_DIFF,
        "source": ICON_SOURCE,
        "revert": ICON_REVERT,
        "brush-square": ICON_SQUARE_BRUSH,
        "brush-round": ICON_ROUND_BRUSH,
        "caret": ICON_CARET,
    }


def icon_defs() -> str:
    syms = [svg_symbol(n, r) for n, r in all_icons().items()]
    syms.append(svg_symbol("via", ICON_VIA, 5, 5))
    syms.append(svg_symbol("via4", ICON_VIA4, 4, 4))
    return (
        '<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>'
        + "".join(syms)
        + "</defs></svg>"
    )


def icon(name: str, cls: str = "ico", size: int = 16, label: str | None = None) -> str:
    aria = f' role="img" aria-label="{label}"' if label else ' aria-hidden="true"'
    return f'<svg class="{cls}" width="{size}" height="{size}"{aria}><use href="#i-{name}"/></svg>'


def via(cls: str = "via", big: bool = True) -> str:
    n = 5 if big else 4
    name = "via" if big else "via4"
    return f'<svg class="{cls}" width="{n}" height="{n}" aria-hidden="true"><use href="#i-{name}"/></svg>'


# --------------------------------------------------------------------------
# sample sprite: 32x32, cs-circuit-16 project palette (index 0 = transparent)
# --------------------------------------------------------------------------

PALETTE = [
    (None, "transparent"),
    ("#161827", "ink"),
    ("#434C60", "slate"),
    ("#838F9C", "steel"),
    ("#C7D2D6", "mist"),
    ("#F5F9F3", "paper"),
    ("#26428C", "navy"),
    ("#22B4D8", "trace-cyan"),
    ("#A8ECEF", "ice"),
    ("#1F6B52", "moss"),
    ("#6CBF3E", "leaf"),
    ("#F2C94C", "gold"),
    ("#D4692E", "rust"),
    ("#F4BF98", "skin"),
    ("#6E3434", "bark"),
    ("#D6333F", "red"),
    ("#6D3F9A", "violet"),
]

# char -> palette index
SPRITE_KEY = {
    "o": 1, "d": 6, "g": 4, "G": 3, "w": 5, "c": 8, "y": 11, "Y": 12,
    "b": 7, "B": 6, "s": 13, "S": 12, "p": 15, "P": 14, "h": 2,
}

SPRITE = [
    "..............oooo..............",
    ".............oywyyo.............",
    ".............oYyyYo.............",
    "..............oGGo..............",
    "..............ogGo..............",
    ".........oooooooooooooo.........",
    ".......oogggwwgggggggGGoo.......",
    "......ogggwwgggggggggggGGo......",
    ".....ogggwgggggggggggggggGo.....",
    ".....ogooooooooooooooooooGo.....",
    ".....ogo" "dccddddddddddddd" "oGo.....",
    ".....ogo" "dddccddddddccddd" "oGo.....",
    ".....ogo" "dddccddddddccddd" "oGo.....",
    ".....ogo" "ddpddddddddddpdd" "oGo.....",
    "....oogooooooooooooooooooGoo....",
    "...opoggggggggggggggggggGGopo...",
    "...oPoGGGGGGGGGGGGGGGGGGGGoPo...",
    "....oooooooooooooooooooooooo....",
    "..............oddo..............",
    ".........oooooooooooooo.........",
    "........obbbbbbccbbbbbBo........",
    ".......obbobbbbccbbbbobBo.......",
    ".......obbobbbbbbbbbbobBo.......",
    ".......osSobbbbbbbbbbBosSo......",
    ".......ooogggggyygggggooo.......",
    "..........oBBBBBBBBBBo..........",
    "..........oBBBBooBBBBo..........",
    "...........oBBo..oBBo...........",
    "..........ogggo..ogggo..........",
    ".........ogggGo..ogggGo.........",
    ".........oooooo..oooooo.........",
    "................................",
]


def sprite_svg(zoom: int, checker_cell: int = 2, overlay_box=None) -> str:
    n = 32
    layers = grid_to_layers(SPRITE, n, n)
    parts = []
    # checkerboard (cell = checker_cell canvas pixels)
    a, b = set(), set()
    for cy in range(n // checker_cell):
        for cx in range(n // checker_cell):
            tgt = a if (cx + cy) % 2 == 0 else b
            for dy in range(checker_cell):
                for dx in range(checker_cell):
                    tgt.add((cx * checker_cell + dx, cy * checker_cell + dy))
    parts.append(f'<path style="fill:var(--cs-checker-a)" d="{runs_path(a)}"/>')
    parts.append(f'<path style="fill:var(--cs-checker-b)" d="{runs_path(b)}"/>')
    by_index: dict[int, set] = {}
    for ch, px in layers.items():
        by_index.setdefault(SPRITE_KEY[ch], set()).update(px)
    for idx in sorted(by_index):
        parts.append(f'<path fill="{PALETTE[idx][0]}" d="{runs_path(by_index[idx])}"/>')
    size = n * zoom
    return (
        f'<svg class="sprite" width="{size}" height="{size}" viewBox="0 0 {n} {n}" '
        f'role="img" aria-label="sample sprite, frame 2">{"".join(parts)}</svg>'
    )


def sprite_usage() -> dict[int, int]:
    layers = grid_to_layers(SPRITE, 32, 32)
    out: dict[int, int] = {}
    for ch, px in layers.items():
        out[SPRITE_KEY[ch]] = out.get(SPRITE_KEY[ch], 0) + len(px)
    out[0] = 32 * 32 - sum(out.values())
    return out


# --------------------------------------------------------------------------
# traces: rasterise 0/45/90-degree polylines into pixel sets
# --------------------------------------------------------------------------


def trace_pixels(points, width: int = 1) -> set[tuple[int, int]]:
    px = set()
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        dx, dy = x1 - x0, y1 - y0
        assert dx == 0 or dy == 0 or abs(dx) == abs(dy), "only 0/45/90 degrees"
        n = max(abs(dx), abs(dy))
        sx = (dx > 0) - (dx < 0)
        sy = (dy > 0) - (dy < 0)
        for i in range(n + 1):
            x, y = x0 + sx * i, y0 + sy * i
            for ox in range(width):
                for oy in range(width):
                    px.add((x + ox, y + oy))
    return px


def notch_svg(n: int, bw: int) -> str:
    """Corner notch overlay for an IC-like panel (top-left 45-degree cut).

    Placed at (-bw-1, -bw-1) relative to the panel padding box. Paints the cut-away
    triangle with --notch-out, the diagonal border with --notch-line and a 1px
    halo with --halo (transparent-looking when the panel is idle)."""
    s = n + 1
    out, line, halo = set(), set(), set()
    for y in range(s):
        for x in range(s):
            xp, yp = x - 1, y - 1
            d = xp + yp
            if d < n - 2:
                out.add((x, y))
            elif d == n - 2:
                halo.add((x, y))
            elif d <= n - 2 + bw:
                line.add((x, y))
    return (
        f'<svg class="notch" width="{s}" height="{s}" aria-hidden="true">'
        f'<path style="fill:var(--notch-out)" d="{runs_path(out)}"/>'
        f'<path style="fill:var(--halo)" d="{runs_path(halo)}"/>'
        f'<path style="fill:var(--notch-line)" d="{runs_path(line)}"/></svg>'
    )
