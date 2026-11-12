"""Compute tile references for the 12x8 meadow map from a 13x9 vertex terrain grid.

Only produces op arguments (set_tiles rows). Tile indices match the order in gen_tiles.py.
"""
import json
import sys

V = [  # vertex materials: . grass, p path, w water
    ".......wwwwww",
    "......wwwwwww",
    "......wwwwwww",
    "........wwwww",
    ".........wwww",
    "ppppp........",
    "ppppp........",
    "...pp........",
    "...pp........",
]
GRASS = [1, 2, 3]
SETS = {
    "p": {"center": [4, 5], "edge": 6, "outer": 7, "inner": 8},
    "w": {"center": [9, 10], "edge": 11, "outer": 12, "inner": 13},
}
EDGE = {(0, 0, 1, 1): "", (1, 1, 0, 0): "y", (0, 1, 0, 1): "d", (1, 0, 1, 0): "xd"}
OUTER = {(0, 0, 0, 1): "", (0, 0, 1, 0): "x", (0, 1, 0, 0): "y", (1, 0, 0, 0): "xy"}
INNER = {(0, 1, 1, 1): "", (1, 0, 1, 1): "x", (1, 1, 0, 1): "y", (1, 1, 1, 0): "xy"}


def pick(choices, c, r):
    # deterministic, irregular variation; first choice dominates
    h = (c * 7 + r * 13 + c * r * 3) % 10
    if len(choices) == 3:
        return choices[0] if h < 6 else (choices[1] if h < 9 else choices[2])
    return choices[0] if h < 7 else choices[1]


def tile_ref(c, r):
    corners = [V[r][c], V[r][c + 1], V[r + 1][c], V[r + 1][c + 1]]
    mats = set(corners) - {"."}
    if not mats:
        return str(pick(GRASS, c, r))
    assert len(mats) == 1, (c, r, corners)
    m = mats.pop()
    bits = tuple(1 if k == m else 0 for k in corners)
    s = SETS[m]
    n = sum(bits)
    if n == 4:
        return str(pick(s["center"], c, r))
    if n == 2:
        return f"{s['edge']}{EDGE[bits]}"
    if n == 1:
        return f"{s['outer']}{OUTER[bits]}"
    return f"{s['inner']}{INNER[bits]}"


ground = [" ".join(tile_ref(c, r) for c in range(12)) for r in range(8)]

if __name__ == "__main__":
    json.dump(ground, sys.stdout, indent=1)
