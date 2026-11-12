"""Final export path protection across the three execution surfaces."""

import json
import os

import pytest
from click.testing import CliRunner

from cybersprite import ops
from cybersprite.cli import cli
from cybersprite.core.canonical import dumps_project, load_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.formats.common import export_policy


def protected_bytes(project):
    return {
        path.relative_to(project).as_posix(): path.read_bytes()
        for path in sorted(project.rglob("*"))
        if path.is_file() and not path.is_relative_to(project / ".cybersprite/previews")
    }


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = tmp_path / "sprite"
    ops.execute("new_project", project, {"width": 2, "height": 2, "name": "project"})
    ops.execute(
        "set_pixel",
        project,
        {"layer": "L1", "frame": 0, "x": 0, "y": 0, "color": 1},
        preview="none",
    )
    return project


def rejected(surface, project, out):
    if surface == "cli":
        response = CliRunner().invoke(cli, ["-p", str(project), "export", "image", "--out", out])
        assert response.exit_code != 0, response.output
        return json.loads(response.output)["error"]
    if surface == "mcp":
        pytest.importorskip("mcp")
        from cybersprite.mcp.server import MCPService

        response = (
            MCPService(root=project.parent)
            .call("export_image", {"project": str(project), "out": out})
            .structured_content
        )
        assert not response["ok"], response
        return response["error"]
    pytest.importorskip("starlette")
    from cybersprite.server.app import Service

    with pytest.raises(CyberSpriteError) as caught:
        Service(project.parent).run_op("export_image", project, {"out": out})
    return {"code": caught.value.code, "details": caught.value.details}


@pytest.mark.parametrize("surface", ["cli", "mcp", "gui"])
@pytest.mark.parametrize(
    "kind", ["direct", "template", "case", "hardlink", "symlink", "source", "history"]
)
def test_export_rejection_preserves_canonical_and_history(project, surface, kind):
    out = (
        project
        / {
            "direct": "project.json",
            "template": "{name}.json",
            "case": "PROJECT.JSON",
            "hardlink": "alias.png",
            "symlink": "alias.png",
            "source": "source/new.png",
            "history": ".cybersprite/history/new.png",
        }[kind]
    )
    if kind == "hardlink":
        os.link(project / "project.json", out)
    if kind == "symlink":
        try:
            out.symlink_to(project / "project.json")
        except OSError:
            pytest.skip("Symlink creation requires developer mode or administrator rights.")
    before = protected_bytes(project)
    error = rejected(surface, project, str(out))
    assert error["code"] == "E_PATH_NOT_ALLOWED", error
    assert error["details"]["reason"] == "protected_project_file", error
    assert protected_bytes(project) == before
    assert (project / "project.json").read_bytes().startswith(b"{")
    assert load_project(project).revision == 1


@pytest.mark.parametrize(
    "name,extra",
    [
        ("export_image", {}),
        ("export_sheet", {}),
        ("export_animation", {"format": "gif"}),
        ("export_animation", {"format": "apng"}),
        ("export_palette", {"format": "hex"}),
        ("export_palette", {"format": "png"}),
        ("export_aseprite", {}),
        ("export_tileset", {"tileset": "TS1", "include_empty": True}),
    ],
)
def test_all_export_formats_share_the_guard(project, name, extra):
    if name == "export_tileset":
        ops.execute(
            "add_tileset", project, {"name": "tiles", "tile_w": 1, "tile_h": 1}, preview="none"
        )
    before = protected_bytes(project)
    with export_policy(project.parent), pytest.raises(CyberSpriteError) as caught:
        ops.execute(name, project, {"out": str(project / "project.json"), **extra})
    assert caught.value.code == "E_PATH_NOT_ALLOWED"
    assert protected_bytes(project) == before


@pytest.mark.parametrize("name", ["export_sheet", "export_tileset"])
def test_data_destination_checked_before_any_output(project, name):
    if name == "export_tileset":
        ops.execute(
            "add_tileset", project, {"name": "tiles", "tile_w": 1, "tile_h": 1}, preview="none"
        )
    out = project.parent / "existing.png"
    out.write_bytes(b"existing output")
    before = protected_bytes(project)
    args = {"out": str(out), "data_out": str(project / "project.json")}
    if name == "export_tileset":
        args.update(tileset="TS1", include_empty=True)
    with export_policy(project.parent), pytest.raises(CyberSpriteError):
        ops.execute(name, project, args)
    assert out.read_bytes() == b"existing output"
    assert protected_bytes(project) == before


def test_all_expanded_frame_paths_checked_before_any_output(project):
    ops.execute("add_frame", project, {"count": 1}, preview="none")
    out = project / "frame-{frame}.png"
    os.link(project / "project.json", project / "frame-1.png")
    before = protected_bytes(project)
    with export_policy(project.parent), pytest.raises(CyberSpriteError):
        ops.execute("export_image", project, {"out": str(out)})
    assert protected_bytes(project) == before
    assert not (project / "frame-0.png").exists()


def test_guard_runs_before_external_history_bookkeeping(project):
    # An external edit must not cause an otherwise refused export to update history.
    model = load_project(project)
    model.name = "external"
    (project / "project.json").write_bytes(dumps_project(model))
    before = protected_bytes(project)
    with export_policy(project.parent), pytest.raises(CyberSpriteError):
        ops.execute("export_image", project, {"out": str(project / "project.json")})
    assert protected_bytes(project) == before


def test_hardlink_to_journal_is_protected(project):
    journal = project / ".cybersprite/history/journal.jsonl"
    alias = project.parent / "journal.png"
    os.link(journal, alias)
    before = protected_bytes(project)
    with export_policy(project.parent), pytest.raises(CyberSpriteError) as caught:
        ops.execute("export_image", project, {"out": str(alias)})
    assert caught.value.code == "E_PATH_NOT_ALLOWED"
    assert protected_bytes(project) == before


def test_allowed_export_subdirectory(project):
    out = project / "exports" / "image.png"
    with export_policy(project.parent):
        result = ops.execute("export_image", project, {"out": str(out)})
    assert result["result"]["verified"] and out.read_bytes().startswith(b"\x89PNG")
