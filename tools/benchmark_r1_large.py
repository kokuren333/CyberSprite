"""Codex R1 section 7 L: fresh-process render then validate, three runs per fixture."""

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
from pathlib import Path
from time import perf_counter_ns


def worker(size, dense):
    import ctypes
    from ctypes import wintypes

    from cybersprite.core.models import ImageCel
    from cybersprite.core.projects import new_project
    from cybersprite.core.quality import report
    from cybersprite.core.render import render

    project = new_project(width=size, height=size)
    project.layers[0].cels = [
        ImageCel(
            frame=0,
            x=0,
            y=0,
            w=size if dense else 1,
            h=size if dense else 1,
            pixels=["01" * size] * size if dense else ["01"],
        )
    ]
    start = perf_counter_ns()
    render(project)
    render_us = (perf_counter_ns() - start) // 1000
    start = perf_counter_ns()
    result = report(project)
    validate_us = (perf_counter_ns() - start) // 1000
    peak_bytes = None
    if sys.platform == "win32":

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "PeakWorkingSetSize",
                    "WorkingSetSize",
                    "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage",
                    "QuotaPeakNonPagedPoolUsage",
                    "QuotaNonPagedPoolUsage",
                    "PagefileUsage",
                    "PeakPagefileUsage",
                )
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        get_process = ctypes.windll.kernel32.GetCurrentProcess
        get_process.restype = wintypes.HANDLE
        get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        assert get_memory(get_process(), ctypes.byref(counters), counters.cb)
        peak_bytes = counters.PeakWorkingSetSize
    print(
        json.dumps(
            {
                "render_us": render_us,
                "validate_us": validate_us,
                "peak_working_set_bytes": peak_bytes,
                "ok": result["ok"],
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--worker", choices=("dense", "sparse"))
    args = parser.parse_args()
    if args.worker:
        worker(1024 if args.worker == "dense" else 4096, args.worker == "dense")
        return
    if args.out is None:
        parser.error("--out is required unless --worker is used")
    environment = dict(os.environ)
    if args.source:
        environment["PYTHONPATH"] = str(args.source.resolve())
    output = {"platform": platform.platform(), "source": str(args.source), "measurements": {}}
    for name in ("dense", "sparse"):
        samples = []
        for _ in range(3):
            result = subprocess.run(
                [sys.executable, "-m", "tools.benchmark_r1_large", "--worker", name],
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            sample = json.loads(result.stdout)
            assert sample["ok"]
            samples.append(sample)
        output["measurements"][name] = {
            "samples": samples,
            "median_render_us": statistics.median(s["render_us"] for s in samples),
            "median_validate_us": statistics.median(s["validate_us"] for s in samples),
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({name: output["measurements"][name]}), flush=True)


if __name__ == "__main__":
    main()
