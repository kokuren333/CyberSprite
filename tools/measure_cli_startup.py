"""Measure the installed CLI and audit lazy imports without loading heavy modules here."""

import argparse
import json
import platform
import shutil
import subprocess
import sys
from time import perf_counter_ns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=7)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be positive")
    executable = shutil.which("cybersprite")
    if executable is None:
        parser.error("Install the CLI with uv sync, then run this tool with uv run python")
    measurements = []
    for option in ("--version", "--help"):
        milliseconds = []
        for _ in range(args.samples):
            start = perf_counter_ns()
            result = subprocess.run([executable, option], capture_output=True, check=True)
            milliseconds.append((perf_counter_ns() - start) // 1_000_000)
            if result.stderr:
                raise RuntimeError(f"Unexpected CLI stderr: {result.stderr!r}")
        audit = subprocess.run(
            [sys.executable, "-X", "importtime", "-m", "cybersprite", option],
            capture_output=True,
            check=True,
            encoding="utf-8",
        )
        modules = [
            line.split("|")[-1].strip()
            for line in audit.stderr.splitlines()
            if line.startswith("import time:")
        ]
        heavy = sorted(
            {name.split(".")[0] for name in modules}
            & {
                "numpy",
                "pydantic",
                "PIL",
                "aseprite",
            }
        )
        if heavy:
            raise RuntimeError(f"Heavy modules imported for {option}: {heavy}")
        measurements.append(
            {
                "option": option,
                "samples_ms": milliseconds,
                "median_ms": sorted(milliseconds)[len(milliseconds) // 2],
                "heavy_imports": heavy,
            }
        )
    print(
        json.dumps(
            {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "executable": executable,
                "measurements": measurements,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
