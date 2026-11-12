"""Measure the complete built-in conversion, including decode, reports and stored PNGs."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter_ns

import numpy as np

from cybersprite.formats.png import encode_png
from cybersprite.pipeline.cli_api import convert
from cybersprite.pipeline.decode import decode_raster

ROOT = Path(__file__).resolve().parents[1]


def main():
    truth = decode_raster(ROOT / "tests/pipeline/corpus/originals/hero_16x16.png")[0][0]
    tiled = np.tile(truth, (4, 4, 1)).repeat(16, 0).repeat(16, 1)
    with TemporaryDirectory(dir=ROOT / ".cybersprite") as folder:
        root = Path(folder)
        source = root / "input.png"
        source.write_bytes(encode_png(tiled, compression="stored"))
        measurements = []
        for repeat in range(3):
            start = perf_counter_ns()
            result = convert(
                source,
                root / f"output{repeat}.png",
                preset="upscaled",
                stages=str(root / f"stages{repeat}"),
            )
            elapsed = (perf_counter_ns() - start) // 1_000_000
            assert result["accepted"] and result["verified"]
            measurements.append(elapsed)
    print(
        json.dumps(
            {
                "input": [1024, 1024],
                "output": [64, 64],
                "milliseconds": measurements,
                "target_ms": 5000,
                "all_within_target": max(measurements) <= 5000,
            }
        )
    )


if __name__ == "__main__":
    (ROOT / ".cybersprite").mkdir(exist_ok=True)
    main()
