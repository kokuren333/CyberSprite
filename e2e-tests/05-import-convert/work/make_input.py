"""Scratch script: draws an original 32x32 slime (clean reference) and degrades it
like an image generator's 'pixel art style' output. Input creation only; the
CyberSprite canvas never receives pixels from this script."""
import random, sys
from PIL import Image, ImageFilter

out_dir = sys.argv[1]
K = (30, 43, 56); D = (47, 122, 60); G = (79, 179, 74); L = (143, 224, 104)
H = (232, 255, 208); W = (255, 255, 255); P = (240, 138, 154); S = (90, 97, 112)
rows = {6: (16, 17), 7: (15, 17), 8: (13, 18), 9: (11, 20), 10: (9, 22), 11: (8, 23), 12: (7, 24),
        13: (6, 25), 14: (6, 25), 15: (5, 26), 16: (5, 26), 17: (4, 27), 18: (4, 27), 19: (4, 27),
        20: (3, 28), 21: (3, 28), 22: (3, 28), 23: (3, 28), 24: (3, 28), 25: (4, 27), 26: (5, 26)}
mask = {(x, y) for y, (a, b) in rows.items() for x in range(a, b + 1)}
img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
px = img.load()
for y in (27, 28):
    a, b = (6, 25) if y == 27 else (9, 22)
    for x in range(a, b + 1):
        px[x, y] = S + (255,)
for (x, y) in mask:
    a, b = rows[y]
    edge = any((x + dx, y + dy) not in mask for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    if edge:
        c = K
    elif y >= 24 or x >= b - 2 or (y >= 22 and x >= b - 4):
        c = D
    elif (x - a) <= 3 and y <= 18 or y <= 10:
        c = L
    else:
        c = G
    px[x, y] = c + (255,)
for (x, y) in [(9, 12), (10, 12), (8, 13), (9, 13), (8, 14), (12, 10), (13, 10)]:
    px[x, y] = H + (255,)
for ex in (11, 19):
    for y in (16, 17, 18):
        for x in (ex, ex + 1):
            px[x, y] = K + (255,)
    px[ex, 16] = W + (255,)
for x in (15, 16):
    px[x, 21] = K + (255,)
px[14, 20] = K + (255,); px[17, 20] = K + (255,)
for x in (8, 9, 22, 23):
    px[x, 20] = P + (255,)
img.save(f"{out_dir}/slime_clean_32.png")

# --- degrade like a generator ---
rng = random.Random(20261112)
bg = (246, 244, 238)
flat = Image.new("RGB", (32, 32), bg)
flat.paste(img, (0, 0), img)
big = flat.resize((347, 347), Image.BICUBIC)
big = big.filter(ImageFilter.GaussianBlur(0.7))
bp = big.load()
# low-frequency hue drift (smooth, no fixed tile period) + per-pixel noise
import math
ph = [rng.random() * 6.28 for _ in range(6)]
for y in range(347):
    for x in range(347):
        r, g, b = bp[x, y]
        d = [round(6 * math.sin(x / 41 + ph[i]) * math.cos(y / 53 + ph[i + 3])) for i in range(3)]
        n = rng.randint(-4, 4)
        bp[x, y] = tuple(max(0, min(255, v + dd + n)) for v, dd in zip((r, g, b), d))
big.save(f"{out_dir}/slime_generated_like.jpg", quality=80)
