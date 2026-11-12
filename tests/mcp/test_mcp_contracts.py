"""Registry contracts exercised through a real SDK client."""

import asyncio
import base64
import json
from dataclasses import replace

import pytest

pytest.importorskip("mcp.server")
from jsonschema import Draft202012Validator  # noqa: E402
from mcp import Client  # noqa: E402
from mcp.shared.exceptions import MCPError  # noqa: E402
from mcp.types import Implementation  # noqa: E402

from cybersprite import ops  # noqa: E402
from cybersprite.core.canonical import load_project  # noqa: E402
from cybersprite.core.registry import Registry  # noqa: E402
from cybersprite.mcp.contracts import MINIMAL, ORDER  # noqa: E402
from cybersprite.mcp.server import MCPService, create_server  # noqa: E402


def test_all_tool_contracts(tmp_path):
    async def run():
        async with Client(create_server(root=tmp_path)) as client:
            tools = (await client.list_tools()).tools
            assert [tool.name for tool in tools] == [
                name
                for name in ORDER
                if name in {op.name for op in ops.registry().all()}
                and name not in {"list_generators", "generate_image"}
            ]
            for tool in tools:
                op = ops.registry().get(tool.name)
                assert tool.title and tool.description
                assert tool.input_schema["additionalProperties"] is False
                assert "project" in tool.input_schema["required"]
                assert tool.input_schema["properties"]["project"]["x-cybersprite-path"] == "project"
                assert tool.output_schema and "oneOf" in tool.output_schema
                Draft202012Validator.check_schema(tool.input_schema)
                Draft202012Validator.check_schema(tool.output_schema)
                assert (
                    tool.annotations.model_dump(by_alias=True, exclude_none=True) == op.annotations
                )
                if op.kind == "mutate":
                    assert {"expect_revision", "idempotency_key", "dry_run", "preview"} <= set(
                        tool.input_schema["properties"]
                    )

    asyncio.run(run())


def test_tileset_preview_and_deletion_through_sdk(tmp_path):
    async def run():
        async with Client(create_server(root=tmp_path)) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}

            async def call(opname, **args):
                response = await client.call_tool(opname, {"project": "tile.csprite", **args})
                value = response.structured_content
                Draft202012Validator(tools[opname].output_schema).validate(value)
                return response, value

            await call("new_project", width=4, height=4)
            await call("add_tileset", name="Tiles", tile_w=2, tile_h=2, preview="none")
            image, result = await call(
                "set_tile_pixels",
                tileset="TS1",
                tile="new",
                rows=["0101", "0101"],
                preview="inline",
            )
            assert result["ok"] and result["changed"]["tilesets"] == ["TS1"]
            assert sum(item.type == "image" for item in image.content) == 1
            image, result = await call("render_preview", tileset="TS1", scale=4)
            assert result["ok"] and sum(item.type == "image" for item in image.content) == 1
            await call("add_layer", name="Map", type="tilemap", tileset="TS1", preview="none")
            response, result = await call("delete_tileset", tileset="TS1")
            assert response.is_error and result["error"]["code"] == "E_IN_USE"
            assert result["error"]["details"]["layers"] == [{"id": "L2", "name": "Map"}]
            await call("delete_layer", layer="L2", preview="none")
            _, result = await call("delete_tileset", tileset="TS1", preview="none")
            assert result["ok"] and result["changed"]["tilesets"] == ["TS1"]
            _, result = await call("delete_tileset", tileset="TS1", missing_ok=True, preview="none")
            assert result["no_op"]

    asyncio.run(run())


@pytest.mark.parametrize("profile", ["standard", "minimal"])
@pytest.mark.parametrize("read_only", [False, True])
def test_profiles(tmp_path, profile, read_only):
    service = MCPService(root=tmp_path, profile=profile, read_only=read_only)
    expected = {op.name for op in ops.registry().all()} - {"list_generators", "generate_image"}
    if profile == "minimal":
        expected &= MINIMAL
    if read_only:
        expected &= {op.name for op in ops.registry().all() if op.kind == "query"}
    assert set(service.exposed) == expected


