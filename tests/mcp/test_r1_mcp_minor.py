"""Compact contract and schema-driven path regression tests."""

import json
from dataclasses import replace

import pytest
from pydantic import Field, create_model

pytest.importorskip("mcp.server")
from jsonschema import Draft202012Validator  # noqa: E402

from cybersprite import ops  # noqa: E402
from cybersprite.core.errors import CyberSpriteError  # noqa: E402
from cybersprite.core.models import Model  # noqa: E402
from cybersprite.core.registry import Registry  # noqa: E402
from cybersprite.mcp.paths import PathPolicy  # noqa: E402
from cybersprite.mcp.result_paths import response_schema  # noqa: E402
from cybersprite.mcp.server import MCPService  # noqa: E402


def test_contract_size_and_local_references(tmp_path):
    # Keep self-contained schemas: external references break offline MCP clients.
    sizes = {}
    for profile in ("standard", "minimal"):
        service = MCPService(root=tmp_path, profile=profile)
        tools = [tool.model_dump(by_alias=True, exclude_none=True) for tool in service.tools()]
        sizes[profile] = len(json.dumps(tools).encode())
        for tool in tools:
            Draft202012Validator.check_schema(tool["inputSchema"])
            Draft202012Validator.check_schema(tool["outputSchema"])
    assert sizes["standard"] <= 100_000
    assert sizes["minimal"] < 25_000


def test_layer_reference_candidates_and_undeclared_argument(tmp_path):
    service = MCPService(root=tmp_path)
    assert not service.call(
        "new_project", {"project": "m.csprite", "width": 2, "height": 2}
    ).is_error
    result = service.call(
        "get_pixels", {"project": "m.csprite", "layer": "missing", "frame": 0}
    ).structured_content
    candidates = result["error"]["details"]["candidates"]
    assert candidates == [{"id": "L1", "path": "Layer 1"}]
    result = service.call("get_info", {"project": "m.csprite", "typo": 1}).structured_content
    assert result["error"]["details"]["arguments"] == ["typo"]
    assert "typo" in result["error"]["message"]


def test_schema_paths_preserve_nonfile_strings_and_metadata(tmp_path):
    inner = create_model(
        "Paths",
        __base__=Model,
        file=(str, Field(json_schema_extra={"format": "path"})),
        path=(str, ...),
    )
    model = create_model(
        "Reply",
        __base__=Model,
        nested=(inner | None, None),
        paths=(list[str], Field(json_schema_extra={"description": "logical paths"})),
    )
    value = {"nested": {"file": "image.png", "path": "Group/Layer"}, "paths": ["a/b"]}
    result = PathPolicy(tmp_path).result(value, tmp_path / "p", model.model_json_schema())
    assert result == {"nested": {"file": "p/image.png", "path": "Group/Layer"}, "paths": ["a/b"]}
    value = {"project": str(tmp_path / "p"), "result": {"source": "SRC1"}}
    result = PathPolicy(tmp_path).result(
        value, tmp_path / "p", response_schema(ops.registry().get("import_aseprite"))
    )
    assert result["result"]["source"] == "SRC1"
    value = {
        "result": {"sources": {"sources": [{"files": [{"path": "source/SRC1/original.png"}]}]}}
    }
    result = PathPolicy(tmp_path).result(
        value, tmp_path / "p", response_schema(ops.registry().get("get_info"))
    )
    assert (
        result["result"]["sources"]["sources"][0]["files"][0]["path"]
        == "p/source/SRC1/original.png"
    )


def test_compact_declarations_do_not_weaken_nested_path_checks(tmp_path):
    nested = create_model(
        "PluginNested",
        __base__=Model,
        input=(str, Field(json_schema_extra={"x-cybersprite-path": "input"})),
        metadata=(dict, ...),
    )
    args = create_model("PluginArgs", __base__=Model, nested=(nested, ...))
    registry = Registry()
    registry.register(
        replace(ops.registry().get("get_info"), name="plugin_read", args=args, provider="example")
    )
    service = MCPService(root=tmp_path, registry=registry, allow_plugin_op=["plugin_read"])
    op = service.exposed["plugin_read"]
    assert service.contracts[op.name]["inputSchema"]["properties"]["nested"] == {"type": "object"}
    with pytest.raises(CyberSpriteError, match="outside"):
        service._arguments(op, {"project": "p", "nested": {"input": "../outside", "metadata": {}}})
