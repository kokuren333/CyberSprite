"""Run the actual CLI on the copied production input and retain review artifacts."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from cybersprite.core.canonical import load_project
from cybersprite.core.render import render
from cybersprite.formats.png import decode_png
from cybersprite.pipeline.decode import decode_raster
from cybersprite.pipeline.quantize import assign_palette

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "tests/pipeline/corpus/slime/slime_generated_like.jpg"
TRUTH = ROOT / "tests/pipeline/corpus/slime/slime_clean_32.png"


def command(*args):
    process = subprocess.run(
        [sys.executable, "-m", "cybersprite", *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    envelope = json.loads(process.stdout)
    assert envelope["ok"], envelope
    return envelope


def agreement(image, truth):
    assert image.shape == truth.shape
    colors = [(0, 0, 0, 0)] + sorted({tuple(p) for p in truth.reshape(-1, 4) if p[3] == 255})
    mapped = assign_palette(image, colors)[0]
    normalized = np.asarray(colors, dtype=np.uint8)[mapped]
    return {
        "rgba_exact": int(np.all(image == truth, axis=2).sum()),
        "nearest_truth_palette": int(np.all(normalized == truth, axis=2).sum()),
        "alpha_mismatches": int(((image[:, :, 3] == 0) != (truth[:, :, 3] == 0)).sum()),
        "pixels": int(truth.shape[0] * truth.shape[1]),
    }


def main():
    base = ROOT / ".venv/fix4-review"
    base.mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="run-", dir=base))
    project = output / "slime.csprite"
    command("new", project, "--size", "32x32")
    before = (project / "project.json").read_bytes()
    dry = command("-p", project, "import", "image", INPUT, "--preset", "ai", "--dry-run")
    assert dry["dry_run"] and before == (project / "project.json").read_bytes()
    assert not (project / "source").exists()
    default = command(
        "-p",
        project,
        "import",
        "image",
        INPUT,
        "--preset",
        "ai",
        "--provenance",
        json.dumps({"license": "Apache-2.0"}),
    )
    assert default["result"]["accepted"]
    exported = command("-p", project, "export", "image", "--out", output / "default.png")
    assert exported["result"]["verified"] and exported["result"]["validation_ok"]
    image = decode_png((output / "default.png").read_bytes()).rgba()
    np.testing.assert_array_equal(image, render(load_project(project), 0))
    truth = decode_raster(TRUTH)[0][0]
    default_report = json.loads((project / default["result"]["report_path"]).read_bytes())
    command("-p", project, "undo")
    overrides = {"background": {"mode": "auto"}, "palette": {"mode": "extract"}}
    tuned = command(
        "-p",
        project,
        "import",
        "image",
        "--source",
        "SRC1",
        "--preset",
        "ai",
        "--pipeline",
        json.dumps(overrides),
    )
    assert tuned["result"]["accepted"]
    tuned_export = command(
        "-p", project, "export", "image", "--out", output / "auto-background.png"
    )
    assert tuned_export["result"]["verified"] and tuned_export["result"]["validation_ok"]
    tuned_image = decode_png((output / "auto-background.png").read_bytes()).rgba()
    np.testing.assert_array_equal(tuned_image, render(load_project(project), 0))
    command("-p", project, "undo")
    detailed_overrides = {
        "background": {"mode": "auto"},
        "downsample": {"method": "center"},
        "palette": {"mode": "extract", "max_colors": 8, "merge_distance": 3000},
        "cleanup": {"min_cluster": 1},
    }
    detailed = command(
        "-p",
        project,
        "import",
        "image",
        "--source",
        "SRC1",
        "--preset",
        "ai",
        "--pipeline",
        json.dumps(detailed_overrides),
    )
    assert detailed["result"]["accepted"]
    detailed_export = command(
        "-p", project, "export", "image", "--out", output / "center-preserved.png"
    )
    assert detailed_export["result"]["verified"] and detailed_export["result"]["validation_ok"]
    detailed_image = decode_png((output / "center-preserved.png").read_bytes()).rgba()
    np.testing.assert_array_equal(detailed_image, render(load_project(project), 0))
    summary = {
        "directory": output.as_posix(),
        "project": project.as_posix(),
        "default": {
            "grid": {
                k: default_report["grid"][k]
                for k in (
                    "columns",
                    "rows",
                    "grid_score",
                    "peak",
                    "normalized_score",
                    "alignment",
                    "snap_variance",
                )
            },
            "gates": default_report["gates"],
            "warnings": default["warnings"],
            "agreement": agreement(image, truth),
            "export": exported["result"],
        },
        "auto_background_extract": {
            "warnings": tuned["warnings"],
            "agreement": agreement(tuned_image, truth),
            "export": tuned_export["result"],
        },
        "center_preserved": {
            "pipeline": detailed_overrides,
            "agreement": agreement(detailed_image, truth),
            "export": detailed_export["result"],
        },
    }
    (output / "acceptance.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
