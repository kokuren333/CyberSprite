"""Tail IO, rebuildable replay indexes, and failure/crash boundary vectors."""

import json
from pathlib import Path

import pytest

from cybersprite import ops
from cybersprite.core import history
from cybersprite.core.canonical import load_project
from cybersprite.core.execution import SaveContext, committed_bytes, intent_path, save_context

POINT = {"layer": "L1", "frame": 0, "x": 1, "y": 1, "color": 1}


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def project(tmp_path):
    ops.execute("new_project", tmp_path, {"width": 4, "height": 4})
    return tmp_path


def test_append_does_not_replace_journal_and_tail_pages(project, monkeypatch):
    journal = history.paths(project) / "journal.jsonl"
    before = journal.read_bytes()
    original = history._atomic_write

    def guarded(path, data):
        assert Path(path) != journal, "An ordinary edit must only append to the journal"
        return original(path, data)

    monkeypatch.setattr(history, "_atomic_write", guarded)
    ops.execute("set_pixel", project, POINT, preview="none")
    assert journal.read_bytes().startswith(before)
    assert len(history.read_journal(project, 1)) == 1
    assert history.read_journal(project, after_revision=0)[0]["revision"] == 1
    assert "result" not in history.read_journal(project)[-1]


def test_tail_spans_blocks_and_ignores_torn_line(project):
    journal = history.paths(project) / "journal.jsonl"
    records = [{"revision": i, "data": "x" * 5000} for i in range(50)]
    journal.write_bytes(history.journal_bytes(records) + b'{"torn":')
    assert history.read_journal(project, 3) == records[-3:]
    assert history.read_journal(project, after_revision=46) == records[-3:]
    with history.ProjectLock(project, "test"):
        history.repair_tail(project)
    assert journal.read_bytes() == history.journal_bytes(records)
    journal.write_bytes(b'{"torn":')
    assert history.read_journal(project) == []
    with history.ProjectLock(project, "test"):
        history.repair_tail(project)
    assert journal.read_bytes() == b""


def test_replay_exact_inline_envelope_rebuild_and_window(project):
    first = ops.execute("set_pixel", project, POINT, idempotency_key="one", preview="inline")
    assert first["preview"]["images"]
    journal = history.paths(project) / "journal.jsonl"
    assert b'"images"' not in journal.read_bytes() and b'"result"' not in journal.read_bytes()
    index = history.paths(project) / "idempotency.json"
    index.unlink()
    assert history.replay(project, "one") == {**first, "replayed": True}
    index.write_bytes(b"broken")
    assert history.replay(project, "one") == {**first, "replayed": True}
    with journal.open("ab") as stream:
        stream.write(history.journal_bytes([{"revision": i + 2} for i in range(1000)]))
    assert history.replay(project, "one") is None


def test_old_single_file_replays_original_result(project):
    expected = {"ok": True, "replayed": False, "preview": {"images": ["legacy"]}}
    journal = history.paths(project) / "journal.jsonl"
    journal.write_bytes(
        history.journal_bytes([{"revision": 1, "idempotency_key": "legacy", "result": expected}])
    )
    assert history.replay(project, "legacy") == {**expected, "replayed": True}


def test_undo_redo_keep_compact_restore_targets_without_envelopes(project):
    ops.execute("set_pixel", project, POINT, preview="none")
    for name, expected in (("undo", 0), ("redo", 1)):
        ops.execute(name, project, {}, preview="none")
        entry = history.read_journal(project, 1)[0]
        assert entry["restored_revision"] == expected
        assert "result" not in entry and "replay" not in entry


def test_read_only_ops_do_not_lock(project, monkeypatch):
    def forbidden(*args):
        pytest.fail("A read-only Op attempted to acquire the write lock")

    with history.ProjectLock(project, "other-writer"):
        monkeypatch.setattr(history, "ProjectLock", forbidden)
        for name, args in (("get_info", {}), ("get_history", {}), ("validate", {})):
            assert ops.execute(name, project, args)["ok"]


class InjectedFailure(BaseException):
    pass


@pytest.mark.parametrize("boundary", range(1, 14))
@pytest.mark.parametrize("after", [False, True])
def test_each_atomic_boundary_rolls_back(project, monkeypatch, boundary, after):
    before = files(project)
    original = history._atomic_write
    count = 0
    fired = False

    def fail(path, data):
        nonlocal count, fired
        count += 1
        if count == boundary:
            fired = True
            if after:
                original(path, data)
            raise InjectedFailure()
        return original(path, data)

    monkeypatch.setattr(history, "_atomic_write", fail)
    try:
        ops.execute("set_pixel", project, POINT, idempotency_key="fault", preview="inline")
    except InjectedFailure:
        assert files(project) == before
    assert fired, f"Boundary {boundary} was not exercised"


@pytest.mark.parametrize("after", [False, True])
def test_append_boundary_rolls_back_bytes(project, monkeypatch, after):
    before = files(project)
    original = history.append_journal

    def fail(*args):
        if after:
            original(*args)
        raise InjectedFailure()

    monkeypatch.setattr(history, "append_journal", fail)
    with pytest.raises(InjectedFailure):
        ops.execute("set_pixel", project, POINT, idempotency_key="append")
    assert files(project) == before


