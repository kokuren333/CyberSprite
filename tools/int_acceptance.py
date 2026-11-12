"""Run INT-1 acceptance through CLI subprocesses and decode the actual exports."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from cybersprite.core.canonical import load_project
from cybersprite.core.hashing import pixel_sha256
from cybersprite.core.render import render
from cybersprite.formats.png import encode_png

REPOSITORY = Path(__file__).resolve().parents[1]


def run(directory):
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    transcript = []

    def cli(*arguments):
        process = subprocess.run(
            [sys.executable, "-m", "cybersprite", *map(str, arguments)],
            cwd=directory,
            capture_output=True,
            check=True,
        )
        assert not process.stderr, process.stderr.decode("utf-8")
        value = json.loads(process.stdout)
        assert value["ok"], value
        transcript.append({"argv": list(map(str, arguments)), "response": value})
        (directory / "cli-transcript.json").write_text(
            json.dumps(transcript, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return value

    calls = [
        json.loads(line)
        for line in (REPOSITORY / "tests/e2e/scenarios/scenario1/calls.jsonl")
        .read_text("utf-8")
        .splitlines()
    ]
    cli(
        "new",
        "hero.csprite",
        "--size",
        "16x16",
        "--palette",
        '["#00000000","#202040ff","#80c0ffff"]',
    )
    for call in calls[1:5]:
        args = dict(call["arguments"])
        args.pop("project")
        args.pop("preview", None)
        if call["name"] == "apply_ops":
            filename = directory / f"draw-{len(transcript)}.json"
            filename.write_text(json.dumps(args) + "\n", encoding="utf-8", newline="\n")
            cli("-p", "hero.csprite", "apply", filename)
        else:
            cli("-p", "hero.csprite", "op", call["name"], "--args", json.dumps(args))
    assert cli("-p", "hero.csprite", "validate")["result"]["ok"]
    cli("-p", "hero.csprite", "preview", "--frames", "0,1,2,3", "--out", "previews")
    for kind, out, extra in (
        (
            "sheet",
            "walk.png",
            [
                "--data-out",
                "walk.json",
                "--data-format",
                "json-hash",
                "--tag",
                "walk",
                "--columns",
                "4",
                "--compression",
                "stored",
            ],
        ),
        ("anim", "walk.gif", ["--tag", "walk"]),
        ("anim", "walk.apng", ["--tag", "walk"]),
        ("aseprite", "walk.aseprite", []),
    ):
        result = cli("-p", "hero.csprite", "export", kind, "--out", out, *extra)["result"]
        assert result["validation_ok"] and result["verified"]
    cli("import", "aseprite", "walk.aseprite", "--out", "returned.csprite")
    original, returned = (
        load_project(directory / name) for name in ("hero.csprite", "returned.csprite")
    )
    assert original.model_dump(exclude={"revision"}) == returned.model_dump(exclude={"revision"})
    frames = [render(original, frame) for frame in range(4)]
    hashes = {}
    for filename in ("walk.png", "walk.gif", "walk.apng"):
        with Image.open(directory / filename) as image:
            decoded = []
            for index in range(getattr(image, "n_frames", 1)):
                image.seek(index)
                decoded.append(np.array(image.convert("RGBA")))
        expected = [np.concatenate(frames, axis=1)] if filename == "walk.png" else frames
        assert len(decoded) == len(expected)
        for actual, reference in zip(decoded, expected, strict=True):
            np.testing.assert_array_equal(actual, reference)
        hashes[filename] = [pixel_sha256(frame) for frame in decoded]
        contact = np.concatenate(decoded, axis=1)
        (directory / f"{filename}-decoded.png").write_bytes(
            encode_png(np.repeat(np.repeat(contact, 8, axis=0), 8, axis=1))
        )
    corpus = REPOSITORY / "tests/pipeline/corpus/originals/hero_16x16.png"
    imported = cli(
        "-p",
        "corpus.csprite",
        "import",
        "image",
        corpus,
        "--preset",
        "exact",
        "--provenance",
        '{"license":"unknown"}',
    )
    assert imported["result"]["accepted"]
    result = cli("-p", "corpus.csprite", "export", "image", "--out", "corpus.png")["result"]
    assert result["validation_ok"] and result["verified"]
    with Image.open(corpus) as image:
        expected = np.array(image.convert("RGBA"))
    with Image.open(directory / "corpus.png") as image:
        np.testing.assert_array_equal(np.array(image.convert("RGBA")), expected)
    report = {"commands": len(transcript), "roundtrip_equal": True, "export_hashes": hashes}
    (directory / "report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("build/int-acceptance"))
    run(parser.parse_args().out)
