import random, sys, math
from PIL import Image, ImageFilter
src = Image.open("source_input/slime_clean_32.png")
bg = (246, 244, 238)
flat = Image.new("RGB", (32, 32), bg); flat.paste(src, (0, 0), src)
def make(size, drift_mode, q, name, blur=0.7):
    rng = random.Random(20261112)
    big = flat.resize((size, size), Image.BICUBIC).filter(ImageFilter.GaussianBlur(blur))
    bp = big.load()
    ph = [rng.random() * 6.28 for _ in range(6)]
    for y in range(size):
        for x in range(size):
            r, g, b = bp[x, y]
            if drift_mode == "smooth":  # low-frequency hue drift, no fixed tile period
                d = [round(6 * math.sin(x / 41 + ph[i]) * math.cos(y / 53 + ph[i + 3])) for i in range(3)]
            else:
                d = [0, 0, 0]
            n = rng.randint(-4, 4)
            bp[x, y] = tuple(max(0, min(255, v + dd + n)) for v, dd in zip((r, g, b), d))
    if q:
        big.save(name, quality=q)
    else:
        big.save(name)
make(347, "smooth", 80, "work/variant_smooth_q80.jpg")
make(347, "smooth", None, "work/variant_smooth_nojpeg.png")
make(347, "smooth", 95, "work/variant_smooth_q95.jpg")
