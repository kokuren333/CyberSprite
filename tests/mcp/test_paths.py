"""Real filesystem escape attempts, including Windows junctions."""

import os
import subprocess

import pytest
from pydantic import Field, create_model

pytest.importorskip("mcp.server")

from cybersprite.core.errors import CyberSpriteError  # noqa: E402
from cybersprite.core.models import Model  # noqa: E402
from cybersprite.mcp.paths import PathPolicy  # noqa: E402
from cybersprite.mcp.server import MCPService  # noqa: E402


def test_project_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    service = MCPService(root=root)
    for path in ["../escape.csprite", str(tmp_path / "outside.csprite"), "../root-other/p.csprite"]:
        result = service.call("new_project", {"project": path, "width": 1, "height": 1})
        assert result.is_error
        assert result.structured_content["error"]["code"] == "E_PATH_NOT_ALLOWED"
    assert not (tmp_path / "outside.csprite").exists()


@pytest.mark.parametrize("tool,field", [("new_project", "palette"), ("load_palette", "source")])
def test_input_escape_and_batch(tmp_path, tool, field):
    root = tmp_path / "root"
    root.mkdir()
    service = MCPService(root=root, profile="minimal")
    assert not service.call("new_project", {"project": "p", "width": 1, "height": 1}).is_error
    if tool == "new_project":
        result = service.call(
            tool, {"project": "p2", "width": 1, "height": 1, field: "../outside.hex"}
        )
    else:
        result = service.call(
            "apply_ops", {"project": "p", "ops": [{"op": tool, "args": {field: "../outside.hex"}}]}
        )
    assert result.structured_content["error"]["code"] == "E_PATH_NOT_ALLOWED"


def test_nested_path_metadata_for_inputs_outputs_and_arrays(tmp_path):
    path = Field(..., json_schema_extra={"x-cybersprite-path": "input"})
    nested = create_model("Nested", __base__=Model, files=(list[str], path))
    args = create_model(
        "Args",
        __base__=Model,
        nested=(nested, ...),
        out=(str, Field(..., json_schema_extra={"x-cybersprite-path": "output"})),
    )
    policy = PathPolicy(tmp_path)
    value = policy.arguments(
        {"nested": {"files": ["a", "b"]}, "out": "c"}, args.model_json_schema()
    )
    assert value == {
        "nested": {"files": [str(tmp_path / "a"), str(tmp_path / "b")]},
        "out": str(tmp_path / "c"),
    }
    for data in [{"nested": {"files": ["../bad"]}}, {"out": "../bad"}]:
        with pytest.raises(CyberSpriteError, match="outside"):
            policy.arguments(data, args.model_json_schema())


def test_allow_dir_and_relative_result(tmp_path):
    root, extra = tmp_path / "root", tmp_path / "extra"
    root.mkdir()
    extra.mkdir()
    service = MCPService(root=root, allow_dir=[extra])
    result = service.call("new_project", {"project": str(extra / "p"), "width": 1, "height": 1})
    assert not result.is_error
    assert result.structured_content["project"] == "../extra/p"
    assert PathPolicy(root, ["../extra"]).resolve(extra / "q") == extra / "q"
    if os.name == "nt":
        assert PathPolicy(root).resolve(str(root).swapcase()) == root


def test_paths_inside_union_and_file_symlink(tmp_path):
    nested = create_model(
        "UnionPath",
        __base__=Model,
        file=(str, Field(..., json_schema_extra={"x-cybersprite-path": "input"})),
    )
    args = create_model("UnionArgs", __base__=Model, target=(nested | None, None))
    with pytest.raises(CyberSpriteError):
        PathPolicy(tmp_path).arguments({"target": {"file": "../outside"}}, args.model_json_schema())
    # Metadata applies to each member of a string-or-array field.
    files = create_model(
        "FilesArgs",
        __base__=Model,
        files=(str | list[str], Field(..., json_schema_extra={"x-cybersprite-path": "input"})),
    )
    with pytest.raises(CyberSpriteError):
        PathPolicy(tmp_path).arguments({"files": ["ok", "../outside"]}, files.model_json_schema())


@pytest.mark.parametrize("junction", [False, True])
def test_links_and_derived_paths(tmp_path, junction):
    root, outside = tmp_path / "root", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "link"
    if junction:
        if os.name != "nt":
            pytest.skip("Directory junctions are a Windows facility")
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True
        )
        if result.returncode:
            pytest.skip("Directory junction creation is not permitted")
    else:
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            pytest.skip("Symlink creation requires platform permission")
    try:
        service = MCPService(root=root)
        result = service.call("new_project", {"project": "link/p", "width": 1, "height": 1})
        assert result.structured_content["error"]["code"] == "E_PATH_NOT_ALLOWED"
        assert not list(outside.iterdir())
        # A project-local derived directory must not become an escape route.
        project = root / "p"
        project.mkdir()
        link.rename(project / ".cybersprite")
        result = service.call("new_project", {"project": "p", "width": 1, "height": 1})
        assert result.structured_content["error"]["code"] == "E_PATH_NOT_ALLOWED"
    finally:
        target = root / "p/.cybersprite" if (root / "p/.cybersprite").exists() else link
        if target.is_symlink():
            target.unlink()
        elif target.exists():
            target.rmdir()  # Remove only the junction, never its target.
