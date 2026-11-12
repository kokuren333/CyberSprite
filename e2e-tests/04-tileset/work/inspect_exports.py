"""Inspect exported files independently of CyberSprite's renderer (read-only)."""
import json
import sys
from pathlib import Path

from PIL import Image

root = Path(sys.argv[1])
proj = json.loads((root / "meadow.csprite" / "project.json").read_text(encoding="utf-8"))
pal = [tuple(int(c[i:i + 2], 16) for i in (1, 3, 5, 7)) for c in proj["palette"]["colors"]]
ti = proj["palette"]["transparent_index"]
ts = proj["tilesets"][0]
TW, TH = ts["tile_w"], ts["tile_h"]


def dec(rows):
    return [[int(r[i:i + 2], 16) for i in range(0, len(r), 2)] for r in rows]


tiles = [dec(t["pixels"]) for t in ts["tiles"]]


def orient(t, flags):  # d (transpose) -> x -> y   (SPEC 6.5.4)
    if "d" in flags:
        t = [list(r) for r in zip(*t)]
    if "x" in flags:
        t = [r[::-1] for r in t]
    if "y" in flags:
        t = t[::-1]
    return t


W, H = proj["canvas"]["width"], proj["canvas"]["height"]
canvas = [[ti] * W for _ in range(H)]
for layer in proj["layers"]:  # bottom to top
    if layer["type"] != "tilemap" or not layer.get("visible", True):
        continue
    for cel in layer["cels"]:
        for r, line in enumerate(cel["tiles"]):
            for c, ref in enumerate(line.split()):
                n = int(ref.rstrip("xyd"))
                flags = ref[len(str(n)):]
                if n == 0:
                    continue
                t = orient(tiles[n], flags)
                for y in range(TH):
                    for x in range(TW):
                        if t[y][x] != ti:
                            canvas[cel["y"] + r * TH + y][cel["x"] + c * TW + x] = t[y][x]

ok = True
# 1) map x1 PNG vs my own composition
im = Image.open(root / "export/meadow_x1.png")
print("x1 mode", im.mode, im.size, "palette entries", len(im.getpalette()) // 3 if im.getpalette() else None)
rgba = im.convert("RGBA")
bad = sum(1 for y in range(H) for x in range(W) if rgba.getpixel((x, y)) != (pal[canvas[y][x]] if canvas[y][x] != ti else (0, 0, 0, 0)))
print("x1 mismatches vs independent tile composition:", bad)
ok &= bad == 0
if im.mode == "P":
    idx_bad = sum(1 for y in range(H) for x in range(W) if im.getpixel((x, y)) != canvas[y][x])
    print("x1 index mismatches:", idx_bad)
    ok &= idx_bad == 0

# 2) x3 == nearest upscale of x1
im3 = Image.open(root / "export/meadow_x3.png").convert("RGBA")
up = rgba.resize((W * 3, H * 3), Image.NEAREST)
d3 = sum(1 for p, q in zip(im3.getdata(), up.getdata()) if p != q)
print("x3 size", im3.size, "mismatches vs nearest x3 of x1:", d3)
ok &= d3 == 0

# 3) tileset PNG rects vs tile data
data = json.loads((root / "export/meadow_tileset.json").read_text(encoding="utf-8"))
sheet = Image.open(root / "export/meadow_tileset.png")
print("tileset png", sheet.mode, sheet.size, "image field", data["image"])
srgba = sheet.convert("RGBA")
for t in data["tiles"]:
    rc = t["rect"]
    tt = tiles[t["index"]]
    mism = sum(1 for y in range(rc["h"]) for x in range(rc["w"])
               if srgba.getpixel((rc["x"] + x, rc["y"] + y)) != (pal[tt[y][x]] if tt[y][x] != ti else (0, 0, 0, 0)))
    if mism:
        print("  tile", t["index"], "mismatch", mism)
        ok = False
print("tileset rects checked:", len(data["tiles"]), "indices", [t["index"] for t in data["tiles"]])
# x3 tileset == nearest x3 of x1 sheet
s3 = Image.open(root / "export/meadow_tileset_x3.png").convert("RGBA")
print("tileset x3 equal:", list(s3.getdata()) == list(srgba.resize((srgba.width * 3, srgba.height * 3), Image.NEAREST).getdata()))

# 4) count flips used
from collections import Counter
cnt = Counter()
for layer in proj["layers"]:
    if layer["type"] == "tilemap":
        for cel in layer["cels"]:
            for line in cel["tiles"]:
                for ref in line.split():
                    n = int(ref.rstrip("xyd"))
                    if n:
                        cnt[ref[len(str(n)):] or "-"] += 1
print("flip usage:", dict(cnt))
print("ALL OK" if ok else "PROBLEMS")