@pytest.mark.parametrize("boundary", range(1, 14))
def test_crash_recovery_and_reader_preimage(project, monkeypatch, boundary):
    before = files(project)
    original = history._atomic_write
    rollback = SaveContext.rollback
    count = 0

    def crash(path, data):
        nonlocal count
        original(path, data)
        count += 1
        if count == boundary:
            raise InjectedFailure()

    monkeypatch.setattr(history, "_atomic_write", crash)
    # Leave only durable disk state, as if the process had died before rollback.
    monkeypatch.setattr(SaveContext, "rollback", lambda self: None)
    with pytest.raises(InjectedFailure):
        ops.execute("set_pixel", project, POINT, idempotency_key="crash")
    monkeypatch.setattr(history, "_atomic_write", original)
    monkeypatch.setattr(SaveContext, "rollback", rollback)
    assert load_project(project).revision == 0
    assert history.read_state(project)["undo_stack"] == []
    assert len(history.read_journal(project)) == 1
    with history.ProjectLock(project, "recovery"):
        pass
    assert files(project) == before


def test_statically_imported_writer_shares_context(project):
    # Covers the old monkeypatch gap: aliases imported before MCP initialization.
    from cybersprite.core.history import atomic_write

    target = project / "aliased.txt"
    with pytest.raises(InjectedFailure):
        with save_context(project):
            atomic_write(target, b"temporary")
            raise InjectedFailure()
    assert not target.exists() and not intent_path(project).exists()


def test_reader_sees_old_bytes_during_save(project):
    import contextvars

    target = project / "project.json"
    before = target.read_bytes()
    with save_context(project):
        history.atomic_write(target, b"pending")
        assert contextvars.Context().run(committed_bytes, target, project) == before
    assert target.read_bytes() == b"pending"


def test_reader_sees_missing_source_manifest_as_empty_during_save(project):
    import contextvars

    from cybersprite.core import sources
    from cybersprite.core.models import Sources

    with save_context(project, lock=object()):
        sources.save_manifest(project, Sources(next_id=2))
        assert contextvars.Context().run(sources.read_manifest, project).next_id == 1
    assert sources.read_manifest(project).next_id == 2


def test_rotation_and_retention_preserve_replay_window(project, monkeypatch):
    journal = history.paths(project) / "journal.jsonl"
    monkeypatch.setattr(history, "JOURNAL_SEGMENT_BYTES", 32 * 1024)
    record = {"revision": 0, "padding": "x" * 32}
    journal.write_bytes(history.journal_bytes([record] * 1025))
    ops.execute("set_pixel", project, POINT, idempotency_key="rolled", preview="none")
    assert list(history.paths(project).glob("journal-*.jsonl"))
    assert history.replay(project, "rolled")["replayed"]
    assert history.read_journal(project, 1)[0]["revision"] == 1
    index = json.loads((history.paths(project) / "idempotency.json").read_bytes())
    assert index["position"] == 1001
    assert len(index["keys"]) == 1


def test_unkeyed_index_size_is_bounded_independent_of_edits(project):
    journal = history.paths(project) / "journal.jsonl"
    journal.write_bytes(history.journal_bytes([{"revision": i} for i in range(10000)]))
    ops.execute("set_pixel", project, POINT, preview="none")
    assert (history.paths(project) / "idempotency.json").stat().st_size < 1024


def test_external_baselines_do_not_evict_keys_before_thousand_transactions(project):
    first = ops.execute("set_pixel", project, POINT, idempotency_key="window", preview="none")
    journal = history.paths(project) / "journal.jsonl"
    rows = []
    for i in range(999):
        rows.extend([{"revision": i + 2, "kind": "external"}, {"revision": i + 2, "kind": "tx"}])
    with journal.open("ab") as stream:
        stream.write(history.journal_bytes(rows))
    assert history.replay(project, "window") == {**first, "replayed": True}
    with journal.open("ab") as stream:
        stream.write(history.journal_bytes([{"revision": 1001, "kind": "tx"}]))
    assert history.replay(project, "window") is None


@pytest.mark.parametrize("boundary", range(1, 7))
@pytest.mark.parametrize("after", [False, True])
def test_rotation_write_boundaries_restore_old_segment(project, monkeypatch, boundary, after):
    journal = history.paths(project) / "journal.jsonl"
    journal.write_bytes(history.journal_bytes([{"revision": 0}] * 20))
    monkeypatch.setattr(history, "JOURNAL_SEGMENT_BYTES", 100)
    before = files(project)
    original = history._atomic_write
    count = 0

    def fail(path, data):
        nonlocal count
        count += 1
        if count == boundary:
            if after:
                original(path, data)
            raise InjectedFailure()
        return original(path, data)

    monkeypatch.setattr(history, "_atomic_write", fail)
    with pytest.raises(InjectedFailure):
        with history.ProjectLock(project, "test") as lock, save_context(project, lock=lock):
            history.commit_journal(project, [{"revision": 1, "kind": "tx"}])
    assert files(project) == before
