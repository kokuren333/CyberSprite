# Light-side outer contour: reads the project's own layers through the CLI (read-only) and writes a transaction
# that recolours outline pixels on the OUTER silhouette to @line where they face right or down (away from the
# upper-left light). Lit-facing outer edges keep the material's darkest colour. Pixels are written only via Ops.
# usage: python tx/contour_pass.py <project> <frame> <out.json>
import json, subprocess, sys

proj, frame, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
LAYERS = ["tail", "frond", "legs", "torso", "arms", "collar", "fern", "head", "face"]  # bottom -> top
OUTLINE_IDX = {2, 7, 11}  # plum0, leaf0, belly0 (the selective outline colours)
LINE = 1
W = H = 80


def layer_px(name):
    r = subprocess.run(["uv", "run", "--project", "../..", "--no-sync", "cybersprite", "-p", proj, "pixels", "--layer", name,
                        "--frame", str(frame), "--rect", "0,0,80,80", "--as", "sym"], capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)["result"]
    inv = {k: v for k, v in d["legend"].items()}
    return [[inv[ch] for ch in row] for row in d["rows"]]


grids = {n: layer_px(n) for n in LAYERS}
owner = [[None] * W for _ in range(H)]
for n in LAYERS:
    g = grids[n]
    for y in range(H):
        for x in range(W):
            if g[y][x] != 0:
                owner[y][x] = n


def opaque(x, y):
    return 0 <= x < W and 0 <= y < H and owner[y][x] is not None


per_layer = {}
contour = dark = 0
for y in range(H):
    for x in range(W):
        if not opaque(x, y):
            continue
        right_down = (not opaque(x + 1, y)) or (not opaque(x, y + 1))
        up_left = (not opaque(x - 1, y)) or (not opaque(x, y - 1))
        if not (right_down or up_left):
            continue
        contour += 1
        n = owner[y][x]
        idx = grids[n][y][x]
        if right_down and idx in OUTLINE_IDX:
            per_layer.setdefault(n, []).append([x, y, LINE])
            dark += 1
        elif idx == LINE:
            dark += 1
ops = [{"op": "set_pixels", "args": {"layer": n, "frame": frame, "pixels": px}} for n, px in per_layer.items()]
json.dump({"label": f"outer contour f{frame}: near-black on edges facing away from the light", "ops": ops}, open(out, "w"))
print(f"contour px={contour} near-black after pass={dark} share={dark / contour:.2f}")
