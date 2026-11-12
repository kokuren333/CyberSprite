"""Transaction failures, history lifecycles, locks and seeded sequence properties."""

import gzip
import json
import os
import random
from hashlib import sha256
from threading import Event

import pytest

from cybersprite.core import history
from cybersprite.core.canonical import dumps_project, load_project, loads_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.models import Model
from cybersprite.core.quality import report, validation_delta
from cybersprite.core.registry import EmptyResult, Op
from cybersprite.core.validation import check_structure
from cybersprite.ops import execute, registry

POINT = {"layer": "L1", "frame": 0, "x": 1, "y": 1, "color": 1}


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_NOW", "2026-11-12T00:00:00+00:00")
    p = tmp_path / "tx.csprite"
    execute("new_project", p, {"width": 8, "height": 8})
    return p


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_mid_failure_byte_identical_and_op_index(project):
    before = files(project)
    with pytest.raises(CyberSpriteError) as error:
        execute(
            "apply_ops",
            project,
            {
                "ops": [
                    {"op": "set_pixel", "args": POINT},
                    {"op": "set_pixel", "args": {**POINT, "color": 255}},
                ]
            },
        )
    assert error.value.code == "E_INDEX_OUT_OF_RANGE" and error.value.op_index == 1
    assert files(project) == before


def test_no_op_idempotency_and_conflict_order(project):
    first = execute("set_pixel", project, POINT, idempotency_key="pixel-1")
    before = files(project)
    second = execute("set_pixel", project, {**POINT, "color": 2}, idempotency_key="pixel-1")
    assert second == {**first, "replayed": True}
    assert files(project) == before
    assert execute("set_pixel", project, POINT, preview="none")["no_op"]
    assert files(project) == before
    with pytest.raises(CyberSpriteError) as error:
        execute("set_pixel", project, POINT, expect_revision=0, idempotency_key="pixel-1")
    assert error.value.code == "E_REVISION_CONFLICT"
    assert error.value.details["current_revision"] == 1


def test_dry_run_writes_only_dry_previews_and_takes_no_lock(project, monkeypatch):
    before = files(project)

    def no_lock(*_):
        pytest.fail("Dry run must not acquire a lock")

    monkeypatch.setattr(history, "ProjectLock", no_lock)
    result = execute("set_pixel", project, POINT, dry_run=True)
    assert result["would_commit"] and result["dry_run"]
    assert result["revision"] == {"before": 0, "after": 1}
    after = files(project)
    assert all(after[name] == data for name, data in before.items())
    assert all(
        name.startswith(".cybersprite/previews/dry/") for name in after.keys() - before.keys()
    )
    execute("set_pixel", project, {**POINT, "color": 0}, dry_run=True, preview="none")
    assert files(project) == after


def test_history_undo_redo_external_edit_and_missing_snapshot(project):
    initial = load_project(project)
    with pytest.raises(CyberSpriteError) as error:
        execute("undo", project, {}, preview="none")
    assert error.value.code == "E_NOTHING_TO_UNDO"
    execute("set_pixel", project, POINT, preview="none")
    painted = load_project(project)
    assert execute("undo", project, {}, preview="none")["revision"]["after"] == 2
    restored = load_project(project)
    restored.revision = initial.revision
    assert dumps_project(restored) == dumps_project(initial)
    execute("redo", project, {}, preview="none")
    restored = load_project(project)
    restored.revision = painted.revision
    assert restored == painted
    state = history.read_state(project)
    history.snapshot_path(project, state["undo_stack"][-1]).unlink()
    with pytest.raises(CyberSpriteError) as error:
        execute("undo", project, {}, preview="none")
    assert error.value.code == "E_HISTORY_UNAVAILABLE"
    edited = load_project(project)
    edited.name = "External change"
    (project / "project.json").write_bytes(dumps_project(edited))
    result = execute("get_history", project, {})["result"]
    assert result["entries"][0]["kind"] == "external"
    assert not result["can_undo"] and not result["can_redo"]
    assert (
        history.read_state(project)["last_saved_sha256"]
        == sha256((project / "project.json").read_bytes()).hexdigest()
    )


