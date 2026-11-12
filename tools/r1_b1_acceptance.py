"""Exercise real CLI replay, history, undo/redo, validation, preview and export."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from cybersprite.core.canonical import load_project
from cybersprite.formats.png import decode_png


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("build/r1-b1-smoke.csprite"))
    root = parser.parse_args().project.resolve()

    def cli(*args):
        value = subprocess.run(
            [sys.executable, "-m", "cybersprite", "-p", str(root), *args],
            check=False,
            capture_output=True,
            encoding="utf-8",
            timeout=300,
        )
        assert value.returncode == 0, (args, value.stdout, value.stderr)
        return json.loads(value.stdout)

    cli("new", str(root), "--size", "4x4")
    first = cli(
        "op",
        "set_pixel",
        "layer=L1",
        "frame=0",
        "x=1",
        "y=1",
        "color=1",
        "--expect-revision",
        "0",
        "--idempotency-key",
        "smoke",
    )
    replay = cli(
        "op",
        "set_pixel",
        "layer=L1",
        "frame=0",
        "x=1",
        "y=1",
        "color=1",
        "--expect-revision",
        "0",
        "--idempotency-key",
        "smoke",
    )
    assert replay["replayed"] and replay["revision"] == first["revision"]
    cli("history")
    cli("undo")
    cli("redo")
    validation = cli("validate")
    out = root / "final.png"
    result = cli("export", "image", "--out", str(out))
    assert result["result"]["validation_ok"] and result["result"]["verified"]
    pixels = decode_png(out.read_bytes())
    assert pixels.rgba().shape == (4, 4, 4)
    assert load_project(root).revision == 3
    value = {"validation": validation, "export": result, "replay": replay}
    (root / "acceptance.json").write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(value))


if __name__ == "__main__":
    main()
