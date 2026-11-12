"""Exercise the actual CLI and independently inspect the final PNG bytes."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from cybersprite.core.canonical import load_project
from cybersprite.formats.png import decode_png


def main():
    directory = Path("build/r1-e1-review")
    directory.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="accept-", dir=directory)).resolve()
    root = run / "nds.csprite"
    env = {**os.environ, "CYBERSPRITE_CONFIG_DIR": str(run / "config")}
    records = []

    def cli(*args):
        proc = subprocess.run(
            [sys.executable, "-m", "cybersprite", *map(str, args)],
            capture_output=True,
            env=env,
            timeout=300,
        )
        assert proc.returncode == 0, (
            args,
            proc.stdout.decode("utf-8"),
            proc.stderr.decode("utf-8"),
        )
        result = json.loads(proc.stdout)
        assert result["ok"], result
        records.append({"args": list(map(str, args)), "envelope": result})
        print(args[0], "OK", flush=True)
        return result

    cli("new", root, "--platform", "nds/sprite-80")
    cli(
        "-p",
        root,
        "op",
        "set_pixel",
        "layer=L1",
        "frame=0",
        "x=1",
        "y=1",
        "color=1",
        "--preview",
        "none",
    )
    cli("-p", root, "op", "set_palette_color", "index=2", "color=#808080ff", "--preview", "none")
    dry = cli("-p", root, "op", "conform_palette", "--dry-run", "--preview", "none")
    assert dry["result"]["replacements"][0]["after"] == "#7b8484ff"
    cli("-p", root, "op", "conform_palette", "--preview", "none")
    validation = cli("-p", root, "validate")
    assert validation["result"]["ok"]
    assert validation["result"]["metrics"]["platform"]["id"] == "nds/sprite-80"
    cli("-p", root, "preview", "--frames", "all", "--no-inline")
    export = cli("-p", root, "export", "image", "--out", root / "final.png")
    assert export["result"]["verified"] and export["result"]["validation_ok"]
    image = root / "final.png"
    decoded = decode_png(image.read_bytes())
    assert decoded.pixels.shape == (80, 80)
    assert int(decoded.pixels[1, 1]) == 1
    from PIL import Image

    with Image.open(image) as independent:
        assert independent.size == (80, 80)
        assert independent.convert("RGBA").getpixel((1, 1)) == (0, 0, 0, 255)
    assert load_project(root).platform.id == "nds/sprite-80"
    (run / "records.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(run, flush=True)


if __name__ == "__main__":
    main()
