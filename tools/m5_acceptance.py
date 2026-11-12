"""Create the authored P-11 files and exercise public Ops for M5 acceptance."""

import argparse
from pathlib import Path

from cybersprite.core.canonical import json_bytes
from cybersprite.core.render import render
from cybersprite.formats.animation import decode_apng, decode_gif
from cybersprite.formats.aseprite_io import decode_aseprite, encode_aseprite
from cybersprite.formats.common import export_policy
from cybersprite.formats.png import encode_png
from cybersprite.ops import execute
from tools.m5_cases import animated_project, tile_project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--p11", type=Path)
    args = parser.parse_args()
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if args.p11:
        args.p11.mkdir(parents=True, exist_ok=True)
        for filename, p in [
            ("layers.aseprite", animated_project()),
            ("tile-flips.aseprite", tile_project()),
        ]:
            (args.p11 / filename).write_bytes(encode_aseprite(p))
    with export_policy(root):
        source = root / "source.aseprite"
        source.write_bytes(encode_aseprite(animated_project()))
        project = root / "animated.csprite"
        execute("import_aseprite", project, {"file": str(source), "if_exists": "open"})
        results = []
        for name, options in [
            (
                "export_sheet",
                dict(out="sheet.png", data_out="sheet.json", data_format="json-hash", trim=True),
            ),
            ("export_animation", dict(out="motion.gif", tag="Motion", scale=4)),
            (
                "export_animation",
                dict(out="motion.apng", tag="Motion", scale=4, compression="stored"),
            ),
            ("export_aseprite", dict(out="roundtrip.aseprite")),
        ]:
            results.append(execute(name, project, options))
        (root / "results.json").write_bytes(json_bytes(results))
        gif_frames, _, _ = decode_gif((root / "motion.gif").read_bytes())
        apng_frames, _, _ = decode_apng((root / "motion.apng").read_bytes())
        p, _ = decode_aseprite((root / "roundtrip.aseprite").read_bytes())
        for n, image in enumerate(gif_frames):
            (root / f"gif-frame-{n}.png").write_bytes(encode_png(image, compression="stored"))
        for n, image in enumerate(apng_frames):
            (root / f"apng-frame-{n}.png").write_bytes(
                encode_png(image.pixels, image.palette, compression="stored")
            )
        for n in range(len(p.frames)):
            (root / f"aseprite-frame-{n}.png").write_bytes(
                encode_png(render(p, n, dict(scale=4)), compression="stored")
            )
        print(f"Verified {len(results)} exports in {root}")


if __name__ == "__main__":
    main()