def test_generation_plugin_and_forbidden_gates(tmp_path):
    registry = Registry()
    base = ops.registry().get("get_info")
    for name, provider in [
        ("plugin_read", "example"),
        ("generate_image", "builtin"),
        ("list_generators", "builtin"),
        ("eval", "example"),
    ]:
        registry.register(replace(base, name=name, provider=provider))
    assert not MCPService(root=tmp_path, registry=registry).exposed
    service = MCPService(
        root=tmp_path,
        registry=registry,
        enable_generation=True,
        allow_plugin_op=["plugin_read", "eval"],
    )
    assert set(service.exposed) == {"plugin_read", "list_generators", "generate_image"}


def test_roundtrip_envelopes_images_actor_and_rollback(tmp_path):
    async def run():
        async with Client(
            create_server(root=tmp_path),
            client_info=Implementation(name="contract-client", version="1"),
        ) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}

            async def call(name, **args):
                result = await client.call_tool(name, {"project": "hero.csprite", **args})
                value = result.structured_content
                assert json.loads(result.content[0].text) == value
                Draft202012Validator(tools[name].output_schema).validate(value)
                assert result.is_error == (not value["ok"])
                return result

            assert (await call("new_project", width=16, height=16)).structured_content["ok"]
            args = dict(
                layer="L1",
                frame=0,
                x=2,
                y=3,
                color=1,
                preview="inline",
                idempotency_key="draw-once",
            )
            result = await call("set_pixel", **args)
            assert result.structured_content["revision"] == {"before": 0, "after": 1}
            assert result.content[1].type == "image"
            assert base64.b64decode(result.content[1].data).startswith(b"\x89PNG\r\n\x1a\n")
            path = result.structured_content["preview"]["paths"][0]
            assert path.startswith("hero.csprite/.cybersprite/previews/")
            assert (tmp_path / path).is_file()
            assert (await call("set_pixel", **args)).structured_content["replayed"]
            history = (await call("get_history")).structured_content["result"]
            assert history["entries"][-1]["actor"] == "agent:contract-client"
            before = (tmp_path / "hero.csprite/project.json").read_bytes()
            for bad in ({**args, "color": 999}, {**args, "extra": 1}, {**args, "x": 1.5}):
                bad.pop("idempotency_key")
                assert (await call("set_pixel", **bad)).is_error
                assert (tmp_path / "hero.csprite/project.json").read_bytes() == before
            failed = await call(
                "apply_ops",
                ops=[
                    {
                        "op": "set_pixel",
                        "args": {"layer": "L1", "frame": 0, "x": 1, "y": 1, "color": 2},
                    },
                    {
                        "op": "set_pixel",
                        "args": {"layer": "L1", "frame": 0, "x": 2, "y": 1, "color": 999},
                    },
                ],
            )
            assert failed.structured_content["error"]["op_index"] == 1
            assert (tmp_path / "hero.csprite/project.json").read_bytes() == before
            assert not (
                await call("set_pixel", layer="L1", frame=0, x=5, y=5, color=2, dry_run=True)
            ).is_error
            assert (tmp_path / "hero.csprite/project.json").read_bytes() == before
            assert not (await call("undo", preview="none")).is_error
            assert load_project(tmp_path / "hero.csprite").revision == 2
            with pytest.raises(MCPError):
                await client.call_tool("missing_tool", {"project": "hero.csprite"})

    asyncio.run(run())


def test_progress(tmp_path):
    async def run():
        progress = []

        async def receive(value, total, message):
            progress.append(value)

        async with Client(create_server(root=tmp_path)) as client:
            await client.call_tool(
                "new_project",
                {"project": "p.csprite", "width": 1, "height": 1},
                progress_callback=receive,
            )
        assert progress

    asyncio.run(run())


def test_valid_json_wrong_argument_shape_is_tool_error(tmp_path):
    async def run():
        async with Client(create_server(root=tmp_path), mode="2026-07-28") as client:
            # model_construct bypasses client-side validation, so the actual server
            # receives a valid JSON request whose tool arguments have the wrong type.
            from mcp import types

            request = types.CallToolRequest(
                params=types.CallToolRequestParams.model_construct(
                    name="get_info", arguments=["wrong-shape"]
                )
            )
            with pytest.warns(UserWarning, match="Pydantic serializer warnings"):
                result = await client.session.send_request(request, types.CallToolResult)
            assert result.is_error
            assert result.structured_content["error"]["code"] == "E_INVALID_ARGS"

    asyncio.run(run())
