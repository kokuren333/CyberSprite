"""Calibration corpus, category (e): images that are NOT pixel art (SPEC §11.9).

All images are original procedural work of the CyberSprite project
(Apache-2.0).  These are test inputs, not pipeline code, so floating point
is allowed here; every random source uses a fixed seed.  The pipeline's
gates are expected to reject them (grid_detected / grid_score fail).

Run (from the repository root):

    python tests/pipeline/corpus/non_pixel/make_non_pixel.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent
SS = 4  # supersampling factor for anti-aliased drawings


def save(name, arr_or_img):
    img = arr_or_img if isinstance(arr_or_img, Image.Image) else Image.fromarray(arr_or_img)
    img.save(OUT / f"{name}.png", format="PNG", optimize=False)
    print(f"{name:32s} {img.width}x{img.height} {img.mode}")


def to_u8(a):
    return np.clip(np.rint(a), 0, 255).astype(np.uint8)


def downsample(img, w, h):
    return img.resize((w, h), Image.LANCZOS)


def value_noise(rng, w, h, cells):
    """Smooth value noise: random lattice, bicubic-smoothstep interpolation."""
    grid = rng.random((cells + 2, cells + 2))
    ys = np.linspace(0, cells, h, endpoint=False)
    xs = np.linspace(0, cells, w, endpoint=False)
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = ys - y0, xs - x0
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    a = grid[y0][:, x0]
    b = grid[y0][:, x0 + 1]
    c = grid[y0 + 1][:, x0]
    d = grid[y0 + 1][:, x0 + 1]
    top = a + (b - a) * fx[None, :]
    bot = c + (d - c) * fx[None, :]
    return top + (bot - top) * fy[:, None]


def fbm(rng, w, h, base=4, octaves=5):
    total = np.zeros((h, w))
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        total += amp * value_noise(rng, w, h, base * 2**o)
        norm += amp
        amp *= 0.5
    return total / norm


# 1. linear gradient --------------------------------------------------------
def gradient_linear():
    w, h = 256, 192
    x = np.linspace(0, 1, w)[None, :, None]
    y = np.linspace(0, 1, h)[:, None, None]
    c0 = np.array([22, 40, 92.0])
    c1 = np.array([238, 120, 86.0])
    c2 = np.array([250, 226, 160.0])
    t = x * 0.8 + y * 0.2
    rgb = np.where(t < 0.5, c0 + (c1 - c0) * (t / 0.5), c1 + (c2 - c1) * ((t - 0.5) / 0.5))
    save("gradient_linear_256x192", to_u8(rgb))


# 2. radial gradient with alpha falloff (RGBA) --------------------------------
def gradient_radial_alpha():
    w, h = 320, 240
    y, x = np.mgrid[0:h, 0:w]
    r = np.hypot((x - w * 0.45) / (w * 0.5), (y - h * 0.5) / (h * 0.5))
    rgb = np.stack([255 - 120 * r, 200 - 90 * r, 120 + 100 * r], axis=-1)
    alpha = 255 * np.clip(1.2 - r, 0, 1)
    save("gradient_radial_alpha_320x240", to_u8(np.dstack([rgb, alpha])))


# 3. anti-aliased concentric circles -------------------------------------------
def aa_circles():
    n = 256
    big = Image.new("RGB", (n * SS, n * SS), (246, 241, 228))
    d = ImageDraw.Draw(big)
    cols = [(32, 60, 110), (220, 90, 70), (60, 150, 120), (240, 190, 60)]
    for i in range(12):
        r = (n * SS // 2) - i * 40 - 20
        d.ellipse(
            [n * SS // 2 - r, n * SS // 2 - r, n * SS // 2 + r, n * SS // 2 + r],
            outline=cols[i % 4],
            width=14,
        )
    save("aa_circles_256", downsample(big, n, n))


# 4. flat vector-style illustration ----------------------------------------------
def aa_vector_scene():
    w, h = 384, 256
    big = Image.new("RGB", (w * SS, h * SS), (250, 214, 160))
    d = ImageDraw.Draw(big)
    S = SS
    d.ellipse([250 * S, 30 * S, 330 * S, 110 * S], fill=(255, 140, 80))
    d.polygon(
        [
            (0, 190 * S),
            (90 * S, 100 * S),
            (170 * S, 170 * S),
            (260 * S, 80 * S),
            (384 * S, 180 * S),
            (384 * S, 256 * S),
            (0, 256 * S),
        ],
        fill=(110, 70, 120),
    )
    d.ellipse([-80 * S, 170 * S, 260 * S, 360 * S], fill=(60, 120, 100))
    d.ellipse([150 * S, 190 * S, 480 * S, 380 * S], fill=(40, 90, 80))
    for i, x in enumerate((60, 95, 300, 335)):
        top = 150 + (i % 2) * 14
        d.polygon(
            [(x * S, top * S), ((x - 16) * S, (top + 50) * S), ((x + 16) * S, (top + 50) * S)],
            fill=(25, 60, 55),
        )
    d.arc([40 * S, 40 * S, 120 * S, 90 * S], 200, 340, fill=(80, 60, 90), width=3 * S)
    d.arc([110 * S, 55 * S, 170 * S, 95 * S], 200, 340, fill=(80, 60, 90), width=3 * S)
    save("aa_vector_scene_384x256", downsample(big, w, h))


# 5. smooth value noise (fbm) -------------------------------------------------
def noise_fbm():
    rng = np.random.default_rng(1001)
    n = fbm(rng, 256, 256)
    rgb = np.stack([60 + 150 * n, 90 + 120 * n, 140 + 90 * n], axis=-1)
    save("noise_fbm_256", to_u8(rgb))


# 6. white noise (worst case: every pixel independent) --------------------------
def noise_white():
    rng = np.random.default_rng(1002)
    save("noise_white_128", rng.integers(0, 256, size=(128, 128, 3), dtype=np.uint8))


# 7. photo-like procedural landscape ---------------------------------------------
def landscape():
    w, h = 512, 320
    rng = np.random.default_rng(1003)
    y = np.linspace(0, 1, h)[:, None]
    sky = np.stack(
        [
            np.broadcast_to(90 + 140 * y, (h, w)),
            np.broadcast_to(140 + 80 * y, (h, w)),
            np.broadcast_to(220 - 10 * y, (h, w)),
        ],
        axis=-1,
    ).astype(float)
    clouds = fbm(rng, w, h, base=3, octaves=6)
    sky += (np.clip(clouds - 0.5, 0, 1) * 300)[..., None] * (1 - y[..., None])
    img = sky
    for layer, (base, amp, col) in enumerate(
        [(0.45, 0.18, (120, 130, 160)), (0.58, 0.14, (70, 95, 90)), (0.72, 0.10, (45, 70, 45))]
    ):
        ridge = fbm(rng, w, 1, base=4 + layer * 2, octaves=6)[0]
        top = (base + amp * (ridge - 0.5) * 2) * h
        mask = (np.arange(h)[:, None] >= top[None, :]).astype(float)
        tex = fbm(rng, w, h, base=16, octaves=4)
        shade = np.array(col, float)[None, None, :] * (0.75 + 0.5 * tex[..., None])
        img = img * (1 - mask[..., None]) + shade * mask[..., None]
    img += rng.normal(0, 4.0, img.shape)  # sensor grain
    pil = Image.fromarray(to_u8(img)).filter(ImageFilter.GaussianBlur(0.8))
    save("landscape_photo_512x320", pil)


# 8. soft-shaded sphere -------------------------------------------------------------
def soft_sphere():
    n = 256 * SS
    y, x = np.mgrid[0:n, 0:n]
    cx = cy = n / 2
    rad = n * 0.38
    dx, dy = (x - cx) / rad, (y - cy) / rad
    rr = dx * dx + dy * dy
    inside = rr <= 1
    dz = np.sqrt(np.clip(1 - rr, 0, 1))
    light = np.array([-0.5, -0.6, 0.62])
    light /= np.linalg.norm(light)
    lam = np.clip(dx * light[0] + dy * light[1] + dz * light[2], 0, 1)
    spec = lam**40
    base = np.array([200, 70, 90.0])
    col = base[None, None, :] * (0.15 + 0.85 * lam[..., None]) + 255 * spec[..., None] * 0.8
    bg = np.array([228, 232, 240.0])
    shadow = np.exp(-(((x - cx * 1.08) / (rad * 1.1)) ** 2 + ((y - cy * 1.75) / (rad * 0.25)) ** 2))
    bgimg = bg[None, None, :] * (1 - 0.35 * shadow[..., None])
    out = np.where(inside[..., None], col, bgimg)
    save("sphere_soft_256", downsample(Image.fromarray(to_u8(out)), 256, 256))


# 9. anti-aliased text with Pillow's default font ------------------------------------
def aa_text():
    w, h = 384, 128
    img = Image.new("RGB", (w, h), (24, 26, 36))
    d = ImageDraw.Draw(img)
    font_big = ImageFont.load_default(size=44)
    font_small = ImageFont.load_default(size=18)
    d.text((16, 14), "Calibration", font=font_big, fill=(240, 236, 220))
    d.text(
        (18, 76), "not pixel art: smooth anti-aliased glyphs", font=font_small, fill=(150, 200, 230)
    )
    save("text_aa_384x128", img)


# 10. blurred shapes (bokeh-like) ---------------------------------------------------------
def blurred_shapes():
    n = 256
    rng = np.random.default_rng(1004)
    img = Image.new("RGB", (n, n), (30, 34, 50))
    d = ImageDraw.Draw(img)
    for _ in range(40):
        x, y = rng.integers(0, n, 2)
        r = int(rng.integers(6, 30))
        c = tuple(int(v) for v in rng.integers(80, 255, 3))
        d.ellipse([int(x) - r, int(y) - r, int(x) + r, int(y) + r], fill=c)
    save("bokeh_blur_256", img.filter(ImageFilter.GaussianBlur(6)))


# 11. rotated anti-aliased checkerboard (strong but non-axis-aligned periodicity) -------
def rotated_checker():
    n = 256 * SS
    y, x = np.mgrid[0:n, 0:n].astype(float)
    a = np.deg2rad(17)
    u = (x * np.cos(a) + y * np.sin(a)) / (14 * SS)
    v = (-x * np.sin(a) + y * np.cos(a)) / (14 * SS)
    chk = ((np.floor(u) + np.floor(v)) % 2)[..., None]
    out = np.array([235, 225, 200.0]) * chk + np.array([50, 60, 90.0]) * (1 - chk)
    save("checker_rotated_aa_256", downsample(Image.fromarray(to_u8(out)), 256, 256))


# 12. painterly brush strokes -------------------------------------------------------------
def brush_strokes():
    w, h = 320, 320
    rng = np.random.default_rng(1005)
    big = Image.new("RGB", (w * 2, h * 2), (236, 228, 210))
    d = ImageDraw.Draw(big)
    for _ in range(140):
        x0, y0 = rng.integers(0, w * 2, 2)
        ang = rng.random() * np.pi
        ln = rng.integers(20, 120)
        x1, y1 = x0 + ln * np.cos(ang), y0 + ln * np.sin(ang)
        c = tuple(
            int(v) for v in (rng.integers(40, 220), rng.integers(60, 200), rng.integers(80, 230))
        )
        d.line([(int(x0), int(y0)), (int(x1), int(y1))], fill=c, width=int(rng.integers(4, 18)))
    img = big.filter(ImageFilter.GaussianBlur(1.5))
    save("brush_strokes_320", downsample(img, w, h))


def main():
    for fn in (
        gradient_linear,
        gradient_radial_alpha,
        aa_circles,
        aa_vector_scene,
        noise_fbm,
        noise_white,
        landscape,
        soft_sphere,
        aa_text,
        blurred_shapes,
        rotated_checker,
        brush_strokes,
    ):
        fn()
    return 0


if __name__ == "__main__":
    sys.exit(main())
