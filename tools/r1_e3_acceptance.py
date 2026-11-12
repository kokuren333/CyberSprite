"""Reproducible R1-E3 CLI demonstration using only authored engineering vectors."""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from cybersprite.core.canonical import load_project
from cybersprite.core.render import render
from cybersprite.formats.native import decode_gb
from cybersprite.formats.png import decode_png, encode_png


def main():
    destination = Path(sys.argv[1] if len(sys.argv) > 1 else "build/r1-e3-acceptance").resolve()
    destination.mkdir(parents=True, exist_ok=True)
    if any((destination / (name + ".csprite")).exists() for name in ("nds", "dmg")):
        raise SystemExit("Choose a new directory; existing projects are never replaced.")
    calls, summaries = [], []
    for name, platform in (("nds", "nds/sprite-80"), ("dmg", "dmg/sprite-16")):
        project = destination / (name + ".csprite")

        def cli(*args, project=project, name=name):
            result = subprocess.run(
                [sys.executable, "-m", "cybersprite", "-p", str(project), *args],
                cwd=destination,
                capture_output=True,
                encoding="utf-8",
                timeout=300,
            )
            if result.returncode:
                raise RuntimeError(f"CLI failed: {args}\n{result.stdout}\n{result.stderr}")
            value = json.loads(result.stdout)
            calls.append(dict(args=args, response=value))
            print(f"{len(calls)}: {name} {value['op']}", flush=True)
            return value

        cli("new", str(project), "--platform", platform, "--frames", "3")
        size = 80 if name == "nds" else 16
        p = load_project(project)
        colors = p.palette.colors
        indices = [1, 2] if name == "nds" else [3, 2, 1]
        actions = [
            dict(
                op="set_palette",
                args=dict(colors=colors, ramps=[dict(name="material", indices=indices)]),
            )
        ]
        for frame in range(3):
            actions.extend(
                [
                    dict(
                        op="rect",
                        args=dict(
                            layer="L1",
                            frame=frame,
                            x=size // 2 - 4 + frame,
                            y=size // 2 - 4,
                            w=6,
                            h=7,
                            filled=True,
                            color="@material:0",
                        ),
                    ),
                    dict(
                        op="set_pixel",
                        args=dict(
                            layer="L1",
                            frame=frame,
                            x=size // 2 - 2 + frame,
                            y=size // 2 - 2,
                            color="@material:1",
                        ),
                    ),
                ]
            )
        actions.append(
            dict(
                op="add_tag",
                args={"name": "idle", "from": 0, "to": 2, "direction": "pingpong", "repeat": 2},
            )
        )
        batch = destination / (name + "-ops.json")
        batch.write_text(
            json.dumps({"label": "Authored engineering vector", "ops": actions}) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        cli("apply", str(batch), "--preview", "none")
        # A tiny independent original reference tests the E2 guide path, without importing pixels.
        design = np.full((8, 8, 4), (255, 255, 255, 255), dtype=np.uint8)
        design[1:7, 2:6] = (0, 0, 0, 255)
        raw_design = destination / (name + "-design.png")
        raw_design.write_bytes(encode_png(design))
        source = cli(
            "source",
            "add",
            raw_design.name,
            "--provenance",
            '{"provider":"authored-engineering-vector","license":"CC0-1.0"}',
        )
        before = (project / "project.json").read_bytes()
        review = cli(
            "preview",
            "--layout",
            "review",
            "--frames",
            "all",
            "--guide",
            json.dumps({"source": source["result"]["source"]}),
            "--out",
            name + "-review.png",
        )
        assert (project / "project.json").read_bytes() == before
        image = decode_png((destination / (name + "-review.png")).read_bytes()).rgba()
        assert image.shape[:2] == (review["result"]["height"], review["result"]["width"])
        validate = cli("validate")["result"]
        assert validate["ok"]
        exported = cli(
            "export", "image", "--frames", "0", "--out", name + "-final.png", "--color-mode", "rgba"
        )
        assert exported["result"]["verified"] and exported["result"]["validation_ok"]
        assert np.array_equal(
            decode_png((destination / (name + "-final.png")).read_bytes()).rgba(),
            render(load_project(project), 0),
        )
        if name == "dmg":
            native = cli("export", "native", "--layer", "L1", "--out", "dmg.2bpp")
            assert native["result"]["verified"] and native["result"]["validation_ok"]
            assert len(decode_gb((destination / "dmg.2bpp").read_bytes())) == 12
        summaries.append(
            dict(
                project=name,
                revision=load_project(project).revision,
                review_shape=list(image.shape),
                validation=validate["counts"],
                warnings=[v for v in validate["issues"] if v["level"] == "warning"],
            )
        )
    (destination / "calls.json").write_text(
        json.dumps(calls, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (destination / "summary.json").write_text(
        json.dumps(summaries, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(summaries), flush=True)


if __name__ == "__main__":
    main()
