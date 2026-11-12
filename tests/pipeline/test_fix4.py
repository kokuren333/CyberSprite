"""Production regression vectors for fractional grids and source lifecycle."""

import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from cybersprite.core import sources
from cybersprite.core.canonical import load_project
from cybersprite.core.render import render
from cybersprite.formats.png import decode_png, encode_png
from cybersprite.ops import execute, registry
from cybersprite.ops.ingest import ImportArgs
from cybersprite.pipeline.args import PipelineSettings
from cybersprite.pipeline.cli_api import convert, detect_grid
from cybersprite.pipeline.downsample import remove_background
from cybersprite.pipeline.quantize import extract_palette, quantize

SLIME = Path(__file__).parent / "corpus/slime"


@pytest.mark.parametrize(
    "filename",
    [
        "slime_generated_like.jpg",
        "variant_bicubic_only.png",
        "variant_bilinear_only.png",
        "variant_nearest_nonint.png",
        "variant_smooth_nojpeg.png",
        "variant_smooth_q80.jpg",
        "variant_smooth_q95.jpg",
        "variant_tile8drift_q80.jpg",
    ],
)
def test_slime_grid_vectors(filename):
    grid = detect_grid(SLIME / filename)
    assert grid["detected"]
    assert (grid["columns"], grid["rows"]) == (32, 32)
    if filename == "slime_generated_like.jpg":
        assert (grid["grid_score"], grid["peak"], grid["normalized_score"]) == (895, 1148, 6336)
        assert grid["x"]["numerator"] == 347 and grid["x"]["denominator"] == 32


def test_strict_pipeline_schema_and_partial_overrides():
    schema = ImportArgs.model_json_schema()
    for name in ("PipelineSettings", "GridSettings", "PaletteSettings", "BackgroundSettings"):
        assert schema["$defs"][name]["additionalProperties"] is False
        assert all(p.get("description") for p in schema["$defs"][name]["properties"].values())
    overrides = {
        "palette": {"protect": ["#ff0000", "#ffffffFF"]},
        "background": {"mode": "key", "color": "#f6f4ee"},
    }
    assert PipelineSettings.model_validate(overrides).model_dump(exclude_unset=True) == overrides
    for overrides in (
        {"grid": {"typo": 1}},
        {"background": {"color": "#xyzxyz"}},
        {"palette": {"merge_distance": 1.5}},
    ):
        with pytest.raises(ValidationError):
            PipelineSettings.model_validate(overrides)
    assert registry().get("import_image").args is ImportArgs


def test_background_tolerant_support_and_connected_removal():
    image = np.full((16, 16, 4), (246, 244, 238, 255), dtype=np.uint8)
    for y in range(16):
        for x in range(16):
            image[y, x, :3] += (x + y) % 5
    image[4:12, 4:12] = (0, 64, 0, 255)
    image[7, 7] = (246, 244, 238, 255)  # enclosed background stays opaque
    output, report = remove_background(image, "auto")
    assert report["removed_pixels"] == 192 and not report["warnings"]
    assert output[7, 7, 3] == 255
    for color in ("#f6f4ee", "#f6f4eeff", [246, 244, 238]):
        output, report = remove_background(image, "key", color=color, tolerance=5)
        assert report["removed_pixels"] == 192


def test_extraction_merges_noise_and_reserves_rare_salient_colors():
    image = np.full((32, 32, 4), (20, 160, 40, 255), dtype=np.uint8)
    image[::2, :, :3] = (21, 161, 41)
    image[4, :4] = (240, 100, 150, 255)
    image[5, :2] = (255, 255, 255, 255)
    palette = extract_palette(image, max_colors=3)
    assert len(palette) == 3
    assert (240, 100, 150, 255) in palette and (255, 255, 255, 255) in palette
    assert palette == extract_palette(image[::-1, ::-1], max_colors=3)
    protected = extract_palette(image, max_colors=2, protect=["#f06496"], salient_distance=0)
    assert (240, 100, 150, 255) in protected
    with pytest.raises(ValueError, match="Protected colors"):
        extract_palette(image, max_colors=1, protect=["#f06496", "#ffffff"])
    _, palette, _ = quantize(image, mode="fixed", source=["#14a028", "#ffffff"])
    assert (255, 255, 255, 255) in palette


def test_warnings_envelope_default_palette_background_and_quality(tmp_path):
    project = tmp_path / "sprite"
    execute("new_project", project, {"width": 32, "height": 32})
    result = execute(
        "import_image",
        project,
        {"files": str(SLIME / "slime_generated_like.jpg"), "provenance": {"license": "Apache-2.0"}},
        preview="none",
    )
    codes = {w["code"] for w in result["warnings"]}
    assert {"W_DEFAULT_PALETTE", "W_PIPELINE_GATE"} <= codes
    assert result["result"]["accepted"]
    assert any(i["rule"] == "Q-SRC-01" for i in result["validation"]["new_issues"])
    assert sources.read_manifest(project).sources[0].pipeline.report["warnings"]
    noisy = np.array(
        [[[x * 16, y * 16, (x + y) * 8, 255] for x in range(16)] for y in range(16)], dtype=np.uint8
    )
    input_path = tmp_path / "colorful.png"
    input_path.write_bytes(encode_png(noisy))
    converted = convert(
        input_path,
        tmp_path / "out.png",
        preset="photo",
        pipeline={
            "grid": {"target_w": 16, "target_h": 16},
            "background": {"mode": "auto"},
            "cleanup": {"min_cluster": 1},
            "gates": {"fidelity": None},
        },
    )
    assert any(w["code"] == "W_BACKGROUND_KEPT" for w in converted["warnings"])


