"""Compare the integrated runtime with the frozen R1-INT base on review fixtures."""

import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "4475308"


def main():
    destination = ROOT / "build/r1-int-measurements"
    destination.mkdir(parents=True, exist_ok=True)
    frozen = destination / "baseline"
    archive = subprocess.check_output(["git", "archive", "--format=zip", BASE, "src"], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        source.extractall(frozen)
    for label, source_root in (("before", frozen / "src"), ("after", ROOT / "src")):
        env = {
            **os.environ,
            "PYTHONPATH": str(source_root),
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "CYBERSPRITE_CONFIG_DIR": str(destination / "config"),
            "CYBERSPRITE_BENCH_SOURCE_REVISION": BASE if label == "before" else "r1-merge",
        }
        subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.benchmark_r1_b2",
                "--case",
                "ds_96_8_45",
                "--case",
                "validate_256_1_32",
                "--out",
                str(destination / (label + ".json")),
            ],
            env=env,
            cwd=ROOT,
            check=True,
        )
    from cybersprite.mcp import server

    original = {"__name__": "cybersprite.mcp.contracts"}
    exec(
        compile(
            subprocess.check_output(
                ["git", "show", "61ae19f:src/cybersprite/mcp/contracts.py"], cwd=ROOT
            ).decode("utf-8"),
            "pre-compaction-contracts",
            "exec",
        ),
        original,
    )
    describe = server.describe
    sizes = {}
    try:
        for label, function in (("before", original["describe"]), ("after", describe)):
            server.describe = function
            sizes[label] = {}
            for profile in ("standard", "minimal"):
                samples = []
                for _ in range(3):
                    service = server.MCPService(root=destination, profile=profile)
                    samples.append(
                        len(
                            json.dumps(
                                [
                                    tool.model_dump(by_alias=True, exclude_none=True)
                                    for tool in service.tools()
                                ]
                            ).encode()
                        )
                    )
                sizes[label][profile] = {
                    "tools": len(service.tools()),
                    "bytes": samples,
                    "median": sorted(samples)[1],
                }
    finally:
        server.describe = describe
    (destination / "mcp-size.json").write_text(
        json.dumps(sizes, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(sizes), flush=True)


if __name__ == "__main__":
    main()
