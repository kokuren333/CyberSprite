import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from cybersprite.core import history, sources
from cybersprite.core.canonical import load_project
from cybersprite.core.color import compare_hue, dist2, rgb_to_oklab_fixed
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.render import render
from cybersprite.formats.png import decode_png, encode_png
from cybersprite.ops import execute
from cybersprite.pipeline.cli_api import convert, detect_grid
from cybersprite.pipeline.decode import decode_raster
from cybersprite.pipeline.runner import run_pipeline

CORPUS = Path(__file__).parent / "corpus"
ORIGINALS = sorted((CORPUS / "originals").glob("*.png"))


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_NOW", "2026-11-12T12:00:00+09:00")


def ingest(project, path=None, **kwargs):
    args = {"preset": "exact", **kwargs}
    if "source" not in args:
        args.setdefault("files", str(path or ORIGINALS[0]))
        args.setdefault("provenance", {"license": "Apache-2.0"})
    return execute("import_image", project, args, actor="test:m6", preview="none")


@pytest.mark.parametrize("path", ORIGINALS, ids=lambda p: p.stem)
@pytest.mark.parametrize("factor", range(1, 17))
def test_real_originals_exact_auto_end_to_end(tmp_path, path, factor):
    truth = decode_raster(path)[0][0]
    image = truth.repeat(factor, 0).repeat(factor, 1)
    frames, palette, report = run_pipeline(
        image, tmp_path, preset="exact" if factor == 1 else "upscaled"
    )
    assert report["accepted"] and report["verified"]
    assert report["grid"]["cell_w"] == report["grid"]["cell_h"] == factor
    np.testing.assert_array_equal(np.asarray(palette, dtype=np.uint8)[frames[0]], truth)
    np.testing.assert_array_equal(decode_png((tmp_path / "result.png").read_bytes()).rgba(), truth)


def test_import_manifest_transaction_journal_and_undo(tmp_path):
    path = CORPUS / "originals/hero_16x16.png"
    result = ingest(tmp_path, path)
    assert result["revision"] == {"before": 0, "after": 1}
    assert result["validation"]["ok"] and result["result"]["accepted"]
    np.testing.assert_array_equal(render(load_project(tmp_path), 0), decode_raster(path)[0][0])
    manifest = sources.read_manifest(tmp_path)
    assert manifest.next_id == 2 and len(manifest.sources) == 1
    source = manifest.sources[0]
    assert source.imported_at == "2026-11-12T12:00:00+09:00"
    assert source.files[0].sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert source.files[0].bytes == len(path.read_bytes())
    assert source.placements[0].revision == 1
    assert history.read_journal(tmp_path)[-1]["actor"] == "test:m6"
    assert history.read_journal(tmp_path)[-1]["ops"][0]["op"] == "import_image"
    execute("undo", tmp_path, preview="none")
    assert not np.any(render(load_project(tmp_path), 0))
    assert sources.read_manifest(tmp_path).sources[0].files == source.files


def test_gate_failure_override_quality_and_tampering(tmp_path):
    execute("new_project", tmp_path, {"width": 32, "height": 32})
    before = (tmp_path / "project.json").read_bytes()
    rejected = ingest(
        tmp_path,
        provenance={"license": "unknown"},
        pipeline={"gates": {"grid_score": [1001, 1001]}},
    )
    assert not rejected["result"]["accepted"] and rejected["result"]["placed"] is None
    assert before == (tmp_path / "project.json").read_bytes()
    assert len(execute("list_sources", tmp_path)["result"]["sources"]) == 1
    accepted = ingest(
        tmp_path,
        source="SRC1",
        on_gate_fail="accept",
        pipeline={"gates": {"grid_score": [1001, 1001]}},
    )
    assert accepted["result"]["accepted"]
    assert {i["rule"] for i in accepted["validation"]["new_issues"]} >= {"Q-SRC-01", "Q-SRC-02"}
    source = execute("get_source", tmp_path, {"id": "SRC1", "include_report": True})["result"]
    assert source["pipeline"]["gates_overridden"] == ["grid_score"]
    assert source["report"]["accepted"] and source["report"]["gates_overridden"] == ["grid_score"]
    original = tmp_path / source["files"][0]["path"]
    original.write_bytes(original.read_bytes() + b"tampered")
    validation = execute("validate", tmp_path)["result"]
    assert not validation["ok"]
    assert any(i["rule"] == "Q-SRC-03" and i["level"] == "error" for i in validation["issues"])
    original.unlink()
    assert any(i["rule"] == "Q-SRC-03" for i in execute("validate", tmp_path)["result"]["issues"])


