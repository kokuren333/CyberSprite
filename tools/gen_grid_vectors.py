"""Create missing language-independent grid vectors; never overwrite existing vectors."""

import argparse
import json
from pathlib import Path

import numpy as np

from cybersprite.pipeline.grid import _signals, detect_grid

ROOT = Path(__file__).resolve().parents[1]


def inputs():
    checker = np.array([[0, 255], [255, 0]], dtype=np.uint8).repeat(3, 0).repeat(3, 1)
    yield "checker-x3", [checker], {"max_cell": 4}
    yield "flat", [np.full((6, 6), 40, dtype=np.uint8)], {"max_cell": 4}
    stripe = np.tile([0, 0, 255, 255, 0, 0, 255, 255], (8, 1)).astype(np.uint8)
    yield "shared-axes", [stripe, stripe.T.copy()], {"max_cell": 4}
    # A rounded 5/2 span, hand-checked boundaries at 3,5,8.
    row = np.repeat([0, 255, 0, 255], [3, 2, 3, 2]).astype(np.uint8)
    fractional = np.tile(row, (10, 1))
    fractional[5:] = 255 - fractional[5:]
    yield "rational-span", [fractional], {"force_square": False, "max_cell": 5}
    # Smooth slopes exercise significant/local maxima and the auxiliary signal.
    ramp = np.array([0, 10, 30, 30, 20, 10, 10, 30], dtype=np.uint8)
    yield "slope-knots", [np.tile(ramp, (8, 1))], {"force_square": False, "max_cell": 4}
    yield "slope-knots-2d", [ramp[:, None] + ramp[None, :]], {"max_cell": 4}
    yield (
        "partial-fixed",
        [np.zeros((9, 11), dtype=np.uint8)],
        {
            "mode": "fixed",
            "cell_w": 4,
            "cell_h": 3,
            "offset_x": 1,
            "offset_y": 2,
        },
    )


def rgba(gray):
    return np.dstack([gray, gray, gray, np.full_like(gray, 255)])


def vector(name, grays, settings):
    frames = [rgba(gray) for gray in grays]
    return {
        "name": name,
        "grayscale_frames": [gray.tolist() for gray in grays],
        "alpha": 255,
        "settings": settings,
        "signals": {str(axis): [s.tolist() for s in _signals(frames, axis)] for axis in (0, 1)},
        "expected": detect_grid(frames, **settings),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    directory = ROOT / "tests/vectors/grid"
    directory.mkdir(parents=True, exist_ok=True)
    for name, grays, settings in inputs():
        path = directory / (name + ".json")
        data = (json.dumps(vector(name, grays, settings), indent=2) + "\n").encode()
        if args.check:
            if path.read_bytes() != data:
                raise SystemExit(f"Grid vector differs: {path}")
        else:
            with path.open("xb") as stream:
                stream.write(data)
        print(name)


if __name__ == "__main__":
    main()
