"""Generate op arguments (sym rows) for the meadow tileset.

This script only produces JSON op arguments; every pixel is written by CyberSprite ops.
Palette symbols: . transparent, 1 outline, 2-5 grass (dark..highlight), 6-9 dirt (dark..sand),
a-d water (deep..foam), e-g rock, h red, i yellow, j white, k bush darkest, l violet.
"""
import json
import math
import sys

N = 16


def blank(c="."):
    return [[c] * N for _ in range(N)]


def rows(g):
    out = ["".join(r) for r in g]
    assert len(out) == N and all(len(r) == N for r in out), out
    return out


def stamp(g, x, y, art, transparent=" "):
    for j, line in enumerate(art):
        for i, ch in enumerate(line):
            if ch != transparent:
                g[y + j][x + i] = ch


# ---------------------------------------------------------------- textures
TUFT = ["4 4", "242"]
TUFT_S = ["4", "2"]


def grass(variant):
    g = blank("3")
    if variant == 0:
        stamp(g, 3, 3, TUFT)
        stamp(g, 10, 9, TUFT)
        stamp(g, 12, 2, TUFT_S)
        stamp(g, 5, 11, TUFT_S)
        g[7][8] = "2"
        g[13][12] = "2"
    elif variant == 1:
        stamp(g, 2, 2, TUFT)
        stamp(g, 9, 4, TUFT)
        stamp(g, 4, 9, TUFT)
        stamp(g, 11, 11, TUFT)
        stamp(g, 7, 13, TUFT_S)
        stamp(g, 13, 7, TUFT_S)
        g[6][6] = "2"
        g[12][2] = "2"
    else:  # tiny flowers
        stamp(g, 3, 9, TUFT)
        stamp(g, 10, 3, TUFT_S)
        for (x, y, c) in [(4, 3, "j"), (11, 10, "i"), (8, 6, "j"), (12, 13, "5"), (2, 13, "5")]:
            g[y][x] = c
        g[4][4] = "4"
        g[11][11] = "4"
        g[7][8] = "4"
    return g


def grass_px(x, y, variant=0):
    return grass(variant)[y][x]


def dirt(variant):
    g = blank("8")
    pebbles = [(3, 4), (11, 2), (8, 9), (2, 12), (12, 12)] if variant == 0 else [(5, 3), (10, 7), (3, 10), (12, 13)]
    for (x, y) in pebbles:
        g[y][x] = "9"
        g[y + 1][x] = "7"
    specks = [(6, 6), (13, 6), (5, 13)] if variant == 0 else [(2, 2), (8, 12), (13, 2), (7, 7)]
    for (x, y) in specks:
        g[y][x] = "7"
    if variant == 1:
        # a few lighter sand streaks
        for x in (6, 7, 8):
            g[10][x] = "9"
        g[11][9] = "7"
    return g


def water(variant):
    g = blank("b")
    if variant == 0:
        deep = [(3, 5, 4), (4, 6, 2), (10, 11, 3), (11, 12, 2)]
        glints = [(9, 2), (4, 9), (12, 7)]
    else:
        deep = [(8, 4, 3), (9, 5, 2), (2, 11, 4), (3, 12, 2)]
        glints = [(4, 2), (11, 9), (7, 13)]
    for (x, y, n) in deep:
        for i in range(n):
            g[y][x + i] = "a"
    for (x, y) in glints:
        g[y][x - 1] = "c"
        g[y][x] = "d"
        g[y][x + 1] = "c"
        g[y + 1][x - 2] = "c"
        g[y + 1][x + 2] = "c"
    return g


# ---------------------------------------------------------------- transition tiles
def edge_s(profile):
    return lambda x, y: y - profile[x]


def outer_s(D, r):
    c = D + r

    def s(x, y):
        if x < c and y < c:
            return r - int(round(math.hypot(c - x, c - y)))
        return min(x - D, y - D)

    return s


def inner_s(D):
    def s(x, y):
        return int(round(math.hypot(x, y))) - D

    return s


def path_tile(sfun, base_variant=0):
    gr = grass(0)
    dr = dirt(0)
    g = blank()
    for y in range(N):
        for x in range(N):
            s = sfun(x, y)
            if s <= -2:
                c = "3"
                # keep grass texture only well inside the grass area
                if sfun(x, y) <= -3 and 1 <= x <= 14 and 1 <= y <= 14:
                    c = gr[y][x]
            elif s == -1:
                c = "4"
            elif s == 0:
                c = "2"
            elif s == 1:
                c = "6"
            elif s == 2:
                c = "7"
            else:
                c = "8"
                if s >= 3 and 1 <= x <= 14 and 1 <= y <= 14:
                    c = dr[y][x]
            g[y][x] = c
    return g