def test_multi_step_undo_redo_and_branch_clears_redo(project):
    for i in range(3):
        execute("set_pixel", project, {**POINT, "x": i}, preview="none")
    painted = load_project(project)
    execute("undo", project, {"steps": 3}, preview="none")
    assert not load_project(project).layers[0].cels
    execute("redo", project, {"steps": 3}, preview="none")
    after = load_project(project)
    after.revision = painted.revision
    assert after == painted
    execute("undo", project, {}, preview="none")
    execute("set_pixel", project, {**POINT, "x": 7}, preview="none")
    with pytest.raises(CyberSpriteError) as error:
        execute("redo", project, {}, preview="none")
    assert error.value.code == "E_NOTHING_TO_REDO"


def test_lock_contention_stale_and_refresh(project, monkeypatch):
    monkeypatch.setattr(history, "LOCK_WAIT_SECONDS", 0)
    with history.ProjectLock(project, "gui"):
        metadata = json.loads((project / ".cybersprite/lock").read_bytes())
        assert metadata["actor"] == "gui" and metadata["pid"] == os.getpid()
        with pytest.raises(CyberSpriteError) as error:
            execute("set_pixel", project, POINT, preview="none")
        assert error.value.code == "E_LOCKED"
    lock = project / ".cybersprite/lock"
    lock.write_text('{"pid": 0, "actor": "crashed"}', encoding="utf-8")
    os.utime(lock, ns=(1, 1))
    assert execute("set_pixel", project, POINT, preview="none")["ok"]
    monkeypatch.setattr(history, "LOCK_REFRESH_SECONDS", 1)
    with history.ProjectLock(project, "gui"):
        old = lock.stat().st_mtime_ns
        Event().wait(2)
        assert lock.stat().st_mtime_ns > old
    assert not lock.exists()


def test_atomic_replace_retry_and_commit_rollback(project, monkeypatch):
    original = history.os.replace
    attempts = []

    def retry(src, dst):
        attempts.append(1)
        if len(attempts) == 1:
            raise PermissionError("Temporarily held open")
        return original(src, dst)

    monkeypatch.setattr(history.os, "replace", retry)
    assert execute("set_pixel", project, POINT, preview="none")["ok"]
    assert len(attempts) >= 2
    before = files(project)

    def broken(src, dst):
        if str(dst).endswith("project.json"):
            raise PermissionError("Held open")
        return original(src, dst)

    monkeypatch.setattr(history.os, "replace", broken)
    with pytest.raises(CyberSpriteError) as error:
        execute("set_pixel", project, {**POINT, "color": 2}, preview="none")
    assert error.value.code == "E_IO"
    assert files(project) == before


def test_plugin_invariant_error_rollback(project):
    name = "test_break_invariant"

    def broken(ctx, args):
        ctx.project.frames = []
        return {}

    if name not in [op.name for op in registry().all()]:
        registry().register(Op(name, Model, broken, EmptyResult, provider="test"))
    before = files(project)
    with pytest.raises(CyberSpriteError) as error:
        execute(name, project, {}, preview="none")
    assert error.value.code == "E_INVARIANT"
    assert files(project) == before
    registry()._ops.pop(name)


