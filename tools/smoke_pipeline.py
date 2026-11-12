"""Run three reviewable imports and verify the actual placed PNG files."""

import json
from pathlib import Path

import numpy as np
from PIL import Image

from cybersprite.core.canonical import load_project
from cybersprite.core.render import render
from cybersprite.formats.png import decode_png, encode_png
from cybersprite.ops import execute
from cybersprite.pipeline.decode import decode_raster

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/pipeline/corpus/originals"
REVIEW = ROOT / ".cybersprite/m6-review"


def main():
    REVIEW.mkdir(parents=True, exist_ok=True)
    sparse = decode_raster(CORPUS / "sparse_firefly_32x32.png")[0][0].repeat(4, 0).repeat(4, 1)
    sparse_path = REVIEW / "sparse_x4.png"
    sparse_path.write_bytes(encode_png(sparse, compression="stored"))
    button = decode_raster(CORPUS / "button_32x16.png")[0][0].repeat(4, 0).repeat(4, 1)
    jpeg_path = REVIEW / "button_q75.jpg"
    Image.fromarray(button).convert("RGB").save(
        jpeg_path, quality=75, subsampling=0, optimize=False, progressive=False
    )
    cases = [
        ("hero", CORPUS / "hero_16x16.png", "exact", {}),
        ("sparse", sparse_path, "upscaled", {}),
        (
            "jpeg",
            jpeg_path,
            "ai",
            {"grid": {"mode": "fixed", "cell_w": 4, "cell_h": 4}, "cleanup": {"min_cluster": 1}},
        ),
    ]
    for name, path, preset, pipeline in cases:
        # Separate run directories preserve earlier review evidence on re-execution.
        serial = 1
        project = REVIEW / f"{name}_{serial}.csprite"
        while project.exists():
            serial += 1
            project = REVIEW / f"{name}_{serial}.csprite"
        result = execute(
            "import_image",
            project,
            {
                "files": str(path),
                "preset": preset,
                "pipeline": pipeline,
                "provenance": {
                    "license": "Apache-2.0",
                    "provider": "file",
                    "rights_note": "Original calibration art; deterministic JPEG test derivative.",
                },
            },
            actor="manual:m6",
            preview="path",
        )
        assert result["result"]["accepted"] and result["validation"]["ok"]
        pixels = render(load_project(project), 0)
        placed = project / "placed.png"
        placed.write_bytes(encode_png(pixels, compression="stored"))
        np.testing.assert_array_equal(decode_png(placed.read_bytes()).rgba(), pixels)
        np.testing.assert_array_equal(
            decode_png((project / "source/SRC1/result.png").read_bytes()).rgba(), pixels
        )
        print(
            json.dumps(
                {
                    "name": name,
                    "project": str(project),
                    "accepted": True,
                    "validation": result["validation"],
                    "placed_png": str(placed),
                    "stages": result["result"]["stage_paths"],
                }
            )
        )


if __name__ == "__main__":
    main()
