"""Run CLI animation previews on a temporary copy and retain diagnostic artifacts."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from cybersprite.core.canonical import json_bytes
from cybersprite.formats.png import decode_png

REPOSITORY = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY / "e2e-tests/03-walk-animation/runner.csprite"


def run_session(out):
    out = Path(out).resolve()
    if not out.is_relative_to(REPOSITORY):
        raise ValueError("Keep --out inside the repository workspace.")
    out.mkdir(parents=True, exist_ok=False)
    original = (SOURCE / "project.json").read_bytes()
    transcript = []

    with tempfile.TemporaryDirectory(prefix="runner-", dir=out) as temporary:
        project = Path(temporary) / "runner.csprite"
        shutil.copytree(SOURCE, project, ignore=shutil.ignore_patterns(".cybersprite"))

        def cli(*args):
            process = subprocess.run(
                [sys.executable, "-m", "cybersprite", "-p", str(project), *map(str, args)],
                cwd=REPOSITORY,
                capture_output=True,
                check=True,
                encoding="utf-8",
            )
            value = json.loads(process.stdout)
            assert value["ok"], value
            transcript.append({"args": list(map(str, args)), "response": value})
            print(value["op"], value["revision"], flush=True)
            return value["result"]

        validation = cli("validate")
        assert validation["ok"]
        layers = cli("info", "--include", "layers")["layers"]
        assert any(layer.get("link_groups") for layer in layers)
        for layout, selection in [("strip", "tag:walk"), ("grid", "all")]:
            result = cli(
                "preview",
                "--frames",
                selection,
                "--layout",
                layout,
                "--out",
                out / (layout + ".png"),
            )
            assert len(result["paths"]) == 1
            assert max(result["width"], result["height"]) <= 1024
        cli(
            "preview",
            "--frames",
            "0",
            "--onion",
            json.dumps({"prev": 1, "next": 1, "loop_tag": "walk"}),
            "--scale",
            "16",
            "--out",
            out / "onion-loop.png",
        )
        cli("preview", "--frames", "0", "--background", "#ffffff", "--out", out / "white.png")
        assert (project / "project.json").read_bytes() == original
        assert (SOURCE / "project.json").read_bytes() == original

    images = {}
    for path in sorted(out.glob("*.png")):
        raw = path.read_bytes()
        image = decode_png(raw).rgba()
        images[path.name] = {
            "width": image.shape[1],
            "height": image.shape[0],
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    summary = {
        "original_sha256": hashlib.sha256(original).hexdigest(),
        "original_unchanged": True,
        "validation": validation,
        "images": images,
        "transcript": transcript,
    }
    (out / "session.json").write_bytes(json_bytes(summary))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_session(args.out)["images"], indent=2))


if __name__ == "__main__":
    main()
