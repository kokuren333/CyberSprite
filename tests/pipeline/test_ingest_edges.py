import json

import numpy as np
import pytest

from cybersprite.core import history, sources
from cybersprite.core.canonical import load_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.render import render
from cybersprite.formats.png import decode_png, encode_png
from cybersprite.ops import execute


def image_file(tmp_path, pixels):
    path = tmp_path / "input.png"
    path.write_bytes(encode_png(np.asarray(pixels, dtype=np.uint8)))
    return str(path)


def import_args(path, **kwargs):
    return {"files": path, "preset": "exact", "provenance": {"license": "Apache-2.0"}, **kwargs}


def test_capacity_gate_rejects_without_wrapping_and_preserves_diagnostics(tmp_path):
    p = tmp_path / "project"
    execute("new_project", p, {"width": 1, "height": 1})
    colors = ["#00000000"] + [f"#{r:02x}0000ff" for r in range(255)]
    execute("set_palette", p, {"colors": colors}, preview="none")
    path = image_file(tmp_path, [[[0, 255, 0, 255]]])
    before = (p / "project.json").read_bytes()
    result = execute("import_image", p, import_args(path), preview="none")
    assert not result["result"]["accepted"]
    assert (p / "project.json").read_bytes() == before
    report = json.loads((p / result["result"]["report_path"]).read_bytes())
    assert report["capacity_failure"]["palette_size"] == 257
    assert next(g for g in report["gates"] if g["name"] == "palette_budget")["outcome"] == "fail"
    assert decode_png((p / "source/SRC1/result.png").read_bytes()).pixels.dtype == np.uint8
    with pytest.raises(CyberSpriteError) as caught:
        execute(
            "import_image",
            p,
            {"source": "SRC1", "preset": "exact", "on_gate_fail": "accept"},
            preview="none",
        )
    assert caught.value.code == "E_LIMIT_EXCEEDED"
    assert (p / "project.json").read_bytes() == before


def test_validation_budget_override_and_frozen_palette(tmp_path):
    p = tmp_path / "project"
    execute("new_project", p, {"width": 2, "height": 2})
    execute("set_validation", p, {"settings": {"palette_max": 3}}, preview="none")
    path = image_file(tmp_path, [[[255, 0, 0, 255]]])
    rejected = execute("import_image", p, import_args(path), preview="none")
    assert not rejected["result"]["accepted"]
    accepted = execute(
        "import_image",
        p,
        {"source": "SRC1", "preset": "exact", "on_gate_fail": "accept"},
        preview="none",
    )
    assert accepted["result"]["accepted"] and not accepted["validation"]["ok"]
    execute("set_palette_frozen", p, {"frozen": True}, preview="none")
    blue = image_file(tmp_path, [[[0, 0, 255, 255]]])
    result = execute("import_image", p, import_args(blue), preview="none")
    assert not result["result"]["accepted"]
    before = (p / "project.json").read_bytes()
    with pytest.raises(CyberSpriteError) as caught:
        execute(
            "import_image",
            p,
            {"source": "SRC2", "preset": "exact", "on_gate_fail": "accept"},
            preview="none",
        )
    assert caught.value.code == "E_PALETTE_FROZEN"
    assert (p / "project.json").read_bytes() == before


def test_nonzero_transparent_index_png_matches_placed_render(tmp_path):
    p = tmp_path / "project"
    execute(
        "new_project",
        p,
        {"width": 2, "height": 1, "palette": ["#ff0000ff", "#ffffffff"], "transparent_index": 1},
    )
    path = image_file(tmp_path, [[[0, 0, 0, 0], [255, 0, 0, 255]]])
    result = execute("import_image", p, import_args(path), preview="none")
    source_png = decode_png((p / "source/SRC1/result.png").read_bytes()).rgba()
    np.testing.assert_array_equal(source_png, render(load_project(p), 0))
    assert source_png[0, 0].tolist() == [0, 0, 0, 0]
    assert result["result"]["accepted"]


