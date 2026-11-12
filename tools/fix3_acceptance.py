"""Exercise tile production CLI on a disposable meadow copy and retain verified PNGs."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from cybersprite.core.canonical import json_bytes, load_project
from cybersprite.core.pixels import pixels_from_rows, pixels_to_rows
from cybersprite.core.render import render
from cybersprite.formats.png import decode_png

REPOSITORY = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY / "e2e-tests/04-tileset/meadow.csprite"


def run_session(out):
    out = Path(out).resolve()
    if not out.is_relative_to(REPOSITORY):
        raise ValueError("Keep --out inside the repository workspace.")
    out.mkdir(parents=True, exist_ok=False)
    original = (SOURCE / "project.json").read_bytes()
    transcript = []

    with tempfile.TemporaryDirectory(prefix="meadow-", dir=out) as temporary:
        project = Path(temporary) / "meadow.csprite"
        shutil.copytree(SOURCE, project, ignore=shutil.ignore_patterns(".cybersprite"))

        def cli(*args, exit_code=0):
            process = subprocess.run(
                [sys.executable, "-m", "cybersprite", "-p", str(project), *map(str, args)],
                cwd=REPOSITORY,
                capture_output=True,
                encoding="utf-8",
                check=False,
            )
            assert process.returncode == exit_code, (process.stdout, process.stderr)
            value = json.loads(process.stdout)
            assert value["ok"] == (exit_code == 0), value
            transcript.append(dict(args=list(map(str, args)), response=value))
            if "validation" in value:
                assert value["validation"]["ok"], value["validation"]
            print(value["op"], value["revision"], flush=True)
            return value

        validation_before = cli("validate")["result"]
        assert validation_before["ok"]
        cli("preview", "--tileset", "TS1", "--scale", "4", "--out", out / "tileset.png")
        cli("preview", "--frames", "0", "--scale", "4", "--grid", "--out", out / "grid.png")
        cli("op", "get_tiles", "layer=L2", "frame=0")

        # Existing source tile 15 has a transparent border; reuse its indexed data only.
        p = load_project(project)
        ts = p.tilesets[0]
        tile = pixels_from_rows(ts.tiles[15].pixels, ts.tile_w, ts.tile_h)
        variants = [tile, tile[:, ::-1], tile[::-1], tile.T]
        data = np.concatenate(variants, axis=1)
        assert np.all(data[0] == p.palette.transparent_index)
        layer = cli("op", "add_layer", "name=Grid regression", "type=image", "--preview", "none")
        layer_id = layer["result"]["id"]
        cli(
            "op",
            "draw_rows",
            "--args",
            json.dumps(dict(layer=layer_id, frame=0, x=0, y=0, rows=pixels_to_rows(data))),
            "--preview",
            "none",
        )
        source_cel = load_project(project).layers[-1].cels[0]
        assert source_cel.y > 0  # Confirm normalization reproduces the reported condition.
        before = render(load_project(project))
        cli("preview", "--frames", "0", "--out", out / "before-conversion.png")
        converted = cli(
            "op",
            "tileset_from_layer",
            "--args",
            json.dumps(
                dict(
                    layer=layer_id,
                    tile_w=ts.tile_w,
                    tile_h=ts.tile_h,
                    match_flips=dict(x=True, y=True, d=True),
                )
            ),
        )
        assert converted["result"]["tiles"] == 1 and converted["result"]["tiles_total"] == 2
        converted_id = converted["result"]["tileset"]
        np.testing.assert_array_equal(render(load_project(project)), before)
        assert load_project(project).layers[-1].cels[0].y == 0
        cli("preview", "--frames", "0", "--out", out / "after-conversion.png")
        cli(
            "preview",
            "--tileset",
            converted_id,
            "--scale",
            "4",
            "--out",
            out / "converted-tiles.png",
        )
        changed = cli(
            "op",
            "set_tile_pixels",
            "--args",
            json.dumps(dict(tileset=converted_id, tile="new", rows=ts.tiles[15].pixels)),
        )
        assert changed["changed"]["data"] and changed["changed"]["frames"] == []
        for path in changed["preview"]["paths"]:
            shutil.copyfile(project / path, out / "tile-edit.png")
        in_use = cli("op", "delete_tileset", f"tileset={converted_id}", exit_code=3)
        assert in_use["error"]["code"] == "E_IN_USE"
        assert in_use["error"]["details"]["layers"][0]["id"] == layer_id
        cli("op", "delete_layer", f"layer={layer_id}", "--preview", "none")
        cli("op", "delete_tileset", f"tileset={converted_id}", "--preview", "none")
        cli(
            "op",
            "delete_tileset",
            f"tileset={converted_id}",
            "missing_ok=true",
            "--preview",
            "none",
        )
        validation = cli("validate")["result"]
        assert validation["ok"]
        for args in [
            ("export", "image", "--frames", "0", "--out", out / "final.png"),
            (
                "export",
                "tileset",
                "--tileset",
                "TS1",
                "--out",
                out / "tiles.png",
                "--data-out",
                out / "tiles.json",
            ),
        ]:
            result = cli(*args)["result"]
            assert result["validation_ok"] and result["verified"]
        metadata = json.loads((out / "tiles.json").read_bytes())
        assert metadata["tileset"] == "TS1" and metadata["name"] == ts.name
        assert metadata["tiles"][0]["display_index"] == 1 + ts.base_index
        np.testing.assert_array_equal(render(load_project(project)), render(load_project(SOURCE)))
        assert (SOURCE / "project.json").read_bytes() == original

    images = {}
    for path in sorted(out.glob("*.png")):
        raw = path.read_bytes()
        image = decode_png(raw).rgba()
        images[path.name] = dict(
            width=image.shape[1], height=image.shape[0], sha256=hashlib.sha256(raw).hexdigest()
        )
    summary = dict(
        original_sha256=hashlib.sha256(original).hexdigest(),
        original_unchanged=True,
        validation_before=validation_before,
        validation=validation,
        images=images,
        transcript=transcript,
    )
    (out / "session.json").write_bytes(json_bytes(summary))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_session(args.out)["images"], indent=2))


if __name__ == "__main__":
    main()