def test_deterministic_snapshots_retention_actor_and_large_args(project, monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_ACTOR", "agent:test-client")
    execute("set_pixel", project, POINT, preview="none")
    p = load_project(project)
    data = history.snapshot_bytes(p)
    assert data == history.snapshot_bytes(p) and data[4:8] == b"\0\0\0\0" and data[9] == 255
    assert gzip.decompress(data) == dumps_project(p)
    entry = history.read_journal(project)[-1]
    assert entry["actor"] == "agent:test-client" and entry["time"] == "2026-11-12T00:00:00+00:00"
    entry["ops"] = [{"op": "draw_rows", "args": {"rows": ["00" * 600000]}}]
    compact = history.compact_entry(entry)
    assert len(history.journal_bytes([compact])) < 1024 * 1024
    assert "sha256" in compact["ops"][0]["args"]
    monkeypatch.setattr(history, "SNAPSHOT_COUNT", 1)
    history.retain(project)
    assert len(list((history.paths(project) / "snapshots").glob("*.gz"))) == 1


def test_seeded_sequences_invariants_undo_and_full_delta(project):
    rng = random.Random(201)
    for _ in range(40):
        before = load_project(project)
        old_report = report(before, root=project)
        frames = len(before.frames)
        name = rng.choice(
            [
                "set_pixel",
                "line",
                "rect",
                "fill",
                "add_frame",
                "delete_frames",
                "set_frame_duration",
                "reverse_frames",
            ]
        )
        draw = {"layer": "L1", "frame": rng.randrange(frames), "color": rng.randrange(1, 5)}
        if name == "set_pixel":
            args = {**draw, "x": rng.randrange(-1, 9), "y": rng.randrange(-1, 9)}
        elif name == "line":
            args = {**draw, **{key: rng.randrange(8) for key in ("x0", "y0", "x1", "y1")}}
        elif name == "rect":
            args = {
                **draw,
                "x": rng.randrange(8),
                "y": rng.randrange(8),
                "w": rng.randrange(1, 5),
                "h": rng.randrange(1, 5),
            }
        elif name == "fill":
            args = {**draw, "x": rng.randrange(8), "y": rng.randrange(8)}
        elif name == "add_frame":
            args = {"at": rng.randrange(frames + 1), "cels": rng.choice(["empty", "copy", "link"])}
        elif name == "delete_frames" and frames > 1:
            args = {"frames": rng.randrange(frames)}
        elif name == "reverse_frames":
            args = {"from": 0, "to": frames - 1}
        else:
            name, args = "set_frame_duration", {"frames": 0, "duration_ms": rng.randrange(1, 500)}
        result = execute(name, project, args, preview="none")
        after = load_project(project)
        assert not check_structure(after)
        assert dumps_project(loads_project(dumps_project(after))) == dumps_project(after)
        assert result["validation"] == validation_delta(old_report, report(after, root=project))
        if not result["no_op"]:
            execute("undo", project, {}, preview="none")
            restored = load_project(project)
            restored.revision = before.revision
            assert restored == before
            execute("redo", project, {}, preview="none")


def test_replay_only_searches_latest_thousand(project):
    original = execute("set_pixel", project, POINT, idempotency_key="old", preview="none")
    journal = history.read_journal(project)
    journal += [{**journal[-1], "idempotency_key": None, "result": None} for _ in range(1000)]
    history.atomic_write(history.paths(project) / "journal.jsonl", history.journal_bytes(journal))
    second = execute(
        "set_pixel", project, {**POINT, "color": 2}, idempotency_key="old", preview="none"
    )
    assert not second["replayed"] and second["revision"]["after"] > original["revision"]["after"]


def test_lock_metadata_write_failure_cleans_own_lock(project, monkeypatch):
    def broken(_fd):
        raise OSError("Cannot flush lock metadata")

    monkeypatch.setattr(history.os, "fsync", broken)
    with pytest.raises(CyberSpriteError) as error:
        execute("set_pixel", project, POINT, preview="none")
    assert error.value.code == "E_IO"
    assert not (project / ".cybersprite/lock").exists()


def test_result_journal_failure_rolls_back_project_history_and_previews(project, monkeypatch):
    before = files(project)
    original = history.atomic_write
    journal_writes = 0

    def fail_second_journal(path, data):
        nonlocal journal_writes
        if path.name == "journal.jsonl":
            journal_writes += 1
            if journal_writes == 2:
                raise CyberSpriteError("E_IO", "Injected result journal failure", "Retry")
        return original(path, data)

    monkeypatch.setattr(history, "atomic_write", fail_second_journal)
    with pytest.raises(CyberSpriteError) as error:
        execute("set_pixel", project, POINT)
    assert error.value.code == "E_IO"
    assert files(project) == before


def test_preview_failure_is_success_and_replays_stored_warning(project, monkeypatch):
    import importlib

    module = importlib.import_module("cybersprite.ops.previews")

    def broken(*_):
        raise CyberSpriteError("E_IO", "Injected PNG writer failure", "Retry preview")

    monkeypatch.setattr(module, "encode_png", broken)
    result = execute("set_pixel", project, POINT, idempotency_key="preview-failure")
    assert (
        result["revision"]["after"] == 1
        and result["warnings"][0]["code"] == "W_PREVIEW_UNAVAILABLE"
    )
    assert execute("set_pixel", project, POINT, idempotency_key="preview-failure") == {
        **result,
        "replayed": True,
    }


def test_preview_retention_uses_revision_groups(project):
    folder = project / ".cybersprite/previews"
    folder.mkdir()
    for revision in range(101):
        (folder / f"r{revision:06d}_f0.png").write_bytes(b"derived")
    history.retain_previews(project)
    assert not (folder / "r000000_f0.png").exists()
    assert len(list(folder.glob("*.png"))) == 100