def test_reject_before_new_project_keeps_inspectable_source(tmp_path):
    rejected = ingest(tmp_path, pipeline={"gates": {"grid_score": [1001, 1001]}})
    assert not rejected["result"]["accepted"] and not (tmp_path / "project.json").exists()
    assert execute("list_sources", tmp_path)["result"]["sources"][0]["id"] == "SRC1"
    accepted = ingest(tmp_path, source="SRC1")
    assert accepted["result"]["accepted"]
    assert sources.read_manifest(tmp_path).next_id == 2


@pytest.mark.parametrize(
    "args,code",
    [
        ({"files": "missing.png"}, "E_INVALID_ARGS"),
        ({"files": "missing.png", "provenance": {"license": ""}}, "E_INVALID_ARGS"),
        ({"files": "missing.png", "provenance": {"license": "unknown"}}, "E_IO"),
        ({"source": "SRC99"}, "E_SOURCE_NOT_FOUND"),
        ({"files": [], "provenance": {"license": "unknown"}}, "E_INVALID_ARGS"),
    ],
)
def test_ingest_errors_are_actionable(tmp_path, args, code):
    with pytest.raises(CyberSpriteError) as caught:
        execute("import_image", tmp_path, args)
    assert caught.value.code == code and caught.value.hint
    assert not (tmp_path / "project.json").exists()


def test_sheet_and_multifile_frames_share_palette(tmp_path):
    sheet = CORPUS / "originals/walker_48x24.png"
    result = ingest(tmp_path / "sheet", sheet, sheet={"cell_w": 12, "cell_h": 24})
    assert result["result"]["placed"]["frames"] == [0, 1, 2, 3]
    p = load_project(tmp_path / "sheet")
    truth = decode_raster(sheet)[0][0]
    for frame in range(4):
        np.testing.assert_array_equal(render(p, frame), truth[:, frame * 12 : (frame + 1) * 12])
    paths = []
    for frame in range(4):
        path = tmp_path / f"frame{frame}.png"
        path.write_bytes(encode_png(truth[:, frame * 12 : (frame + 1) * 12]))
        paths.append(str(path))
    result = ingest(tmp_path / "files", files=paths)
    assert result["result"]["placed"]["frames"] == [0, 1, 2, 3]
    assert len(sources.read_manifest(tmp_path / "files").sources[0].files) == 4
    for frame in range(4):
        np.testing.assert_array_equal(
            render(load_project(tmp_path / "files"), frame), render(p, frame)
        )


def test_existing_layer_transparent_preserves_destination_and_clips(tmp_path):
    execute(
        "new_project", tmp_path, {"width": 4, "height": 4, "palette": ["#00000000", "#ffffffff"]}
    )
    execute(
        "set_pixel",
        tmp_path,
        {"layer": "L1", "frame": 0, "x": 0, "y": 0, "color": 1},
        preview="none",
    )
    pixels = np.zeros((4, 4, 4), dtype=np.uint8)
    pixels[1, 1] = (255, 255, 255, 255)
    image = tmp_path / "input.png"
    image.write_bytes(encode_png(pixels))
    result = ingest(tmp_path, image, target={"mode": "layer", "layer": "L1"})
    p = load_project(tmp_path)
    assert render(p, 0)[0, 0, 3] == render(p, 0)[1, 1, 3] == 255
    assert result["result"]["placed"]["layer"] == "L1"


def test_placement_failure_rolls_back_project_and_manifest_placement(tmp_path):
    ingest(tmp_path)
    before = (tmp_path / "project.json").read_bytes()
    with pytest.raises(CyberSpriteError) as caught:
        ingest(tmp_path, target={"mode": "layer", "layer": "missing"})
    assert caught.value.code == "E_LAYER_NOT_FOUND"
    assert (tmp_path / "project.json").read_bytes() == before
    assert not sources.read_manifest(tmp_path).sources[-1].placements


def test_ingest_atomic_save_failure(tmp_path, monkeypatch):
    ingest(tmp_path)
    before = (tmp_path / "project.json").read_bytes()
    original = history.save_files

    def fail_commit(writes):
        if any(Path(path).name == "project.json" for path, _ in writes):
            raise CyberSpriteError("E_IO", "Injected commit failure.", "Retry.")
        return original(writes)

    monkeypatch.setattr(history, "save_files", fail_commit)
    with pytest.raises(CyberSpriteError):
        ingest(tmp_path)
    assert (tmp_path / "project.json").read_bytes() == before
    assert not sources.read_manifest(tmp_path).sources[-1].placements


