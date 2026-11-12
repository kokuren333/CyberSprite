"""16x16 UI icon designs for CyberSprite (original work, Apache-2.0).

This module is DATA ONLY: it returns 16 strings of 16 characters per icon.
Pixels are written into the CyberSprite projects (`../<name>.csprite`) by
`build_icons.py`, which calls the CyberSprite CLI `draw_rows` op. The
.csprite projects are the originals; this file records how they were first
drawn so the set can be rebuilt deterministically.

Design characters (mapped to palette indices of ui-icons.gpl in build_icons.py):
  .  transparent        #  ink (outline, 1px)   k  ink-soft
  d  trace-deep         c  trace (cyan)         s  trace-soft
  w  white              g  warn gold            r  error red
  v  agent violet       p  agent-soft violet

Style rules: 1px ink outline, content inside the 14x14 box (1..14), cyan
family for tools, status colours only on status icons, shape always carries
the meaning (never colour alone).
"""

from __future__ import annotations

W = H = 16


# ----------------------------------------------------------------- helpers


def blank() -> list[list[str]]:
    return [["."] * W for _ in range(H)]


def to_rows(g) -> list[str]:
    return ["".join(r) for r in g]


def grid(rows: list[str]) -> list[str]:
    assert len(rows) == H, len(rows)
    for i, r in enumerate(rows):
        assert len(r) == W, (i, r, len(r))
    return list(rows)


def shift(rows: list[str], dx: int = 0, dy: int = 0) -> list[str]:
    g = blank()
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch != "." and 0 <= x + dx < W and 0 <= y + dy < H:
                g[y + dy][x + dx] = ch
    return to_rows(g)


def mirror(rows: list[str]) -> list[str]:
    return [r[::-1] for r in rows]


def put(rows: list[str], pts, ch: str) -> list[str]:
    g = [list(r) for r in rows]
    for x, y in pts:
        g[y][x] = ch
    return to_rows(g)


