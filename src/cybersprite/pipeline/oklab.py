"""Appendix B integer colour science. Safe to import without Pillow or core.

Coefficients: Bjorn Ottosson's Oklab, reproduced from docs/SPEC.md Appendix B.
All normative bytes are verified on load, including when loaded from a wheel.
"""

import hashlib
import json
from importlib.resources import files

import numpy as np

from ._common import integer, require

TABLE_SHA256 = {
    "srgb_lin16_v1.json": "16f0d68ce1b921100d4528beeee0912f570adc0223fdf152253b236252368199",
    "m1i_v1.json": "cb89a0f0c2af59a82da5d3c289d124da8d23ae22e5558cebb8ae43595b548075",
    "m2i_v1.json": "d2eadda0c72323cbd65f4978b57a93198a191f7e3d2fa615e32b934e0cc29c94",
    "bayer_v1.json": "819093e2e6a0173e9c5b2957f4985e36a75fcf102f8305a56e2fd94ffc889c05",
}


def load_table(name):
    data = files("cybersprite").joinpath("data", "color", name).read_bytes()
    if hashlib.sha256(data).hexdigest() != TABLE_SHA256[name]:
        raise ValueError(f"Normative colour table checksum mismatch: {name}; reinstall trusted data.")
    return json.loads(data)


LIN = tuple(load_table("srgb_lin16_v1.json"))
M1I = tuple(tuple(row) for row in load_table("m1i_v1.json"))
M2I = tuple(tuple(row) for row in load_table("m2i_v1.json"))


def icbrt(n):
    """Return the exact floor cube root of any nonnegative Python integer."""
    n = integer(n, "cube-root input", 0)
    if n == 0:
        return 0
    x = 1 << ((n.bit_length() + 2) // 3)
    while True:
        y = (2 * x + n // (x * x)) // 3
        if y >= x:
            return x
        x = y


def rgb_to_oklab_fixed(rgb):
    require(len(rgb) == 3, "RGB must contain exactly three channels.")
    rgb = [integer(v, "RGB channel", 0, 255) for v in rgb]
    roots = [icbrt(sum(row[i] * LIN[rgb[i]] for i in range(3)) << 16) for row in M1I]
    return tuple((sum(row[i] * roots[i] for i in range(3)) + 32768) >> 16 for row in M2I)


def rgb_to_oklab_fixed_numpy(rgb):
    """Convert an integer array of shape (..., 3) to int64 (..., 3)."""
    rgb = np.asarray(rgb)
    require(rgb.ndim >= 1 and rgb.shape[-1] == 3 and rgb.dtype.kind in "iu",
            "RGB array must have integer channels and shape (..., 3).")
    require(bool(np.all((rgb >= 0) & (rgb <= 255))), "RGB channels must be in 0..255.")
    linear = np.asarray(LIN, dtype=np.int64)[rgb.astype(np.int64)]
    n = (linear @ np.asarray(M1I, dtype=np.int64).T) << 16
    lo, hi = np.zeros_like(n), np.full_like(n, 65537)
    for _ in range(17):
        mid = (lo + hi) // 2
        below = mid * mid * mid <= n
        lo = np.where(below, mid, lo)
        hi = np.where(below, hi, mid)
    return (lo @ np.asarray(M2I, dtype=np.int64).T + 32768) >> 16


def dist2(first, second):
    """Scalar squared Oklab distance; Python ints avoid narrow-array overflow."""
    return sum((int(a) - int(b)) ** 2 for a, b in zip(first, second, strict=True))