def test_undo_redo_restores_source_metrics_across_branches(tmp_path):
    image = SLIME / "slime_clean_32.png"
    args = {"files": str(image), "preset": "exact", "provenance": {"license": "unknown"}}
    first = execute("import_image", tmp_path, args, preview="none")
    active = sources.read_manifest(tmp_path).sources[0].model_dump()
    pixels = render(load_project(tmp_path), 0)
    undone = execute("undo", tmp_path, preview="none")
    source = sources.read_manifest(tmp_path).sources[0]
    assert source.placements == [] and source.pipeline is None
    validation = execute("validate", tmp_path)["result"]
    assert validation["metrics"]["sources"]["grid_scores"] == {}
    assert not np.any(render(load_project(tmp_path), 0))
    execute("redo", tmp_path, preview="none")
    assert sources.read_manifest(tmp_path).sources[0].model_dump() == active
    np.testing.assert_array_equal(render(load_project(tmp_path), 0), pixels)
    execute("undo", tmp_path, preview="none")
    second = execute(
        "import_image", tmp_path, {"source": "SRC1", "preset": "exact"}, preview="none"
    )
    assert second["revision"]["after"] > first["revision"]["after"]
    assert len(sources.read_manifest(tmp_path).sources[0].placements) == 1
    execute("undo", tmp_path, preview="none")
    assert sources.read_manifest(tmp_path).sources[0].pipeline is None
    assert undone["validation"]["resolved_issues"]


def test_dry_run_writes_only_stage_previews_and_no_source(tmp_path):
    project = tmp_path / "sprite"
    execute("new_project", project, {"width": 32, "height": 32})
    before = {
        p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
    args = {
        "files": str(SLIME / "slime_generated_like.jpg"),
        "preset": "ai",
        "provenance": {"license": "unknown"},
    }
    result = execute("import_image", project, args, dry_run=True, preview="none")
    assert result["dry_run"] and result["result"]["placed"] is None
    assert result["result"]["source"] is None and len(result["result"]["stage_paths"]) == 5
    for name, data in before.items():
        assert (project / name).read_bytes() == data
    assert not (project / "source").exists()
    report = json.loads((project / result["result"]["report_path"]).read_bytes())
    assert report["grid"]["columns"] == 32
    assert (
        decode_png((project / ".cybersprite/previews/dry/result.png").read_bytes()).pixels.shape[1]
        == 32
    )
    for path in project.rglob("*"):
        if path.is_file() and path.relative_to(project).as_posix() not in before:
            assert path.is_relative_to(project / ".cybersprite/previews/dry")


def test_remove_unused_reports_null_for_removed_indices(tmp_path):
    execute("new_project", tmp_path, {"width": 1, "height": 1})
    execute(
        "draw_rows",
        tmp_path,
        {"layer": "L1", "frame": 0, "x": 0, "y": 0, "rows": ["01"]},
        preview="none",
    )
    result = execute("remap_palette", tmp_path, {"remove_unused": True}, preview="none")
    assert result["result"]["mapping"] == {"0": 0, "1": 1, **{str(i): None for i in range(2, 17)}}


def test_legacy_undo_marks_unavailable_metrics_and_redo_restores(tmp_path):
    args = {
        "files": str(SLIME / "slime_clean_32.png"),
        "preset": "exact",
        "provenance": {"license": "Apache-2.0"},
    }
    execute("import_image", tmp_path, args, preview="none")
    execute("import_image", tmp_path, {"source": "SRC1", "preset": "exact"}, preview="none")
    for path in (tmp_path / ".cybersprite/history/sources").glob("*.json"):
        path.unlink()
    execute("undo", tmp_path, preview="none")
    source = sources.read_manifest(tmp_path).sources[0]
    assert [p.revision for p in source.placements] == [1]
    assert source.pipeline.report["history_status"] == "undone_conversion_metrics"
    assert "grid_score" not in source.pipeline.report
    execute("redo", tmp_path, preview="none")
    source = sources.read_manifest(tmp_path).sources[0]
    assert [p.revision for p in source.placements] == [1, 2]
    assert source.pipeline.report["grid_score"] == 1000
    # Reconstruct a target that was itself created by a compact undo record.
    for path in (tmp_path / ".cybersprite/history/sources").glob("*.json"):
        path.unlink()
    execute("undo", tmp_path, preview="none")
    source = sources.read_manifest(tmp_path).sources[0]
    assert [p.revision for p in source.placements] == [1]


def test_wrong_coarse_grid_cannot_pass_without_diagnostics(tmp_path):
    result = convert(
        SLIME / "slime_generated_like.jpg",
        tmp_path / "wrong.png",
        pipeline={"grid": {"mode": "fixed", "cell_w": 32, "cell_h": 32}},
    )
    outcomes = {g["name"]: g["outcome"] for g in result["gates"]}
    assert outcomes["grid_cell_count"] == "warn"
    assert any(w["gate"] == "grid_cell_count" for w in result["warnings"])
