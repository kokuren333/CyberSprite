"""Representative R1-B2 measurements; run unchanged before and after optimization."""

import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter_ns

import numpy as np

from cybersprite import ops
from cybersprite.core import quality
from cybersprite.core.models import ImageCel, ImageLayer
from cybersprite.core.pixels import pixels_to_rows
from cybersprite.core.projects import create_project, new_project


def fixture(width, height, layers, frames, *, dense=False):
    p = new_project(width=width, height=height, frames=frames)
    yy, xx = np.indices((height, width), dtype=np.int32)
    p.layers = []
    for layer in range(layers):
        cels = []
        for frame in range(frames):
            image = np.ones((height, width), dtype=np.uint8)
            if not dense:
                image = (1 + ((xx + frame) // 8 + (yy + layer) // 8) % 2).astype(np.uint8)
                # All independent frames differ, even after the 16px pattern repeats.
                bits = min(width, 16)
                image[0, :bits] = 1 + ((frame >> np.arange(bits, dtype=np.int32)) & 1)
            cels.append(
                ImageCel(frame=frame, x=0, y=0, w=width, h=height, pixels=pixels_to_rows(image))
            )
        p.layers.append(ImageLayer(id=f"L{layer + 1}", name=f"Layer {layer + 1}", cels=cels))
    p.id_counters.layer = layers
    return p


CASES = (
    ("small_32_3_4", 32, 32, 3, 4),
    ("review_80_1_4", 80, 80, 1, 4),
    ("legacy_64_10_32", 64, 64, 10, 32),
    ("ds_96_8_45", 96, 96, 8, 45),
    ("review_96_1_16", 96, 96, 1, 16),
    ("medium_256_1_8", 256, 256, 1, 8),
    ("validate_256_1_32", 256, 256, 1, 32),
    ("wide_480_270_1_16", 480, 270, 1, 16),
    ("dense_1024_1_1", 1024, 1024, 1, 1),
)


def available_memory():
    if sys.platform != "win32":
        return None
    import ctypes

    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong)
            for name in (
                "total_physical",
                "available_physical",
                "total_pagefile",
                "available_pagefile",
                "total_virtual",
                "available_virtual",
                "available_extended_virtual",
            )
        ]

    value = Memory()
    value.length = ctypes.sizeof(value)
    assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value))
    return value.available_physical


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--case", action="append", choices=[c[0] for c in CASES])
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    cli = shutil.which("cybersprite")
    assert cli is not None
    result = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "workspace_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "source_revision": os.environ.get("CYBERSPRITE_BENCH_SOURCE_REVISION", "working-tree"),
        "measurements": {},
        "source_root": str(Path(ops.__file__).parents[1]),
        "source_sha256": {
            str(relative): sha256(
                (Path(ops.__file__).parents[1] / relative).read_bytes()
            ).hexdigest()
            for relative in (
                Path("core/quality.py"),
                Path("ops/__init__.py"),
                Path("generate/__init__.py"),
            )
        },
    }
    if args.resume and args.out.exists():
        result = json.loads(args.out.read_text("utf-8"))
    workspace_build = Path(__file__).resolve().parents[1] / "build"
    workspace_build.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=workspace_build) as directory:
        for name, width, height, layers, frames in CASES:
            if args.case and name not in args.case:
                continue
            measurements = result["measurements"].setdefault(name, {})
            expected = {"validate_cold", "validate_cached", "edit", "info_summary", "cli_info"}
            if name == "review_80_1_4":
                expected.add("cli_empty_layers")
            if expected <= measurements.keys():
                continue
            p = fixture(width, height, layers, frames, dense=name.startswith("dense"))
            root = Path(directory) / f"{name}.csprite"
            create_project(root, p)
            ops.execute("get_history", root)  # Exclude initial history setup from query timing.
            reference_row = p.layers[-1].cels[0].pixels[1]

            def record(label, function, prepare=lambda: None, name=name, measurements=measurements):
                if label in measurements:
                    return
                samples = []
                memory_before = []
                for i in range(3):
                    prepare()
                    memory_before.append(available_memory())
                    start = perf_counter_ns()
                    function(i)
                    samples.append((perf_counter_ns() - start) // 1000)
                measurements[label] = {
                    "us": samples,
                    "median_us": statistics.median(samples),
                    "available_physical_bytes_before": memory_before,
                }
                print(json.dumps({"case": name, label: measurements[label]}), flush=True)
                result["measurements"][name] = measurements
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(
                    json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
                )

            record("validate_cold", lambda _, p=p: quality.report(p), quality._FRAME_CACHE.clear)

            # Like reviewers: process-local edit after initial inspection, no preview.
            def edit(i, root=root, layers=layers, reference_row=reference_row):
                x = i + 1
                response = ops.execute(
                    "set_pixel",
                    root,
                    {
                        "layer": f"L{layers}",
                        "frame": 0,
                        "x": x,
                        "y": 1,
                        "color": 3 - int(reference_row[2 * x : 2 * x + 2], 16),
                        "preview": "none",
                    },
                )
                assert not response["no_op"] and response["validation"]["ok"]

            record("edit", edit)
            record("info_summary", lambda _, root=root: ops.execute("get_info", root))
            record(
                "cli_info",
                lambda _, root=root: subprocess.run(
                    [cli, "-p", str(root), "info"], check=True, capture_output=True
                ),
            )
            if name == "review_80_1_4":
                # Codex §4.1 uses empty 80²/4 frames and --include layers.
                empty = Path(directory) / "empty.csprite"
                create_project(empty, new_project(width=80, height=80, frames=4))
                record(
                    "cli_empty_layers",
                    lambda _, empty=empty: subprocess.run(
                        [cli, "-p", str(empty), "info", "--include", "layers"],
                        check=True,
                        capture_output=True,
                    ),
                )
            # Full rules and metrics are still evaluated; only unchanged frame analysis is reused.
            record("validate_cached", lambda _, p=p: quality.report(p))


if __name__ == "__main__":
    main()
