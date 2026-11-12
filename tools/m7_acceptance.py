"""Run a real CLI tile session and retain reviewable images and validation envelopes."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from cybersprite.core.canonical import json_bytes, load_project
from cybersprite.core.hashing import pixel_sha256
from cybersprite.core.render import render
from cybersprite.formats.aseprite_io import equivalent, read_aseprite
from tools.m7_cases import GLYPH, PALETTE


def run_session(out):
    out = Path(out).resolve()
    if not out.is_relative_to(Path.cwd().resolve()):
        raise ValueError("Run from a parent directory of --out, matching the CLI export policy.")
    out.mkdir(parents=True, exist_ok=False)
    project = out / "session.csprite"
    transcript = []

    def cli(*args):
        command = [sys.executable, "-m", "cybersprite", *map(str, args)]
        result = subprocess.run(command, capture_output=True, check=True, encoding="utf-8")
        envelope = json.loads(result.stdout)
        assert envelope["ok"], envelope
        if "validation" in envelope:
            assert envelope["validation"]["ok"], envelope
        transcript.append({"args": list(map(str, args)), "response": envelope})
        print(envelope["op"], envelope["revision"], flush=True)
        return envelope

    def op(name, args):
        return cli("-p", project, "op", name, "--args", json.dumps(args), "--preview", "none")

    cli("new", project, "--size", "24x3", "--frames", "2", "--palette", json.dumps(PALETTE))
    op("add_tileset", dict(name="Glyphs", tile_w=3, tile_h=3))
    op("set_tile_pixels", dict(tileset="TS1", tile="new", rows=["010000", "020000", "030303"]))
    op("add_layer", dict(name="Map", type="tilemap", tileset="TS1"))
    op("set_tiles", dict(layer="L2", frame=0, col=0, row=0, rows=["1 1x 1y 1xy 1d 1xd 1yd 1xyd"]))
    op("link_cel", dict(layer="L2", source_frame=0, frames=[1]))
    # Keep an actual pre-correction export to review the shared edit's effect.
    cli("-p", project, "render", "--frame", "0", "--scale", "16", "--out", out / "before.png")
    fixed = op("set_tile_pixels", dict(tileset="TS1", tile=1, rows=GLYPH))
    assert [f["frame"] for f in fixed["changed"]["frames"]] == [0, 1]
    validation = cli("-p", project, "validate")
    assert validation["result"]["ok"] and validation["result"]["counts"]["warning"] == 0
    cli("-p", project, "preview", "--frames", "0,1", "--scale", "16", "--out", out / "preview")
    exports = [
        cli(
            "-p",
            project,
            "export",
            "image",
            "--out",
            out / "frame-{frame}.png",
            "--compression",
            "stored",
        ),
        cli(
            "-p",
            project,
            "export",
            "tileset",
            "--tileset",
            "TS1",
            "--out",
            out / "tiles.png",
            "--data-out",
            out / "tiles.json",
            "--scale",
            "24",
            "--compression",
            "stored",
        ),
        cli("-p", project, "export", "aseprite", "--out", out / "tiles.aseprite"),
    ]
    assert all(e["result"]["validation_ok"] and e["result"]["verified"] for e in exports)
    p = load_project(project)
    assert equivalent(p, read_aseprite(out / "tiles.aseprite")[0])
    hashes = {}
    for frame in range(2):
        with Image.open(out / f"frame-{frame}.png") as image:
            actual = np.asarray(image.convert("RGBA"))
        np.testing.assert_array_equal(actual, render(p, frame))
        hashes[f"frame-{frame}.png"] = pixel_sha256(actual)
    cli("-p", project, "render", "--frame", "0", "--scale", "16", "--out", out / "after.png")
    (out / "transcript.json").write_bytes(json_bytes(transcript))
    (out / "hashes.json").write_bytes(json_bytes(hashes))
    print(json.dumps(hashes), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    run_session(parser.parse_args().out)