def test_cleanup_pixels_region_links_and_positions(tmp_path):
    execute("new_project", tmp_path, {"width": 4, "height": 4, "frames": 2})
    execute(
        "set_pixel",
        tmp_path,
        {"layer": "L1", "frame": 0, "x": 1, "y": 1, "color": 1},
        preview="none",
    )
    execute("link_cel", tmp_path, {"layer": "L1", "source_frame": 0, "frames": [1]}, preview="none")
    result = execute("cleanup_pixels", tmp_path, {"layer": "L1", "frames": "all"}, preview="none")
    assert result["result"]["pixels_written"] == 1
    assert result["result"]["positions"] == [{"frame": 0, "x": 1, "y": 1, "from": 1, "to": 0}]
    assert result["changed"]["linked_frames"] == [0, 1]
    assert not np.any(render(load_project(tmp_path), 1))


def test_integer_hue_comparator_and_perceptual_distance_vectors():
    assert compare_hue((100, 0, 0), (1, 1000, 0)) < 0
    hues = [(10, 1000, 0), (10, 0, 1000), (10, -1000, 0), (10, 0, -1000)]
    for i in range(4):
        for j in range(4):
            assert (compare_hue(hues[i], hues[j]) > 0) - (compare_hue(hues[i], hues[j]) < 0) == (
                i > j
            ) - (i < j)
    assert dist2(rgb_to_oklab_fixed((128, 128, 128)), rgb_to_oklab_fixed((255, 255, 255))) < dist2(
        rgb_to_oklab_fixed((128, 128, 128)), (0, 0, 0)
    )


def test_reports_and_stored_pngs_identical_after_process_restart(tmp_path):
    code = """import sys
from cybersprite.pipeline.decode import decode_raster
from cybersprite.pipeline.runner import run_pipeline
images,_=decode_raster(sys.argv[1])
run_pipeline(images,sys.argv[2],preset='exact')
"""
    for i, seed in enumerate(("1", "451")):
        subprocess.run(
            [sys.executable, "-c", code, str(ORIGINALS[0]), str(tmp_path / str(i))],
            check=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        )
    first = {p.name: p.read_bytes() for p in (tmp_path / "0").iterdir()}
    second = {p.name: p.read_bytes() for p in (tmp_path / "1").iterdir()}
    assert first == second
    images = decode_raster(ORIGINALS[0])[0]
    run_pipeline(images, tmp_path / "0", preset="exact")
    assert first == {p.name: p.read_bytes() for p in (tmp_path / "0").iterdir()}


def test_override_mapping_order_does_not_change_report_bytes(tmp_path):
    images = decode_raster(ORIGINALS[0])[0]
    overrides = [
        {"cleanup": {"min_cluster": 1, "max_passes": 2}, "background": {"mode": "keep"}},
        {"background": {"mode": "keep"}, "cleanup": {"max_passes": 2, "min_cluster": 1}},
    ]
    for i, settings in enumerate(overrides):
        run_pipeline(images, tmp_path / str(i), preset="exact", overrides=settings)
    assert (tmp_path / "0/pipeline_report.json").read_bytes() == (
        tmp_path / "1/pipeline_report.json"
    ).read_bytes()


def test_cli_api_convert_grid_and_errors(tmp_path):
    result = convert(ORIGINALS[0], tmp_path / "output.png", preset="exact")
    assert result["accepted"] and result["verified"]
    assert json.loads(json.dumps(result)) == result
    assert detect_grid(ORIGINALS[0], mode="none")["detected"]
    for call in (
        lambda: convert(ORIGINALS[0], tmp_path / "out.gif"),
        lambda: convert(ORIGINALS[0], tmp_path / "out.png", unknown=True),
        lambda: detect_grid(ORIGINALS[0], unknown=True),
    ):
        with pytest.raises(CyberSpriteError) as caught:
            call()
        assert caught.value.code == "E_INVALID_ARGS"


def test_scenario2_reject_retry_cleanup_export(tmp_path):
    # Generated category (d) awaits M9; original non-pixel input exercises the same flow.
    path = CORPUS / "non_pixel/aa_circles_256.png"
    args = {
        "preset": "photo",
        "pipeline": {
            "grid": {"target_w": 24, "target_h": 24},
            "cleanup": {"min_cluster": 1},
            "gates": {"fidelity": [0, 0]},
        },
    }
    rejected = ingest(tmp_path, path, **args)
    assert not rejected["result"]["accepted"]
    args["pipeline"]["gates"]["fidelity"] = None
    accepted = ingest(tmp_path, source="SRC1", **args)
    assert accepted["result"]["accepted"]
    layer = accepted["result"]["placed"]["layer"]
    cleaned = execute("cleanup_pixels", tmp_path, {"layer": layer}, preview="none")
    assert cleaned["validation"]["ok"]
    assert execute("validate", tmp_path)["result"]["ok"]
    # M5 registers export_image on merge. Here exercise the existing renderer/writer boundary.
    pixels = render(load_project(tmp_path), 0)
    output = tmp_path / "scenario2.png"
    output.write_bytes(encode_png(pixels, compression="stored"))
    np.testing.assert_array_equal(decode_png(output.read_bytes()).rgba(), pixels)
