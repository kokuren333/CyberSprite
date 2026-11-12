"""Parsed GUI models are reusable only while the actual canonical bytes agree."""

import base64
import os
from types import SimpleNamespace

import pytest

pytest.importorskip("starlette")

from cybersprite.core.canonical import load_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.quality import report
from cybersprite.core.render import render
from cybersprite.ops import execute
from cybersprite.server.app import Service


def test_gui_model_cache_checks_bytes_even_with_same_timestamp_and_size(tmp_path):
    project = tmp_path / "gui.csprite"
    execute("new_project", project, {"width": 4, "height": 4})
    execute(
        "set_pixel",
        project,
        {"layer": "L1", "frame": 0, "x": 0, "y": 0, "color": 1},
        preview="none",
    )
    service = Service(tmp_path)
    session = SimpleNamespace(project=project)
    first = service.read_project(project)
    assert service.read_project(project) is first
    original_stat = (project / "project.json").stat()
    report(first)
    execute(
        "set_pixel",
        project,
        {"layer": "L1", "frame": 0, "x": 0, "y": 0, "color": 2},
        preview="none",
    )
    os.utime(project / "project.json", ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    assert (project / "project.json").stat().st_size == original_stat.st_size
    actual = service.dispatch(session, "render.frame", {"frame": 0})
    expected = render(load_project(project)).tobytes()
    assert base64.b64decode(actual["frames"][0]["rgba"]) == expected
    assert service.read_project(project) is not first
    for frame in (-1, 1, True):
        with pytest.raises(CyberSpriteError, match="outside the project"):
            service.dispatch(session, "render.frame", {"frame": frame})


def test_gui_region_uses_current_core_render(tmp_path):
    project = tmp_path / "crop.csprite"
    execute("new_project", project, {"width": 4, "height": 4})
    execute(
        "set_pixel",
        project,
        {"layer": "L1", "frame": 0, "x": 1, "y": 1, "color": 1},
        preview="none",
    )
    service = Service(tmp_path)
    actual = service.dispatch(
        SimpleNamespace(project=project),
        "render.frame",
        {
            "frame": 0,
            "region": {"x": 1, "y": 1, "w": 1, "h": 1},
        },
    )
    expected = render(load_project(project), 0, {"crop": {"x": 1, "y": 1, "w": 1, "h": 1}})
    assert base64.b64decode(actual["frames"][0]["rgba"]) == expected.tobytes()


def test_gui_cache_preserves_missing_project_error(tmp_path):
    service = Service(tmp_path)
    with pytest.raises(CyberSpriteError) as error:
        service.read_project(tmp_path / "missing.csprite")
    assert error.value.code == "E_PROJECT_NOT_FOUND"
