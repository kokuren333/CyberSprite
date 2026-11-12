"""Measure all SPEC 13.8 targets; timings include IO but exclude fixture setup."""

import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter_ns

import numpy as np

from cybersprite import ops
from cybersprite.core.models import ImageCel, ImageLayer
from cybersprite.core.pixels import pixels_to_rows
from cybersprite.core.projects import create_project, new_project
from cybersprite.core.quality import report
from cybersprite.core.render import render
from cybersprite.formats.png import encode_png
from cybersprite.pipeline.cli_api import convert
from tools.gui_test_support import connect_gui, rpc, running_gui

ROOT = Path(__file__).resolve().parents[1]


def fixture(size, layers=1, frames=1):
    p = new_project(width=size, height=size, frames=frames)
    yy, xx = np.indices((size, size), dtype=np.int32)
    pattern = (1 + (xx // 8 + yy // 8) % 2).astype(np.uint8)
    p.layers = [
        ImageLayer(
            id=f"L{layer + 1}",
            name=f"Layer {layer + 1}",
            cels=[
                ImageCel(frame=f, x=0, y=0, w=size, h=size, pixels=pixels_to_rows(pattern))
                for f in range(frames)
            ],
        )
        for layer in range(layers)
    ]
    p.id_counters.layer = layers
    return p


def measure(function, count):
    values = []
    for i in range(count):
        start = perf_counter_ns()
        function(i)
        values.append((perf_counter_ns() - start) // 1000)
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--out", type=Path, default=ROOT / "build/m10-bench.json")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive.")
    values = {}

    def record(name, limit, function):
        samples = measure(function, args.repeats)
        values[name] = {
            "microseconds": samples,
            "target_ms": limit,
            "median_us": statistics.median_low(samples),
            "max_us": max(samples),
            "all_within_target": max(samples) <= limit * 1000,
        }
        print(json.dumps({name: values[name]}), flush=True)

    cli = shutil.which("cybersprite")
    if cli is None:
        parser.error("Run with uv run python -m tools.bench to use the installed CLI.")
    record(
        "cli_version",
        400,
        lambda _: subprocess.run([cli, "--version"], check=True, capture_output=True),
    )
    with TemporaryDirectory() as folder:
        root = Path(folder)
        p = fixture(64, 10, 32)
        project = root / "transaction.csprite"
        # Initial, exclusive creation only. Every subsequent write uses the registry.
        create_project(project, p)
        ops.execute("get_info", project, {"include": ["summary"]})

        def transaction(i):
            value = ops.execute(
                "set_pixel",
                project,
                {
                    "layer": "L10",
                    "frame": 0,
                    "x": 1,
                    "y": 1,
                    "color": 2 if i % 2 == 0 else 1,
                    "preview": "path",
                },
            )
            assert value["validation"]["ok"] and value["preview"]["paths"]

        record("transaction_64_10_32_with_preview", 150, transaction)
        p = fixture(256)
        record("render_256", 50, lambda _: render(p))
        p32 = fixture(256, frames=32)
        record("validate_256_32", 2000, lambda _: report(p32))
        gui_project = root / "gui.csprite"
        create_project(gui_project, fixture(128))
        ops.execute("get_info", gui_project, {"include": ["summary"]})
        with running_gui(root, gui_project) as (origin, token), connect_gui(origin, token) as c:
            rpc(c, "project.open", {"project": "gui.csprite"})

            def gui(i):
                value, _ = rpc(
                    c,
                    "op.apply",
                    {
                        "op": "set_pixel",
                        "args": {
                            "layer": "L1",
                            "frame": 0,
                            "x": 1,
                            "y": 1,
                            "color": 2 if i % 2 == 0 else 1,
                            "preview": "none",
                        },
                    },
                )
                assert value["result"]["validation"]["ok"]
                value, _ = rpc(c, "render.frame", {"frame": 0})
                assert value["result"]["frames"][0]["width"] == 128

            record("gui_128_op_and_render_roundtrip", 50, gui)
        # The same four-colour engineering pattern scaled 16x; the built-in
        # upscaled preset must recover 64x64. Decode/stages/report/verification included.
        image = render(fixture(64)).repeat(16, 0).repeat(16, 1)
        source = root / "pipeline.png"
        source.write_bytes(encode_png(image, compression="stored"))

        def pipeline(i):
            result = convert(
                source,
                root / f"converted{i}.png",
                preset="upscaled",
                stages=str(root / f"stages{i}"),
            )
            assert result["accepted"] and result["verified"]

        record("pipeline_1024", 5000, pipeline)
    output = {
        "machine": {
            "os": platform.platform(),
            "cpu": platform.processor(),
            "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        "measurements": values,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
