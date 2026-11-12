"""Run R1-A2's safe reproductions and real CLI/PNG checks without large allocations."""

import argparse
import importlib.util
import json
import statistics
import subprocess
import sys
from pathlib import Path
from time import perf_counter_ns

import numpy as np

from cybersprite import ops
from cybersprite.core.canonical import load_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.projects import new_project
from cybersprite.core.registry import OpContext
from cybersprite.core.render import _options, render_indexed
from cybersprite.formats.png import decode_png, encode_png
from cybersprite.ops.drawing import drawing
from cybersprite.pipeline._common import PipelineError
from cybersprite.pipeline.decode import decode_raster


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("build/r1-a2-review"))
    parser.add_argument("--baseline", required=True, help="Original fixr1-a2 base commit.")
    args = parser.parse_args()
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=True)
    project = root / "sample.csprite"
    # Repeated runs never overwrite a prior project.
    index = 1
    while project.exists():
        project = root / f"sample-{index}.csprite"
        index += 1
    commands = []

    def cli(*command, expected=0):
        result = subprocess.run(
            [sys.executable, "-m", "cybersprite", *map(str, command)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=300,
        )
        assert result.returncode == expected, (command, result.stdout, result.stderr)
        payload = json.loads(result.stdout)
        commands.append(
            dict(command=list(map(str, command)), exit_code=result.returncode, response=payload)
        )
        return payload

    cli("new", project, "--size", "2x2", "--palette", '["#00000000","#000000ff","#ffffffff"]')
    initial = (project / "project.json").read_bytes()
    rect = dict(layer="L1", frame=0, x=0, y=0, w=10**9, h=10**9, color=1)
    reject = cli(
        "-p", project, "op", "rect", "--args", json.dumps(rect), "--preview", "none", expected=6
    )
    assert reject["error"]["code"] == "E_LIMIT_EXCEEDED"
    wide = root / "wide.png"
    wide.write_bytes(encode_png(np.full((1, 8193, 4), 255, dtype=np.uint8)))
    imported = cli(
        "-p",
        project,
        "op",
        "import_image",
        "--args",
        json.dumps(dict(files=str(wide), preset="exact", provenance={"license": "unknown"})),
        expected=6,
    )
    assert imported["error"]["details"]["limit_name"] == "source_width"
    assert (project / "project.json").read_bytes() == initial
    drawn = cli(
        "-p",
        project,
        "op",
        "line",
        "--args",
        json.dumps(dict(layer="L1", frame=0, x0=0, y0=0, x1=1, y1=1, color=1)),
        "--preview",
        "path",
    )
    assert drawn["validation"]["after"]["ok"] if "after" in drawn["validation"] else drawn["ok"]
    validation = cli("-p", project, "validate")
    output = root / f"{project.stem}.png"
    exported = cli("-p", project, "op", "export_image", "--args", json.dumps(dict(out=str(output))))
    assert exported["result"]["validation_ok"] and exported["result"]["verified"]
    actual = decode_png(output.read_bytes())
    assert np.array_equal(actual.pixels, render_indexed(load_project(project)))
    try:
        _options(new_project(width=4096, height=4096), 0, {"scale": 64})
    except CyberSpriteError as error:
        scaling = error.as_dict()
    else:
        raise AssertionError("Scaling must fail before allocation.")

    # Supplementary bounded fixture, not a throughput claim for the unsafe 10**9 case.
    # Load only our own baseline implementations; all dependencies remain unchanged.
    def original(path, name, package):
        source = subprocess.run(
            ["git", "show", f"{args.baseline}:{path}"], check=True, capture_output=True
        ).stdout
        spec = importlib.util.spec_from_loader(name, loader=None)
        module = importlib.util.module_from_spec(spec)
        module.__package__ = package
        exec(compile(source, path, "exec"), module.__dict__)
        return module

    old_decode = original(
        "src/cybersprite/pipeline/decode.py", "a2_old_decode", "cybersprite.pipeline"
    )
    old_drawing = original("src/cybersprite/ops/drawing.py", "a2_old_drawing", "cybersprite.ops")
    old_drawing.raster = original(
        "src/cybersprite/core/raster.py", "a2_old_raster", "cybersprite.core"
    )
    measures = {}
    for label, before, after in (
        (
            "8193x1_header_only_decode",
            lambda: old_decode.decode_raster(wide),
            lambda: decode_raster(wide),
        ),
        ("512x512_off_canvas_rect", old_drawing.drawing, drawing),
    ):
        data = {}
        for version, function in (("before", before), ("after", after)):
            times = []
            for _ in range(3):
                if label.endswith("rect"):
                    ctx = OpContext(new_project(width=2, height=2), root)
                    shape = (
                        ops.registry()
                        .get("rect")
                        .parse(
                            dict(
                                layer="L1",
                                frame=0,
                                x=10000,
                                y=10000,
                                w=512,
                                h=512,
                                filled=True,
                                color=1,
                            )
                        )
                    )
                start = perf_counter_ns()
                try:
                    result = function(ctx, shape, "rect") if label.endswith("rect") else function()
                except PipelineError as error:
                    assert version == "after" and error.code == "E_LIMIT_EXCEEDED"
                else:
                    if label.endswith("rect"):
                        assert result == {"pixels_written": 0} and ctx.clipped_pixels == 262144
                times.append(perf_counter_ns() - start)
            data[version] = dict(runs_ns=times, median_ns=statistics.median(times))
        measures[label] = data
    record = dict(
        commands=commands,
        scaling=scaling,
        measurements=measures,
        validation=validation,
        baseline=args.baseline,
        output=str(output),
        project=str(project),
    )
    (root / "report.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            dict(report=str(root / "report.json"), output=str(output), measurements=measures),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
