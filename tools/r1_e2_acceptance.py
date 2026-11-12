"""Run the R1-E2 engineering demonstration through real CLI subprocesses."""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from cybersprite.core.canonical import load_project
from cybersprite.core.render import render
from cybersprite.formats.png import decode_png, encode_png


def main():
    destination = Path(sys.argv[1] if len(sys.argv) > 1 else "build/r1-e2-verified").resolve()
    destination.mkdir(parents=True, exist_ok=True)
    project = destination / "demo.csprite"
    if project.exists():
        raise SystemExit("Use a fresh destination; the acceptance run never overwrites a project.")
    calls = []

    def cli(*args):
        result = subprocess.run(
            [sys.executable, "-m", "cybersprite", "-p", str(project), *args],
            cwd=destination,
            capture_output=True,
            encoding="utf-8",
            timeout=300,
        )
        if result.returncode:
            raise RuntimeError(f"CLI failed: {args}\n{result.stdout}\n{result.stderr}")
        value = json.loads(result.stdout)
        calls.append({"args": args, "response": value})
        print(f"{len(calls)}: {value['op']}", flush=True)
        return value

    def drawing(operation, **args):
        return cli(
            "op", operation, "layer=L1", "frame=0", "--preview", "none", "--args", json.dumps(args)
        )

    cli("new", str(project), "--size", "24x20")
    cli("op", "set_palette_color", "index=1", "color=#123456ff", "name=shadow", "--preview", "none")
    drawing("ellipse", x=5, y=4, w=13, h=13, filled=True, color="@shadow")
    drawing("rect", x=7, y=4, w=11, h=9, filled=True, color=2, mask={"only_on": ["@shadow"]})
    drawing("rect", x=9, y=4, w=7, h=4, filled=True, color=3, mask={"only_on": [2]})
    drawing("outline", color=4, exclude_colors=[4])
    second = drawing("outline", color=4, exclude_colors=[4])
    assert second["no_op"]
    cli("preview", "--rect", "4,3,15,15", "--scale", "8", "--out", "crop.png")
    design = np.full((20, 24, 4), (123, 45, 67, 255), dtype=np.uint8)
    (destination / "design.png").write_bytes(encode_png(design))
    before = (project / "project.json").read_bytes()
    added = cli("source", "add", "design.png", "--provenance", '{"license":"CC0-1.0"}')
    cli(
        "preview",
        "--frames",
        "all",
        "--scale",
        "8",
        "--guide",
        json.dumps({"source": added["result"]["source"]}),
        "--out",
        "guide.png",
    )
    assert (project / "project.json").read_bytes() == before
    validation = cli("validate")["result"]
    assert validation["ok"] and validation["counts"]["warning"] == 0
    exported = cli("export", "image", "--out", "export.png", "--color-mode", "rgba")
    assert exported["result"]["validation_ok"] and exported["result"]["verified"]
    decoded = decode_png((destination / "export.png").read_bytes()).rgba()
    assert np.array_equal(decoded, render(load_project(project), 0))
    (destination / "calls.json").write_text(
        json.dumps(calls, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "calls": len(calls),
                "validation": validation["counts"],
                "outline_second_no_op": second["no_op"],
                "verified": True,
                "output": str(destination),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
