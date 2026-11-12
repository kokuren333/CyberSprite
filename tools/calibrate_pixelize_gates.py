"""Measure final default-AUTO gates, with fixed wrong-grid and AUTO controls."""

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def summarize_records(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["category"]].append(row)
    return {
        category: {
            "n": len(group),
            "accepted": sum(row.get("accepted") is True for row in group),
            "rejected": sum(row.get("accepted") is False for row in group),
            "errors": sum("error" in row for row in group),
        }
        for category, group in sorted(grouped.items())
    }


def calibrate(
    output, *, code_root=None, repeats=3, categories=None, names=None, timeout=120, worker=None
):
    if code_root:
        sys.path.insert(0, str(code_root))
    output.mkdir(parents=True, exist_ok=True)

    corpus = ROOT / "tests/pipeline/corpus"
    inputs = []
    manifest = json.loads((corpus / "generated/manifest.json").read_text(encoding="utf-8"))
    for item in manifest["images"]:
        inputs.append((item["id"], item["category"], corpus / "generated" / item["file"], 1, None))
    for path in sorted((corpus / "non_pixel").glob("*.png")):
        inputs.append((path.stem, "e", path, 1, None))
    for path in sorted((corpus / "originals").glob("*.png")):
        inputs.append((path.stem, "f-auto-control", path, 4, None))
        for wrong in (5, 7):
            inputs.append(
                (
                    path.stem + f"-wrong{wrong}",
                    "f",
                    path,
                    4,
                    {"grid": {"mode": "fixed", "cell_w": wrong, "cell_h": wrong}},
                )
            )
    rows = []
    for name, category, path, factor, overrides in inputs:
        if categories and category not in categories:
            continue
        if names and name not in names:
            continue
        if worker is not None and (name, category) != tuple(worker):
            continue
        if worker is None:
            destination = output / "workers" / category / name
            command = [
                getattr(sys, "_base_executable", sys.executable),
                str(Path(__file__).resolve()),
                "--output",
                str(destination),
                "--repeats",
                str(repeats),
                "--worker",
                name,
                category,
            ]
            if code_root:
                command.extend(["--code-root", str(code_root.resolve())])
            environment = dict(os.environ)
            environment["PYTHONPATH"] = os.pathsep.join(sys.path)
            try:
                completed = subprocess.run(
                    command, capture_output=True, text=True, timeout=timeout, env=environment
                )
                if completed.returncode:
                    raise RuntimeError(completed.stderr[-2000:])
                row = json.loads((destination / "results.json").read_text(encoding="utf-8"))[
                    "records"
                ][0]
            except (
                subprocess.TimeoutExpired,
                RuntimeError,
                OSError,
                ValueError,
                IndexError,
            ) as error:
                row = {
                    "name": name,
                    "category": category,
                    "error": f"{type(error).__name__}: {error}",
                    "accepted": None,
                }
            rows.append(row)
            print(category, name, row.get("accepted"), row.get("error", ""), flush=True)
            output.mkdir(parents=True, exist_ok=True)
            (output / "results.json").write_text(
                json.dumps({"repeats": repeats, "records": rows}, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            continue
        runs, decisions = [], []
        try:
            from cybersprite.pipeline.decode import decode_raster
            from cybersprite.pipeline.runner import run_pipeline

            image = decode_raster(path)[0][0].repeat(factor, 0).repeat(factor, 1)
            for _ in range(repeats):
                start = time.perf_counter_ns()
                _, _, report = run_pipeline(
                    image, output / "stages" / category / name, preset="ai", overrides=overrides
                )
                runs.append((time.perf_counter_ns() - start) / 1_000_000)
                decisions.append(report["accepted"])
            rows.append(
                {
                    "name": name,
                    "category": category,
                    "accepted": report["accepted"],
                    "size": [report["result"]["width"], report["result"]["height"]],
                    "grid": {
                        k: report["grid"][k]
                        for k in (
                            "mode",
                            "detected",
                            "cell_w",
                            "cell_h",
                            "columns",
                            "rows",
                            "grid_score",
                            "alignment",
                            "snap_variance",
                        )
                    },
                    "gates": report["gates"],
                    "runs_ms": runs,
                    "median_ms": statistics.median(runs),
                    "repeat_identical_decision": len(set(decisions)) == 1,
                }
            )
        except Exception as error:
            rows.append(
                {"name": name, "category": category, "error": f"{type(error).__name__}: {error}"}
            )
        print(category, name, rows[-1].get("accepted", rows[-1].get("error")), flush=True)
        output.mkdir(parents=True, exist_ok=True)
        (output / "results.json").write_text(
            json.dumps({"repeats": repeats, "records": rows}, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    summary = summarize_records(rows)
    report = {"repeats": repeats, "summary": summary, "records": rows}
    (output / "results.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/pixelize-calibration")
    parser.add_argument("--code-root", type=Path, help="Optional archived baseline src directory.")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=["d", "d-nonpixel-control", "e", "f", "f-auto-control"],
        help="Subset of calibration categories.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Wall-clock deadline per input; timeouts are errors, never gate rejections.",
    )
    parser.add_argument("--worker", nargs=2, help=argparse.SUPPRESS)
    parser.add_argument(
        "--names", nargs="+", help="Measure only these named inputs (for explicit retries)."
    )
    parser.add_argument(
        "--summarize", type=Path, help="Aggregate recorded decisions without rerunning inputs."
    )
    args = parser.parse_args()
    if args.repeats < 1 or args.timeout < 1:
        parser.error("repeats and timeout must be positive")
    if args.summarize:
        report = json.loads(args.summarize.read_text(encoding="utf-8"))
        report["summary"] = summarize_records(report["records"])
        args.summarize.write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(json.dumps(report["summary"], indent=2))
    else:
        calibrate(
            args.output,
            code_root=args.code_root,
            repeats=args.repeats,
            categories=args.categories,
            names=args.names,
            timeout=args.timeout,
            worker=args.worker,
        )