def shore_tile(sfun):
    gr = grass(1)
    wt = water(0)
    g = blank()
    for y in range(N):
        for x in range(N):
            s = sfun(x, y)
            if s <= -2:
                c = "3"
                if s <= -3 and 1 <= x <= 14 and 1 <= y <= 14:
                    c = gr[y][x]
            elif s == -1:
                c = "2"
            elif s == 0:
                c = "9"
            elif s == 1:
                c = "8"
            elif s == 2:
                c = "d"
            elif s == 3:
                c = "c"
            else:
                c = "b"
            g[y][x] = c
    # stamp only whole water features (8-connected components) lying fully in open water
    seen = set()
    for y in range(N):
        for x in range(N):
            if wt[y][x] == "b" or (x, y) in seen:
                continue
            comp, stack = [], [(x, y)]
            seen.add((x, y))
            while stack:
                px, py = stack.pop()
                comp.append((px, py))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        q = (px + dx, py + dy)
                        if 0 <= q[0] < N and 0 <= q[1] < N and q not in seen and wt[q[1]][q[0]] != "b":
                            seen.add(q)
                            stack.append(q)
            if all(sfun(px, py) >= 5 for px, py in comp):
                for px, py in comp:
                    g[py][px] = wt[py][px]
    return g


PATH_PROFILE = [5, 5, 6, 6, 5, 4, 4, 5, 5, 4, 4, 5, 6, 6, 5, 5]
SHORE_PROFILE = [3, 3, 4, 4, 4, 3, 2, 2, 2, 2, 3, 4, 4, 4, 3, 3]
for p in (PATH_PROFILE, SHORE_PROFILE):
    assert all(p[i] == p[N - 1 - i] for i in range(N))

# ---------------------------------------------------------------- props (transparent)
FLOWERS = [
    "................",
    "................",
    "...h........j...",
    "..hih......jij..",
    "...h.......2j...",
    "...2...l...2....",
    "..42..lil..24...",
    "...2...l2.......",
    "...2....2..i....",
    "....2..42.iii...",
    "....24.2...i2...",
    ".....2.2...2....",
    "...h..22..42....",
    "..hih..2..2.....",
    "...h2..2.2......",
    "....2...........",
]

ROCK = [
    "................",
    "................",
    "................",
    "................",
    "......eeee......",
    "....eefggfee....",
    "...efggggfffe...",
    "..efgggffffffe..",
    "..efggfffffffe..",
    ".efgffffffffeee.",
    ".effffffffeeeee.",
    ".eefffffeeeeee1.",
    ".1eeeeeeeeeee1..",
    "..1111111111122.",
    "...2222222222...",
    "................",
]

BUSH = [
    "................",
    "................",
    "......kkkk......",
    "....kk3443kk....",
    "...k33455432k...",
    "..k3345554432k..",
    "..k3344443332k..",
    ".k333443h33322k.",
    ".k23333332h322k.",
    ".k2233h3332222k.",
    ".kk2223332222kk.",
    "..kk22222222kk..",
    "...kkkkkkkkkk...",
    "...2222222222...",
    "................",
    "................",
]

TILES = [
    ("grass_a", grass(0)),
    ("grass_b", grass(1)),
    ("grass_flowers", grass(2)),
    ("dirt", dirt(0)),
    ("dirt_b", dirt(1)),
    ("path_edge", path_tile(edge_s(PATH_PROFILE))),
    ("path_outer", path_tile(outer_s(PATH_PROFILE[0], 4))),
    ("path_inner", path_tile(inner_s(PATH_PROFILE[0]))),
    ("water", water(0)),
    ("water_b", water(1)),
    ("shore_edge", shore_tile(edge_s(SHORE_PROFILE))),
    ("shore_outer", shore_tile(outer_s(SHORE_PROFILE[0], 3))),
    ("shore_inner", shore_tile(inner_s(SHORE_PROFILE[0]))),
    ("flowers", [list(r) for r in FLOWERS]),
    ("rock", [list(r) for r in ROCK]),
    ("bush", [list(r) for r in BUSH]),
]

if __name__ == "__main__":
    out = {name: rows(g) for name, g in TILES}
    json.dump(out, sys.stdout, indent=1)
