"""Review, ramps and native exports share the real MCP contracts and path policy."""

import asyncio

import pytest

pytest.importorskip("mcp.server")
from jsonschema import Draft202012Validator  # noqa: E402
from mcp import Client  # noqa: E402

from cybersprite.mcp.server import MCPService, create_server  # noqa: E402


def test_mcp_e3_full_contracts(tmp_path, monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_CONFIG_DIR", str(tmp_path / "config"))
    service = MCPService(root=tmp_path)

    async def run():
        async with Client(create_server(root=tmp_path)) as client:

            async def call(name, **args):
                response = await client.call_tool(name, {"project": "p", **args})
                value = response.structured_content
                assert not response.is_error, value
                Draft202012Validator(service.contracts[name]["outputSchema"]).validate(value)
                return value

            await call("new_project", platform="dmg/sprite-16")
            palette = await call("get_palette")
            colors = [v["color"] for v in palette["result"]["colors"]]
            await call(
                "set_palette",
                colors=colors,
                ramps=[{"name": "body", "indices": [1, 2, 3]}],
                preview="none",
            )
            await call("set_pixel", layer="L1", frame=0, x=3, y=3, color="@body:1", preview="none")
            await call("shift_ramp", layer="L1", frame=0, direction="darker", preview="none")
            review = await call("render_preview", layout="review", inline=False)
            assert len(review["result"]["panels"]) >= 4
            exported = await call("export_native", format="gb-2bpp", out="tiles.2bpp", layer="L1")
            assert exported["result"]["verified"]
            assert (tmp_path / "tiles.2bpp").stat().st_size == 64
            refused = await client.call_tool(
                "export_native", {"project": "p", "layer": "L1", "out": "../escape.2bpp"}
            )
            assert refused.is_error
            assert refused.structured_content["error"]["code"] == "E_PATH_NOT_ALLOWED"

    asyncio.run(run())
