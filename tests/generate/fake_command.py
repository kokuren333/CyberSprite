"""A deterministic, authored test command; no models, downloaded assets or shell."""

import argparse
import json
from pathlib import Path

import numpy as np

from cybersprite.formats.png import encode_png

parser = argparse.ArgumentParser()
for field in ("prompt", "negative-prompt", "out"):
    parser.add_argument("--" + field, required=True)
for field in ("width", "height", "seed", "count"):
    parser.add_argument("--" + field, type=int, required=True)
args = parser.parse_args()
out = Path(args.out)
(out.parent / "received.json").write_text(json.dumps(vars(args)), encoding="utf-8")
for i in range(args.count):
    pixels = np.zeros((args.height, args.width, 4), dtype=np.uint8)
    pixels[:, :, 3] = 255
    pixels[1:-1, 1:-1, :3] = (255, 255, 255)
    destination = out if args.count == 1 else out.with_stem(f"{out.stem}_{i:04d}")
    destination.write_bytes(encode_png(pixels, compression="stored"))
