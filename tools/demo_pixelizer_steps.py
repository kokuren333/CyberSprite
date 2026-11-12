"""Exercise bundled pixelizers through real CLI and MCP import/validate/export calls."""

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from cybersprite.core.canonical import load_project
from cybersprite.core.render import render
from cybersprite.core.sources import read_manifest

ROOT = Path(__file__).resolve().parents[1]
METHODS = ("pixel_art_fixer", "proper_pixel_art", "pixeloe")


def verify(root, project, output, method):
    document = load_project(root / project)
    with Image.open(root / output) as decoded:
        pixels = np.asarray(decoded.convert("RGBA"))
    assert np.array_equal(pixels, render(document, 0))
    source = read_manifest(root / project).sources[0]
    report = source.pipeline.report
    record = report["plugins"][0]
    assert record["method"] == method and not record["level_a"]
    assert record["implementation"]["version"] != "uninstalled"
    return {
        "method": method,
        "size": [pixels.shape[1], pixels.shape[0]],
        "plugin": record,
        "warnings": report["warnings"],
        "gate_scope": "reconstructed output; input grid gates unavailable",
        "independent_png_decode_matches_render": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("build/r1-d2-demo"))
    args = parser.parse_args()
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    # Input remains the full-size corpus image; no downscaling of the fixture.
    (destination / "input.png").write_bytes(args.input.read_bytes())
    results = []
    provenance = {"provider": "engineering-demo", "license": "unknown"}
    manifest_path = args.input.parent / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(item for item in manifest["images"] if item["file"] == args.input.name)
        provenance = {
            "kind": "generated",
            "provider": entry["tool"],
            "license": "unknown" if entry["license"].startswith("unknown") else entry["license"],
            "rights_note": entry["license"],
            "prompt": entry["prompt"],
            "params": {
                "corpus_sha256": entry["sha256"],
                "ground_truth": None,
                "generator_model": entry["model"],
            },
        }

    def pipeline(method):
        params = {"target_w": 32, "target_h": 32} if method == "pixeloe" else {}
        return {"reconstruct": {"method": method, "params": params}}

    def cli(project, *command):
        process = subprocess.run(
            [sys.executable, "-m", "cybersprite", "-p", str(destination / project), *command],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=300,
        )
        if process.returncode:
            raise RuntimeError(process.stdout + process.stderr)
        return json.loads(process.stdout)

    for method in METHODS:
        project = "cli-" + method
        converted = cli(
            project,
            "convert",
            str(destination / "input.png"),
            str(destination / (project + "-converted.png")),
            "--preset",
            "ai",
            "--pipeline",
            json.dumps(pipeline(method)),
            "--stages",
            str(destination / (project + "-convert-stages")),
        )
        assert converted["result"]["accepted"] and converted["result"]["verified"]
        imported = cli(
            project,
            "import",
            "image",
            str(destination / "input.png"),
            "--preset",
            "ai",
            "--pipeline",
            json.dumps(pipeline(method)),
            "--provenance",
            json.dumps(provenance),
            "--preview",
            "none",
        )
        assert imported["result"]["accepted"], imported
        validation = cli(project, "validate")
        exported = cli(project, "export", "image", "--out", str(destination / (project + ".png")))
        assert exported["result"]["validation_ok"] and exported["result"]["verified"]
        row = verify(destination, project, project + ".png", method)
        with Image.open(destination / (project + "-converted.png")) as left:
            with Image.open(destination / (project + ".png")) as right:
                assert np.array_equal(
                    np.asarray(left.convert("RGBA")), np.asarray(right.convert("RGBA"))
                )
        row.update(surface="cli", import_result=imported, validation=validation, export=exported)
        row["convert"] = converted
        results.append(row)
        (destination / "results.json").write_text(
            json.dumps(results, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print("cli", method, row["size"], flush=True)

    async def mcp_demo():
        from mcp import Client

        from cybersprite.mcp.server import create_server

        async with Client(create_server(root=destination)) as client:
            for method in METHODS:
                project = "mcp-" + method

                async def call(name, project=project, **arguments):
                    result = await client.call_tool(name, {"project": project, **arguments})
                    assert not result.is_error, result.structured_content
                    return result.structured_content

                imported = await call(
                    "import_image",
                    files=["input.png"],
                    preset="ai",
                    pipeline=pipeline(method),
                    provenance=provenance,
                    preview="none",
                )
                assert imported["result"]["accepted"]
                validation = await call("validate")
                exported = await call("export_image", out=project + ".png")
                assert exported["result"]["validation_ok"] and exported["result"]["verified"]
                row = verify(destination, project, project + ".png", method)
                with Image.open(destination / ("cli-" + method + ".png")) as left:
                    with Image.open(destination / (project + ".png")) as right:
                        assert np.array_equal(
                            np.asarray(left.convert("RGBA")), np.asarray(right.convert("RGBA"))
                        )
                row["cli_mcp_pixels_identical"] = True
                row.update(
                    surface="mcp", import_result=imported, validation=validation, export=exported
                )
                results.append(row)
                (destination / "results.json").write_text(
                    json.dumps(results, indent=2) + "\n", encoding="utf-8", newline="\n"
                )
                print("mcp", method, row["size"], flush=True)

    asyncio.run(mcp_demo())


if __name__ == "__main__":
    main()
