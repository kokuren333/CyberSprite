"""Generate Appendix B normative tables and independent integer test vectors.

Only this development tool uses floating point. Existing normative data is not
silently replaced: pass --write explicitly, then review the resulting diff.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M1 = [
    [0.4122214708, 0.5363325363, 0.0514459929],
    [0.2119034982, 0.6806995451, 0.1073969566],
    [0.0883024619, 0.2817188376, 0.6299787005],
]
M2 = [
    [0.2104542553, 0.7936177850, -0.0040720468],
    [1.9779984951, -2.4285922050, 0.4505937099],
    [0.0259040371, 0.7827717662, -0.8086757660],
]


def generate():
    lin = []
    for v in range(256):
        c = v / 255
        f = c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        lin.append(math.floor(f * 65535 + 0.5))
    m1, m2 = ([[math.floor(c * 65536 + 0.5) for c in row] for row in m] for m in (M1, M2))

    def convert(rgb):
        roots = []
        for row in m1:
            n = sum(row[i] * lin[rgb[i]] for i in range(3)) << 16
            # Independent binary-search oracle (runtime uses integer Newton).
            lo, hi = 0, 65537
            while lo + 1 < hi:
                mid = (lo + hi) // 2
                if mid**3 <= n:
                    lo = mid
                else:
                    hi = mid
            roots.append(lo)
        return [(sum(row[i] * roots[i] for i in range(3)) + 32768) >> 16 for row in m2]

    colors = [[v, v, v] for v in range(256)]
    colors += [[255, 0, 0], [0, 255, 0], [0, 0, 255], [0, 255, 255], [255, 0, 255], [255, 255, 0]]
    state = 0x43535052
    for _ in range(1000):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        colors.append([(state >> shift) & 255 for shift in (24, 16, 8)])
    bayer = [[0, 2], [3, 1]]
    matrices = {"bayer2": bayer}
    for size in (4, 8):
        half = size // 2
        bayer = [
            [
                4 * bayer[y % half][x % half] + [[0, 2], [3, 1]][y // half][x // half]
                for x in range(size)
            ]
            for y in range(size)
        ]
        matrices[f"bayer{size}"] = bayer
    return {
        "src/cybersprite/data/color/srgb_lin16_v1.json": lin,
        "src/cybersprite/data/color/m1i_v1.json": m1,
        "src/cybersprite/data/color/m2i_v1.json": m2,
        "src/cybersprite/data/color/bayer_v1.json": matrices,
        "tests/vectors/color/oklab_fixed_v1.json": {
            "version": 1,
            "lcg": {
                "seed": 0x43535052,
                "a": 1664525,
                "c": 1013904223,
                "modulus": 4294967296,
                "rgb_shifts": [24, 16, 8],
            },
            "vectors": [{"rgb": rgb, "lab": convert(rgb)} for rgb in colors],
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write generated normative files.")
    args = parser.parse_args()
    for name, value in generate().items():
        data = (json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n").encode()
        path = ROOT / name
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        elif not path.exists() or path.read_bytes() != data:
            raise SystemExit(f"Generated data differs: {name}; review before using --write.")
        print(hashlib.sha256(data).hexdigest(), name)
