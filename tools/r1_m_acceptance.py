"""Exercise R1-M through actual CLI processes and decode the exported files independently."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from cybersprite.core.canonical import load_project
from cybersprite.core.render import render

ROOT = Path(__file__).resolve().parents[1]


def main():
    (ROOT / "build").mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="r1-m-verified-", dir=ROOT / "build"))
    project = directory / "test.csprite"
    environment = {**os.environ, "CYBERSPRITE_CONFIG_DIR": str(directory / "settings")}

    def call(*arguments):
        process = subprocess.run(
            ["uv", "run", "--no-sync", "csp", *map(str, arguments)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=True,
        )
        value = json.loads(process.stdout)
        assert value["ok"], value
        if "validation" in value:
            assert value["validation"]["ok"], value["validation"]
        return value

    call(
        "new",
        project,
        "--size",
        "4x4",
        "--frames",
        "2",
        "--palette",
        '["#ff00ff00","#102030ff","#405060ff"]',
        "--background",
        "1",
    )
    call(
        "-p",
        project,
        "op",
        "erase",
        "layer=L2",
        "frame=0",
        'region={"type":"rect","x":0,"y":0,"w":2,"h":2}',
    )
    call(
        "-p",
        project,
        "op",
        "rect",
        "layer=L1",
        "frame=1",
        "x=2",
        "y=2",
        "w=2",
        "h=2",
        "color=2",
        "filled=true",
    )
    expected = [render(load_project(project), f) for f in range(2)]
    call("-p", project, "op", "flatten")
    p = load_project(project)
    assert len(p.layers) == 1 and p.layers[0].background
    for f in range(2):
        np.testing.assert_array_equal(render(p, f), expected[f])
    info = call("-p", project, "info", "--include", "layers", "--include", "frames")
    assert set(info["result"]) == {"layers", "frames"}
    validation = call("-p", project, "validate")["result"]
    assert validation["ok"]
    outputs = {}
    for kind in ("gif", "apng"):
        path = directory / f"animation.{kind}"
        value = call(
            "-p", project, "export", "anim", "--out", path, "--format", kind, "--loop", "1"
        )
        assert value["result"]["validation_ok"] and value["result"]["verified"]
        with Image.open(path) as image:
            assert image.n_frames == 2
            for frame in range(2):
                image.seek(frame)
                np.testing.assert_array_equal(np.array(image.convert("RGBA")), expected[frame])
        outputs[kind] = str(path)
    path = directory / "sheet.png"
    value = call(
        "-p",
        project,
        "export",
        "sheet",
        "--out",
        path,
        "--layout",
        "horizontal",
        "--data-out",
        directory / "sheet.json",
        "--compression",
        "stored",
    )
    assert value["result"]["validation_ok"] and value["result"]["verified"]
    with Image.open(path) as image:
        np.testing.assert_array_equal(
            np.array(image.convert("RGBA")), np.concatenate(expected, axis=1)
        )
    outputs["sheet"] = str(path)
    path = directory / "frame.png"
    value = call("-p", project, "export", "image", "--out", path, "--frames", "0")
    assert value["result"]["validation_ok"] and value["result"]["verified"]
    with Image.open(path) as image:
        np.testing.assert_array_equal(np.array(image.convert("RGBA")), expected[0])
    outputs["png"] = str(path)
    call("schema", "sheet")
    print(json.dumps({"project": str(project), "outputs": outputs, "issues": validation["issues"]}))


if __name__ == "__main__":
    main()