def test_frame_bounds_locked_layers_and_outside_canvas_warning(tmp_path):
    p = tmp_path / "project"
    execute("new_project", p, {"width": 1, "height": 1})
    path = image_file(tmp_path, [[[255, 0, 0, 255]]])
    before = (p / "project.json").read_bytes()
    with pytest.raises(CyberSpriteError) as caught:
        execute(
            "import_image",
            p,
            import_args(path, target={"frame": 1, "add_frames": False}),
            preview="none",
        )
    assert caught.value.code == "E_FRAME_OUT_OF_RANGE"
    assert (p / "project.json").read_bytes() == before
    execute("update_layer", p, {"layer": "L1", "locked": True}, preview="none")
    with pytest.raises(CyberSpriteError) as caught:
        execute(
            "import_image",
            p,
            import_args(path, target={"mode": "layer", "layer": "L1"}),
            preview="none",
        )
    assert caught.value.code == "E_LAYER_LOCKED"
    result = execute("import_image", p, import_args(path, target={"x": 2}), preview="none")
    assert (
        next(g for g in result["result"]["gates"] if g["name"] == "fits_canvas")["outcome"]
        == "warn"
    )
    assert result["result"]["accepted"]


def test_ingest_replay_preserves_source_count_actor_and_warnings(tmp_path, monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_ACTOR", "agent:m6")
    path = image_file(tmp_path, [[[255, 0, 0, 255]]])
    args = import_args(
        path, pipeline={"gates": {"grid_score": [1001, 1001]}}, on_gate_fail="accept"
    )
    p = tmp_path / "project"
    first = execute("import_image", p, args, idempotency_key="once", preview="none")
    second = execute("import_image", p, args, idempotency_key="once", preview="none")
    assert not first["replayed"] and second["replayed"]
    assert first["result"] == second["result"] and first["warnings"] == second["warnings"]
    assert len(sources.read_manifest(p).sources) == 1
    assert history.read_journal(p)[-1]["actor"] == "agent:m6"


def test_new_project_commit_failure_never_leaves_project(tmp_path, monkeypatch):
    path = image_file(tmp_path, [[[255, 0, 0, 255]]])

    def fail_save(_writes):
        raise CyberSpriteError("E_IO", "Injected failure.", "Retry.")

    monkeypatch.setattr(history, "save_files", fail_save)
    p = tmp_path / "project"
    with pytest.raises(CyberSpriteError):
        execute("import_image", p, import_args(path), preview="none")
    assert not (p / "project.json").exists()
    assert not sources.read_manifest(p).sources[0].placements


def test_retry_existing_source_has_correct_delta_and_only_committed_overrides(tmp_path):
    path = image_file(tmp_path, [[[255, 0, 0, 255]]])
    p = tmp_path / "project"
    execute("import_image", p, import_args(path), preview="none")
    args = {
        "source": "SRC1",
        "preset": "exact",
        "on_gate_fail": "accept",
        "pipeline": {"gates": {"grid_score": [1001, 1001]}},
    }
    with pytest.raises(CyberSpriteError):
        execute(
            "import_image",
            p,
            {**args, "target": {"mode": "layer", "layer": "missing"}},
            preview="none",
        )
    assert sources.read_manifest(p).sources[0].pipeline.gates_overridden == []
    result = execute("import_image", p, args, preview="none")
    assert any(i["rule"] == "Q-SRC-01" for i in result["validation"]["new_issues"])
    assert len(sources.read_manifest(p).sources[0].placements) == 2


def test_malformed_pipeline_overrides_return_project_error(tmp_path):
    path = image_file(tmp_path, [[[255, 0, 0, 255]]])
    for pipeline in (
        {"grid": {"unknown": 1}},
        {"downsample": {"method": "bad"}},
        {"cleanup": {"min_cluster": 0}},
        {"gates": {"fidelity": ["a", 1]}},
        {"palette": {"max_colors": 1.5}},
        {"unknown": {}},
        {"grid": None},
    ):
        with pytest.raises(CyberSpriteError) as caught:
            execute(
                "import_image",
                tmp_path / "project",
                import_args(path, pipeline=pipeline),
                preview="none",
            )
        assert caught.value.code == "E_INVALID_ARGS"
