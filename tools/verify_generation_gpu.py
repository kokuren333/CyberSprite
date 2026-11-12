"""Measure real CLI generation and retain JSON evidence outside the repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

from cybersprite.core.sources import find_source, read_manifest
from cybersprite.formats.png import decode_png


def cli(args, directory, label, *, measure=False):
    samples = []
    monitor = None
    if measure:
        monitor = subprocess.Popen(
            [
                "nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
                "-lms",
                "200",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )

        def collect():
            for line in monitor.stdout:
                if line.strip().isdigit():
                    samples.append(int(line.strip()))

        worker = threading.Thread(target=collect, daemon=True)
        worker.start()
    stdout_path = directory / f"{label}.stdout.json"
    stderr_path = directory / f"{label}.stderr.txt"
    started = time.perf_counter()
    try:
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                [sys.executable, "-m", "cybersprite", *args], stdout=stdout, stderr=stderr
            )
            try:
                process.wait(timeout=1800)
            except subprocess.TimeoutExpired:
                # Windows venv launchers spawn a base interpreter; kill that child too.
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                    )
                else:
                    process.kill()
                process.wait(timeout=30)
    finally:
        elapsed = time.perf_counter() - started
        if monitor is not None:
            monitor.terminate()
            monitor.wait(timeout=10)
            worker.join(timeout=10)
    record = {
        "args": args,
        "seconds": elapsed,
        "returncode": process.returncode,
        "peak_board_memory_mib_200ms": max(samples, default=None),
    }
    (directory / f"{label}.measurement.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(label, json.dumps(record), flush=True)
    content = stdout_path.read_text(encoding="utf-8")
    if not content.strip():
        raise RuntimeError(
            f"CLI produced no JSON; inspect {stderr_path} and {label}.measurement.json"
        )
    return json.loads(content), record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="sdxl-pixel")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--import-source", action="store_true")
    args = parser.parse_args()
    directory = args.out.resolve()
    root = Path(__file__).resolve().parents[1]
    if directory.is_relative_to(root):
        parser.error("Choose an output directory outside the repository.")
    directory.mkdir(parents=True, exist_ok=True)
    project = directory / "sdxl-pixel.csprite"
    hashes, measurements = [], []
    for number in range(args.runs):
        response, measurement = cli(
            [
                "-p",
                str(project),
                "gen",
                "run",
                "--backend",
                "diffusers",
                "--model",
                args.model,
                "--prompt",
                "pixel art, a small wooden chest, simple, flat colors, plain white background",
                "--negative-prompt",
                "3d render, realistic, text, watermark",
                "--width",
                "1024",
                "--height",
                "1024",
                "--seed",
                "42",
                "--params",
                '{"num_inference_steps":30,"guidance_scale":7,"deterministic":true}',
            ],
            directory,
            f"generation-{number + 1}",
            measure=True,
        )
        if not response.get("ok"):
            raise RuntimeError(response)
        source = find_source(read_manifest(project), response["result"]["sources"][0])
        image = project / source.files[0].path
        assert decode_png(image.read_bytes()).rgba().shape == (1024, 1024, 4)
        hashes.append(hashlib.sha256(image.read_bytes()).hexdigest())
        measurements.append(measurement)
    summary = {
        "seed": 42,
        "sha256": hashes,
        "same_bytes": len(set(hashes)) == 1,
        "runs": measurements,
        "median_seconds_including_process_load_hashing_and_png": statistics.median(
            m["seconds"] for m in measurements
        ),
    }
    (directory / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    if args.import_source:
        response, _ = cli(
            ["-p", str(project), "import", "image", "--source", "SRC1", "--preset", "ai"],
            directory,
            "import-ai",
        )
        print("Pipeline result:", json.dumps(response), flush=True)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
