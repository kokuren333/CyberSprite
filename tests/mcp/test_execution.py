"""Deadline and serialization failures cannot leave committed project changes."""

import pytest

pytest.importorskip("mcp.server")

from cybersprite import ops  # noqa: E402
from cybersprite.core import history  # noqa: E402
from cybersprite.mcp import execution, server  # noqa: E402
from cybersprite.mcp.server import MCPService  # noqa: E402


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("phase", ["before", "after", "preview"])
def test_timeout_rolls_back_all_core_writes(tmp_path, monkeypatch, phase):
    service = MCPService(root=tmp_path)
    service.call("new_project", {"project": "p", "width": 4, "height": 4})
    before = snapshot(tmp_path / "p")
    original = ops.execute
    clock = [0]
    monkeypatch.setattr(execution, "monotonic_ns", lambda: clock[0])

    def slow(*args, **kwargs):
        if phase == "before":
            clock[0] = 60_000_000_000
        result = original(*args, **kwargs)
        if phase == "after":
            clock[0] = 60_000_000_000
        return result

    if phase == "preview":
        import cybersprite.ops.previews as previews

        original_preview = previews.previews

        def slow_preview(*args, **kwargs):
            result = original_preview(*args, **kwargs)
            clock[0] = 60_000_000_000
            return result

        monkeypatch.setattr(previews, "previews", slow_preview)
    monkeypatch.setattr(ops, "execute", slow)
    monkeypatch.setitem(server.TIMEOUTS, "set_pixel", 1)
    result = service.call(
        "set_pixel", {"project": "p", "layer": "L1", "frame": 0, "x": 0, "y": 0, "color": 1}
    )
    assert result.structured_content["error"]["code"] == "E_TIMEOUT"
    assert snapshot(tmp_path / "p") == before
    assert execution._active.get() is None


def test_text_limit_is_utf8_bytes_and_rolls_back(tmp_path, monkeypatch):
    service = MCPService(root=tmp_path)
    service.call("new_project", {"project": "p", "width": 4, "height": 4})
    before = snapshot(tmp_path / "p")
    monkeypatch.setattr(server, "TEXT_LIMIT", 2000)
    result = service.call("set_project_meta", {"project": "p", "user_data": {"text": "あ" * 2000}})
    # get_info has a large user payload only in layers; force a result after a real commit.
    if not result.is_error:
        original = ops.execute

        def large(*args, **kwargs):
            value = original(*args, **kwargs)
            value["warnings"] = [{"message": "あ" * 2000}]
            return value

        monkeypatch.setattr(ops, "execute", large)
        before = snapshot(tmp_path / "p")
        result = service.call(
            "set_pixel", {"project": "p", "layer": "L1", "frame": 0, "x": 0, "y": 0, "color": 1}
        )
    assert result.structured_content["error"]["code"] == "E_LIMIT_EXCEEDED"
    assert snapshot(tmp_path / "p") == before


def test_core_cli_execution_still_works_after_mcp_request(tmp_path):
    service = MCPService(root=tmp_path)
    service.call("new_project", {"project": "p", "width": 2, "height": 2})
    value = ops.execute(
        "set_pixel",
        tmp_path / "p",
        {"layer": "L1", "frame": 0, "x": 0, "y": 0, "color": 1},
        preview="none",
    )
    assert value["ok"]
    assert not (tmp_path / "p/.cybersprite/lock").exists()
    assert history.read_state(tmp_path / "p")["undo_stack"] == [0]


def test_queries_do_not_lock_or_install_runtime_hooks(tmp_path, monkeypatch):
    import sys

    service = MCPService(root=tmp_path)
    assert not service.call("new_project", {"project": "p", "width": 2, "height": 2}).is_error
    writer = history.atomic_write
    trace = sys.gettrace()

    def forbidden(*args):
        pytest.fail("MCP query acquired a write lock")

    with history.ProjectLock(tmp_path / "p", "other"):
        monkeypatch.setattr(history, "ProjectLock", forbidden)
        assert not service.call("validate", {"project": "p"}).is_error
    assert history.atomic_write is writer
    assert sys.gettrace() is trace