def outlined(mask: set[tuple[int, int]], fill: str) -> list[str]:
    """4-neighbour edge of the mask becomes ink, the rest `fill` (clean 1px)."""
    g = blank()
    for x, y in mask:
        edge = any((x + dx, y + dy) not in mask for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        g[y][x] = "#" if edge else fill
    return to_rows(g)


def merge(*layers: list[str]) -> list[str]:
    """Later layers paint over earlier ones (non-transparent pixels only)."""
    g = blank()
    for rows in layers:
        for y, r in enumerate(rows):
            for x, ch in enumerate(r):
                if ch != ".":
                    g[y][x] = ch
    return to_rows(g)


def tri_mask(x_base: int, direction: int, y_top: int, widths: list[int]) -> set:
    """Triangle with a vertical base at x_base; widths per row from y_top."""
    m = set()
    for i, w in enumerate(widths):
        for k in range(w):
            m.add((x_base + direction * k, y_top + i))
    return m


# Play-style triangle, 13 rows tall, 10 wide (alternating 1/2 px steps).
TRI_BIG = [1, 2, 4, 5, 7, 8, 10, 8, 7, 5, 4, 2, 1]
# Smaller triangle for the transport buttons, 11 rows tall, 7 wide.
TRI_SMALL = [1, 2, 3, 5, 6, 7, 6, 5, 3, 2, 1]


def rect_mask(x0, y0, x1, y1) -> set:
    return {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}


# ------------------------------------------------------------- tool bar


PENCIL = grid([
    "................",
    "............##..",
    "...........#ss#.",
    "..........#sss#.",
    ".........#c#s#..",
    "........#ccc#...",
    ".......#ccc#....",
    "......#ccc#.....",
    ".....#ccc#......",
    "....#ccc#.......",
    "...#wcc#........",
    "..#wwc#.........",
    "..#kw#..........",
    "..###...........",
    "................",
    "................",
])

ERASER = grid([
    "................",
    "..........#.....",
    ".........#c#....",
    "........#ccc#...",
    ".......#ccccc#..",
    "......#ccccccc#.",
    ".....#w#ccccc#..",
    "....#www#ccc#...",
    "...#wwwww#c#....",
    "...#wwwwww#.....",
    "....#wwww#......",
    ".....#ww#.......",
    "......##........",
    "................",
    "..dddddddddddd..",
    "................",
])

LINE = grid([
    "................",
    "............###.",
    "............#c#.",
    "............###.",
    "...........#....",
    "..........#.....",
    ".........#......",
    "........#.......",
    ".......#........",
    "......#.........",
    ".....#..........",
    "....#...........",
    ".###............",
    ".#c#............",
    ".###............",
    "................",
])

RECT = grid([
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
])

ELLIPSE = grid([
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
])

FILL = shift(grid([
    "...........#....",
    "..........#c#...",
    ".........#ccc#..",
    ".........#ccc#..",
    "..........###...",
    "................",
    "..##########....",
    "..#cccccccc#....",
    "..#cccccccc#....",
    "..#cccccccc#....",
    "..#cccccccc#....",
    "..#cccccccc#....",
    "..#cccccccc#....",
    "..##########....",
    "................",
    "................",
]), 0, 1)

EYEDROPPER = grid([
    "...........##...",
    "..........#dd#..",
    ".........#dddd#.",
    ".........##ddd#.",
    ".........###d#..",
    "........#s###...",
    ".......#s#......",
    "......#s#.......",
    ".....#s#........",
    "....#s#.........",
    "...#s#..........",
    "..#s#...........",
    "..##............",
    ".#..............",
    "................",
    "................",
])


def select_rect() -> list[str]:
    per = []
    x0, y0, x1, y1 = 2, 2, 13, 13
    per += [(x, y0) for x in range(x0, x1 + 1)]
    per += [(x1, y) for y in range(y0 + 1, y1 + 1)]
    per += [(x, y1) for x in range(x1 - 1, x0 - 1, -1)]
    per += [(x0, y) for y in range(y1 - 1, y0, -1)]
    on = [p for i, p in enumerate(per) if (i // 2) % 2 == 0]
    return put(to_rows(blank()), on, "#")


MOVE = grid([
    "................",
    "........#.......",
    ".......###......",
    "......#####.....",
    "........#.......",
    "....#...#...#...",
    "...##...#...##..",
    "..######w######.",
    "...##...#...##..",
    "....#...#...#...",
    "........#.......",
    "......#####.....",
    ".......###......",
    "........#.......",
    "................",
    "................",
])

HAND = shift(grid([
    "................",
    ".......#.#......",
    ".....##w#w##....",
    "....#w#w#w#w#...",
    "....#w#w#w#w#...",
    "....#w#w#w#w#...",
    "..#.#w#w#w#w#...",
    ".#w##w#w#w#w#...",
    ".#wwwwwwwwww#...",
    "..#wwwwwwwww#...",
    "...#wwwwwwww#...",
    "....#wwwwww#....",
    ".....######.....",
    "................",
    "................",
    "................",
]), 1, 1)

ZOOM = grid([
    "................",
    "....#####.......",
    "..##sssss##.....",
    "..#sssssss#.....",
    ".#ssss#ssss#....",
    ".#ssss#ssss#....",
    ".#s#######s#....",
    ".#ssss#ssss#....",
    ".#ssss#ssss#....",
    "..#sssssss#.....",
    "..##sssss###....",
    "....#####.###...",
    "...........###..",
    "............###.",
    ".............##.",
    "................",
])

# ------------------------------------------------------------- timeline

EYE = grid([
    "................",
    "................",
    "................",
    "................",
    ".....######.....",
    "...##wccccw##...",
    "..#wwcc##ccww#..",
    ".#wwwc#w##cwww#.",
    ".#wwwc####cwww#.",
    "..#wwcc##ccww#..",
    "...##wccccw##...",
    ".....######.....",
    "................",
    "................",
    "................",
    "................",
])

EYE_OFF = grid([
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
])

LOCK = grid([
    "................",
    "......####......",
    ".....#....#.....",
    "....#......#....",
    "....#......#....",
    "....#......#....",
    "..############..",
    "..#ssssssssss#..",
    "..#ssss##ssss#..",
    "..#ssss##ssss#..",
    "..#sssss#ssss#..",
    "..#sssss#ssss#..",
    "..#ssssssssss#..",
    "..############..",
    "................",
    "................",
])

UNLOCK = grid([
    "................",
    "........####....",
    ".......#....#...",
    "......#......#..",
    "......#......#..",
    "......#.........",
    "..############..",
    "..#ssssssssss#..",
    "..#ssss##ssss#..",
    "..#ssss##ssss#..",
    "..#sssss#ssss#..",
    "..#sssss#ssss#..",
    "..#ssssssssss#..",
    "..############..",
    "................",
    "................",
])

LINK = grid([
    "................",
    "................",
    "................",
    "................",
    "..#######.......",
    ".#.......#......",
    ".#....##.#.###..",
    ".#...#...#....#.",
    ".#...#...#....#.",
    "..##.#####....#.",
    ".....#........#.",
    "......########..",
    "................",
    "................",
    "................",
    "................",
])


def play() -> list[str]:
    return outlined(tri_mask(3, 1, 2, TRI_BIG), "c")


def pause() -> list[str]:
    return merge(outlined(rect_mask(3, 2, 6, 14), "c"), outlined(rect_mask(9, 2, 12, 14), "c"))


def step_next() -> list[str]:
    return merge(outlined(tri_mask(3, 1, 3, TRI_SMALL), "c"), outlined(rect_mask(10, 3, 12, 13), "c"))


def step_prev() -> list[str]:
    return mirror(step_next())


def last() -> list[str]:
    return merge(
        outlined(tri_mask(1, 1, 3, TRI_SMALL), "c"),
        outlined(tri_mask(6, 1, 3, TRI_SMALL), "c"),
        outlined(rect_mask(12, 3, 14, 13), "c"),
    )


def first() -> list[str]:
    return mirror(last())


def onion() -> list[str]:
    back = []
    for x in range(1, 10):
        back += [(x, 1), (x, 9)]
    for y in range(1, 10):
        back += [(1, y), (9, y)]
    back = [(x, y) for x, y in back if (x + y) % 2 == 0]
    g = put(to_rows(blank()), back, "d")
    return merge(g, outlined(rect_mask(5, 5, 14, 14), "c"))


def grid_icon() -> list[str]:
    g = blank()
    lines = (1, 5, 9, 13)
    for y in range(1, 14):
        for x in range(1, 14):
            if x in lines or y in lines:
                outer = x in (1, 13) or y in (1, 13)
                g[y][x] = "#" if outer else "d"
    return shift(to_rows(g), 1, 1)


# ------------------------------------------------------------- commands

UNDO = shift(grid([
    ".....#..........",
    "....##..........",
    "...###..........",
    "..###########...",
    "...###.....##...",
    "....##.......#..",
    ".....#........#.",
    "..............#.",
    "..............#.",
    ".............#..",
    "...........##...",
    ".....######.....",
    "................",
    "................",
    "................",
    "................",
]), 0, 2)


def redo() -> list[str]:
    return mirror(UNDO)


def add() -> list[str]:
    return outlined(rect_mask(6, 2, 9, 13) | rect_mask(2, 6, 13, 9), "c")


def remove() -> list[str]:
    return outlined(rect_mask(2, 6, 13, 9), "c")


# --------------------------------------------------------------- status


def warning() -> list[str]:
    m = set()
    for i in range(14):
        half = i // 2  # widen by one pixel per side every two rows
        for x in range(7 - half, 9 + half):
            m.add((x, 1 + i))
    g = outlined(m, "g")
    mark = [(x, y) for x in (7, 8) for y in range(5, 10)] + [(7, 11), (8, 11), (7, 12), (8, 12)]
    return put(g, mark, "#")


OCTAGON = {
    1: (5, 10), 2: (4, 11), 3: (3, 12), 4: (2, 13),
    5: (1, 14), 6: (1, 14), 7: (1, 14), 8: (1, 14), 9: (1, 14), 10: (1, 14),
    11: (2, 13), 12: (3, 12), 13: (4, 11), 14: (5, 10),
}

CIRCLE14 = {
    1: (5, 10), 2: (3, 12), 3: (2, 13), 4: (2, 13),
    5: (1, 14), 6: (1, 14), 7: (1, 14), 8: (1, 14), 9: (1, 14), 10: (1, 14),
    11: (2, 13), 12: (2, 13), 13: (3, 12), 14: (5, 10),
}


def span_mask(spans: dict[int, tuple[int, int]]) -> set:
    return {(x, y) for y, (a, b) in spans.items() for x in range(a, b + 1)}


def error() -> list[str]:
    g = outlined(span_mask(OCTAGON), "r")
    x = []
    for i in range(6):
        x += [(5 + i, 5 + i), (10 - i, 5 + i)]
    return put(g, x, "w")


def info() -> list[str]:
    g = outlined(span_mask(CIRCLE14), "d")
    mark = [(7, 4), (8, 4)] + [(x, y) for x in (7, 8) for y in range(6, 11)] + [(6, 6), (6, 11), (7, 11), (8, 11), (9, 11)]
    return put(g, mark, "w")


AGENT = shift(grid([
    "................",
    ".......vv.......",
    ".......##.......",
    "...##########...",
    "..#pppppppppp#..",
    "..#p########p#..",
    ".##p#vwvvwv#p##.",
    ".##p#vwvvwv#p##.",
    "..#p########p#..",
    "..#pppppppppp#..",
    "..#ppp####ppp#..",
    "..#pppppppppp#..",
    "...##########...",
    "................",
    "................",
    "................",
]), 0, 1)

HUMAN = shift(grid([
    "................",
    "......####......",
    ".....#ssss#.....",
    "....#ssssss#....",
    "....#ssssss#....",
    "....#ssssss#....",
    ".....#ssss#.....",
    "......####......",
    "................",
    "....########....",
    "...#ssssssss#...",
    "..#ssssssssss#..",
    "..#ssssssssss#..",
    "..############..",
    "................",
    "................",
]), 0, 1)

DIFF = grid([
    "................",
    "................",
    ".##############.",
    ".#sssss##ccccc#.",
    ".#sssss##ccccc#.",
    ".#sssss##ccccc#.",
    ".#ssss####cccc#.",
    ".#ssss#ww#cccc#.",
    ".#ssss#ww#cccc#.",
    ".#ssss####cccc#.",
    ".#sssss##ccccc#.",
    ".#sssss##ccccc#.",
    ".#sssss##ccccc#.",
    ".##############.",
    "................",
    "................",
])

SOURCES = grid([
    "................",
    "..########......",
    "..#wwwwww##.....",
    "..#wwwwww#s#....",
    "..#wwwwww#ss#...",
    "..#wwwwww#####..",
    "..#wwwwwwwwww#..",
    "..#wwwwwwwggw#..",
    "..#wwwwwwwggw#..",
    "..#wwwdwwwwww#..",
    "..#wwdddwwcww#..",
    "..#wdddddcccw#..",
    "..#ddddddddcc#..",
    "..############..",
    "................",
    "................",
])

VALIDATE_OK = grid([
    "................",
    "................",
    "....#########...",
    "...#cccccccc#...",
    ".###cccccccc###.",
    "...#cccccccc#...",
    ".###cccccc#c###.",
    "...#cccccc##c#..",
    "...#c#ccc##cc#..",
    ".###c##c##cc###.",
    "...#cc###ccc#...",
    ".###ccc#cccc###.",
    "...#cccccccc#...",
    "...##########...",
    "................",
    "................",
])

TAG = grid([
    "................",
    "................",
    "................",
    ".....##########.",
    "....#ccccccccc#.",
    "...#cc##cccccc#.",
    "..#cc#..#ccccc#.",
    ".#ccc#..#ccccc#.",
    ".#ccc#..#ccccc#.",
    "..#ccc##cccccc#.",
    "...#ccccccccc#..",
    "....#ccccccccc#.",
    ".....##########.",
    "................",
    "................",
    "................",
])

LAYER = grid([
    "................",
    ".......##.......",
    ".....##cc##.....",
    "...##cccccc##...",
    ".##cccccccccc##.",
    "...##cccccc##...",
    ".#...##cc##...#.",
    "..##...##...##..",
    "....##....##....",
    ".#....####....#.",
    "..##........##..",
    "....##....##....",
    "......####......",
    "................",
    "................",
    "................",
])

FOLDER = grid([
    "................",
    "................",
    ".######.........",
    ".#cccc#.........",
    ".#cccc########..",
    ".#ssssssssssss#.",
    ".##############.",
    ".#cccccccccccc#.",
    ".#cccccccccccc#.",
    ".#cccccccccccc#.",
    ".#cccccccccccc#.",
    ".#cccccccccccc#.",
    ".#cccccccccccc#.",
    ".##############.",
    "................",
    "................",
])


def tile() -> list[str]:
    return merge(
        outlined(rect_mask(1, 1, 6, 6), "c"),
        outlined(rect_mask(9, 1, 14, 6), "s"),
        outlined(rect_mask(1, 9, 6, 14), "s"),
        outlined(rect_mask(9, 9, 14, 14), "c"),
    )


# ---------------------------------------------------- revised (code-built)

TRI_45 = [1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1]  # 45-degree triangle, 11 tall, 6 wide


def step_next() -> list[str]:  # noqa: F811 - revised design
    bar = put(to_rows(blank()), [(x, y) for x in (11, 12) for y in range(3, 14)], "#")
    return merge(outlined(tri_mask(4, 1, 3, TRI_45), "c"), bar)


def step_prev() -> list[str]:  # noqa: F811
    return mirror(step_next())


def last() -> list[str]:  # noqa: F811
    bar = put(to_rows(blank()), [(x, y) for x in (13, 14) for y in range(3, 14)], "#")
    return merge(
        outlined(tri_mask(1, 1, 3, TRI_45), "c"),
        outlined(tri_mask(6, 1, 3, TRI_45), "c"),
        bar,
    )


def first() -> list[str]:  # noqa: F811
    return mirror(last())


DIAMOND = [(7, 8), (5, 10), (3, 12), (1, 14), (3, 12), (5, 10), (7, 8)]


def layer() -> list[str]:
    out = to_rows(blank())
    # two plates, 4 rows apart, so the lower plate shows as a clean chevron band
    for k, fill in ((1, "s"), (0, "c")):
        m = set()
        for t, (a, b) in enumerate(DIAMOND):
            for x in range(a, b + 1):
                m.add((x, 3 + 4 * k + t))
        g = blank()
        for x, y in m:
            # edge = the two outermost pixels of each row (keeps the 2:1 slope 1px thick)
            a, b = DIAMOND[y - 3 - 4 * k]
            g[y][x] = "#" if (x <= a + 1 or x >= b - 1) else fill
        out = merge(out, to_rows(g))
    return out


def validate_ok() -> list[str]:
    body = {(x, y) for x in range(3, 13) for y in range(2, 14)} - {(3, 2)}  # notched IC
    g = outlined(body, "c")
    legs = [(x, y) for y in (4, 6, 9, 11) for x in (1, 2, 13, 14)]
    g = put(g, legs, "#")
    check = [(5, 7), (6, 8), (7, 9), (8, 8), (9, 7), (10, 6)]
    check += [(x, y + 1) for x, y in check]
    return put(g, check, "#")


def tag() -> list[str]:
    spans = {3: (5, 14), 4: (4, 14), 5: (3, 14), 6: (2, 14), 7: (1, 14), 8: (1, 14),
             9: (2, 14), 10: (3, 14), 11: (4, 14), 12: (5, 14)}
    m = span_mask(spans) - {(5, 7), (6, 7), (5, 8), (6, 8)}
    g = outlined(m, "c")
    # outlined() already rings the hole; tidy the hole corners to read as a round eyelet
    return put(g, [(4, 6), (7, 6), (4, 9), (7, 9)], "c")


def link() -> list[str]:
    a = outlined(span_mask({4: (2, 8), 5: (1, 9), 6: (1, 9), 7: (1, 9), 8: (1, 9), 9: (2, 8)}), ".")
    b = outlined(span_mask({7: (7, 13), 8: (6, 14), 9: (6, 14), 10: (6, 14), 11: (6, 14), 12: (7, 13)}), ".")
    g = merge(a, b)
    # weave: ring A passes over ring B at the top-right crossing, under it at the bottom-left
    g = put(g, [(8, 7), (10, 7)], ".")
    g = put(g, [(9, 7)], "#")
    g = put(g, [(5, 9), (7, 9)], ".")
    return put(g, [(6, 9)], "#")


def all_icons() -> dict[str, list[str]]:
    icons = {
        # tool bar (SPEC 14.2)
        "pencil": PENCIL,
        "eraser": ERASER,
        "line": LINE,
        "rect": RECT,
        "ellipse": ELLIPSE,
        "fill": FILL,
        "eyedropper": EYEDROPPER,
        "select-rect": select_rect(),
        "move": MOVE,
        "hand": HAND,
        "zoom": ZOOM,
        # timeline
        "eye": EYE,
        "eye-off": EYE_OFF,
        "lock": LOCK,
        "unlock": UNLOCK,
        "link": link(),
        "play": play(),
        "pause": pause(),
        "step-prev": step_prev(),
        "step-next": step_next(),
        "first": first(),
        "last": last(),
        "onion": onion(),
        "grid": grid_icon(),
        # commands
        "undo": UNDO,
        "redo": redo(),
        "add": add(),
        "remove": remove(),
        # status and agent panel
        "warning": warning(),
        "error": error(),
        "info": info(),
        "agent": AGENT,
        "human": HUMAN,
        "diff": DIFF,
        "sources": SOURCES,
        "validate-ok": validate_ok(),
        # structure
        "tag": tag(),
        "layer": layer(),
        "folder": FOLDER,
        "tile": tile(),
    }
    for name, rows in icons.items():
        grid(rows)
    return icons


if __name__ == "__main__":
    d = all_icons()
    names = list(d)
    for i in range(0, len(names), 8):
        grp = names[i:i + 8]
        print("  ".join(n[:16].ljust(16) for n in grp))
        for y in range(16):
            print("  ".join(d[n][y] for n in grp))
        print()
