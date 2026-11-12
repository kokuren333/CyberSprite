"""Import dry runs use the real prepared placement and structural validation."""

from copy import deepcopy

import numpy as np
import pytest

from cybersprite import ops
from cybersprite.core import history
from cybersprite.core.canonical import dumps_project, load_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.formats.png import encode_png


def saved_bytes(project):
    return {
        path.relative_to(project).as_posix(): path.read_bytes()
        for path in sorted(project.rglob("*"))
        if path.is_file() and not path.is_relative_to(project / ".cybersprite/previews/dry")
    }


@pytest.fixture
def setup(tmp_path):
    project = tmp_path / "sprite"
    ops.execute("new_project", project, {"width": 2, "height": 2})
    image = tmp_path / "input.png"
    image.write_bytes(encode_png(np.full((2, 2, 4), 255, dtype=np.uint8)))
    return project, {
        "files": str(image),
        "preset": "exact",
        "provenance": {"license": "unknown"},
        "target": {"mode": "layer", "layer": "L1"},
    }


@pytest.mark.parametrize(
    "condition,code",
    [
        ("locked", "E_LAYER_LOCKED"),
        ("missing", "E_LAYER_NOT_FOUND"),
        ("frame", "E_FRAME_OUT_OF_RANGE"),
        ("limit", "E_LIMIT_EXCEEDED"),
        ("no_layer", "E_INVALID_ARGS"),
        ("no_provenance", "E_INVALID_ARGS"),
        ("structure", "E_INVARIANT"),
        ("ancestor", "E_LAYER_LOCKED"),
    ],
)
def test_dry_run_and_commit_reject_the_same_placement(setup, condition, code, monkeypatch):
    project, args = setup
    if condition == "locked":
        ops.execute("update_layer", project, {"layer": "L1", "locked": True}, preview="none")
    elif condition == "missing":
        args["target"]["layer"] = "missing"
    elif condition == "frame":
        args["target"].update(frame=1, add_frames=False)
    elif condition == "limit":
        args["target"]["frame"] = 4096
    elif condition == "no_layer":
        args["target"].pop("layer")
    elif condition == "no_provenance":
        args.pop("provenance")
    elif condition == "ancestor":
        group = ops.execute(
            "add_layer", project, {"type": "group", "name": "parent"}, preview="none"
        )
        group_id = group["result"]["id"]
        ops.execute("update_layer", project, {"layer": "L1", "parent": group_id}, preview="none")
        ops.execute("update_layer", project, {"layer": group_id, "locked": True}, preview="none")
    elif condition == "structure":
        from cybersprite.ops import ingest

        original = ingest.place

        def broken(ctx, args):
            result = original(ctx, args)
            ctx.project.frames.clear()
            return result

        from dataclasses import replace

        monkeypatch.setitem(
            ops.registry()._ops,
            "import_image",
            replace(ops.registry().get("import_image"), apply=broken),
        )
    before = saved_bytes(project)
    with pytest.raises(CyberSpriteError) as dry:
        ops.execute("import_image", project, args, dry_run=True, preview="none")
    assert dry.value.code == code
    assert saved_bytes(project) == before
    with pytest.raises(CyberSpriteError) as real:
        ops.execute("import_image", project, args, preview="none")
    assert real.value.code == code
    assert (project / "project.json").read_bytes() == before["project.json"]


def test_dry_run_places_once_in_memory_without_lock_or_source(setup, monkeypatch):
    from cybersprite.ops import ingest

    project, args = setup
    args["target"]["frame"] = 2
    before = saved_bytes(project)
    original = ingest.run_pipeline
    calls = []

    def pipeline(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    def no_lock(*args, **kwargs):
        raise AssertionError("Dry run must not acquire a lock.")

    with monkeypatch.context() as patch:
        patch.setattr(ingest, "run_pipeline", pipeline)
        patch.setattr(history, "ProjectLock", no_lock)
        result = ops.execute("import_image", project, args, dry_run=True, preview="none")
    assert calls == [1]
    assert result["would_commit"] and result["checked"] == ["pipeline", "placement", "structure"]
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(result, ops.registry().get("import_image").describe()["outputSchema"])
    assert result["revision"] == {"before": 0, "after": 1}
    assert saved_bytes(project) == before
    assert not (project / "source").exists()
    real = ops.execute("import_image", project, args, preview="none")
    assert real["revision"] == result["revision"]
    assert real["changed"] == result["changed"]
    assert real["validation"] == result["validation"]
    assert len(load_project(project).frames) == 3


def test_new_project_dry_run_does_not_create_canonical(setup):
    project, args = setup
    destination = project.parent / "new"
    result = ops.execute("import_image", destination, args, dry_run=True, preview="none")
    assert result["would_commit"] and "placement" in result["checked"]
    assert not (destination / "project.json").exists()
    assert not (destination / "source").exists()
    real = ops.execute("import_image", destination, args, preview="none")
    assert real["revision"] == result["revision"]


def test_pipeline_only_has_no_commit_claim_or_placement_check(setup):
    project, args = setup
    args.pop("provenance")
    args["target"]["layer"] = "missing"
    args["pipeline_only"] = True
    before = saved_bytes(project)
    result = ops.execute("import_image", project, args, dry_run=True, preview="none")
    assert result["pipeline_accepted"]
    assert result["checked"] == ["pipeline"] and "would_commit" not in result
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(result, ops.registry().get("import_image").describe()["outputSchema"])
    assert saved_bytes(project) == before
    with pytest.raises(CyberSpriteError) as caught:
        ops.execute("import_image", project, args, preview="none")
    assert caught.value.code == "E_INVALID_ARGS"


def test_source_reuse_dry_run_preserves_source_and_history(setup):
    project, args = setup
    real = ops.execute("import_image", project, args, preview="none")
    before = saved_bytes(project)
    result = ops.execute(
        "import_image",
        project,
        {"source": real["result"]["source"], "preset": "exact"},
        dry_run=True,
        preview="none",
    )
    assert result["would_commit"] and saved_bytes(project) == before


def test_transparent_only_baseline_uses_same_palette_override(setup):
    project, args = setup
    project = project.parent / "baseline"
    args = deepcopy(args)
    ops.execute("import_image", project, args, preview="none")
    ops.execute("undo", project, preview="none")
    before = dumps_project(load_project(project))
    dry = ops.execute("import_image", project, args, dry_run=True, preview="none")
    assert dry["would_commit"] and dumps_project(load_project(project)) == before
    assert ops.execute("import_image", project, args, preview="none")["changed"] == dry["changed"]


def test_dry_run_replayed_key_does_not_claim_another_commit(setup):
    project, args = setup
    ops.execute("import_image", project, args, idempotency_key="same", preview="none")
    before = saved_bytes(project)
    result = ops.execute(
        "import_image", project, args, idempotency_key="same", dry_run=True, preview="none"
    )
    assert result["replayed"] and not result["would_commit"]
    assert result["checked"] == ["idempotency"]
    assert saved_bytes(project) == before
