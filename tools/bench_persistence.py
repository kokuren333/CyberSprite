"""Reproduce R1 journal H, real-edit growth, and MCP single-call overhead."""

import argparse
import json
import platform
import statistics
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter_ns

from cybersprite import ops
from cybersprite.core import history
from cybersprite.core.projects import create_project
from cybersprite.mcp.server import TIMEOUTS, MCPService, _sdk
from tools.bench import fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--real-edits", type=int, default=1200)
    args = parser.parse_args()
    _sdk()  # SDK import is server startup, not single-call overhead.
    TIMEOUTS.update({"set_pixel": 600, "validate": 600})
    rows = {
        "metadata": {
            "python": sys.version,
            "platform": platform.platform(),
            "source": str(Path(history.__file__).resolve()),
            "mcp_fixture": "32x32, one dense layer, 10 distinct frames, path previews",
            "real_fixture": "32x32, one layer, alternating one-pixel edit, path previews",
        }
    }

    def record(name, samples, **details):
        rows[name] = {"ms": samples, "median_ms": statistics.median(samples), **details}
        print(json.dumps({name: rows[name]}), flush=True)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8", newline="\n")

    def timed(function):
        start = perf_counter_ns()
        value = function()
        assert (
            value.structured_content["ok"] if hasattr(value, "structured_content") else value["ok"]
        ), value
        return (perf_counter_ns() - start) / 1_000_000

    with TemporaryDirectory() as folder:
        root = Path(folder)
        p = root / "h"
        ops.execute("new_project", p, {"width": 16, "height": 16})
        pixel = {"layer": "L1", "frame": 0, "x": 1, "y": 1, "color": 1}
        ops.execute("set_pixel", p, pixel, preview="none")
        sample = history.read_journal(p)[-1]
        for count in (10, 1000, 10000):
            data = history.journal_bytes([dict(sample, revision=i + 1) for i in range(count)])
            (history.paths(p) / "journal.jsonl").write_bytes(data)
            record(
                f"H_{count}",
                [
                    timed(
                        lambda i=i: ops.execute(
                            "set_pixel",
                            p,
                            {**pixel, "color": 2 if i % 2 == 0 else 1},
                            preview="none",
                        )
                    )
                    for i in range(3)
                ],
                journal_bytes=len(data),
            )
        service = MCPService(root=root)
        for mode in ("direct", "mcp"):
            project = root / mode
            dense = fixture(32, frames=10)
            for frame, cel in enumerate(dense.layers[0].cels):
                row = cel.pixels[0]
                cel.pixels[0] = row[: frame * 2] + "03" + row[frame * 2 + 2 :]
            create_project(project, dense)
            ops.execute("get_info", project, {"include": ["summary"]})
            for name in ("set_pixel", "validate"):
                samples = []
                for i in range(3):
                    values = (
                        {**pixel, "color": 2 if i % 2 == 0 else 1, "preview": "path"}
                        if name == "set_pixel"
                        else {}
                    )
                    if mode == "direct":
                        samples.append(
                            timed(
                                lambda name=name, project=project, values=values: ops.execute(
                                    name, project, values
                                )
                            )
                        )
                    else:
                        samples.append(
                            timed(
                                lambda name=name, mode=mode, values=values: service.call(
                                    name, {"project": mode, **values}
                                )
                            )
                        )
                record(f"{mode}_{name}_32_10", samples)
        real = {200: [], 1000: [], 1200: []}
        late = []
        for trial in range(3):
            project = root / f"real{trial}"
            ops.execute("new_project", project, {"width": 32, "height": 32})
            samples = []
            for i in range(args.real_edits):
                samples.append(
                    timed(
                        lambda i=i, project=project: ops.execute(
                            "set_pixel",
                            project,
                            {**pixel, "color": 1 if i % 2 == 0 else 2},
                            preview="path",
                        )
                    )
                )
                if i + 1 in real:
                    real[i + 1].append(statistics.mean(samples[-50:]))
                    record(f"real_last50_at_{i + 1}", real[i + 1])
            if len(samples) >= 1200:
                late.append(statistics.mean(samples[1000:1200]))
                record("real_1001_to_1200", late)


if __name__ == "__main__":
    main()
