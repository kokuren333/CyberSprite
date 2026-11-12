"""Measure standalone --version startup including interpreter and process startup."""

import statistics
import subprocess
import sys
from time import perf_counter_ns


def main():
    samples = []
    for _ in range(10):
        start = perf_counter_ns()
        result = subprocess.run(
            [sys.executable, "-m", "cybersprite", "--version"], capture_output=True, check=True
        )
        samples.append((perf_counter_ns() - start) // 1000000)
        assert result.stdout.strip() == b"cybersprite, version 0.1.0"
    print(
        f"--version: median={statistics.median(samples)} ms; max={max(samples)} ms; "
        f"samples={samples}; target <400 ms"
    )


if __name__ == "__main__":
    main()
