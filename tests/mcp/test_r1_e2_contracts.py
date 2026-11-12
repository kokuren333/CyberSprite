"""M12 tools through the real MCP client and shared path policy."""

import asyncio

import numpy as np
import pytest

pytest.importorskip("mcp.server")
from jsonschema import Draft202012Validator  # noqa: E402
from mcp import Client  # noqa: E402

from cybersprite.formats.png import encode_png  # noqa: E402
from cybersprite.mcp.server import MCPService, create_server  # noqa: E402


def test_mcp_m12_contracts_and_demo(tmp_path, monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_NOW", "2026-11-12T12:00:00+09:00")
    (tmp_path / "design.png").write_bytes(encode_png(np.full((3, 4, 4), 255, dtype=np.uint8)))
    service = MCPService(root=tmp_path)

    async def run():
        async with Client(create_server(root=tmp_path)) as client:

            async def call(operation, **args):
                response = await client.call_tool(operation, {"project": "p", **args})
                value = response.structured_content
                assert not response.is_error, value
                Draft202012Validator(service.contracts[operation]["outputSchema"]).validate(value)
                return value

            await call("new_project", width=16, height=12)
            await call(
                "set_palette_color", index=1, color="#123456ff", name="shadow", preview="none"
            )
            draw = {"layer": "L1", "frame": 0, "preview": "none"}
            await call("ellipse", **draw, x=4, y=3, w=7, h=7, color="@shadow", filled=True)
            await call(
                "rect",
                **draw,
                x=5,
                y=3,
                w=6,
                h=5,
                color=2,
                filled=True,
                mask={"only_on": ["@shadow"]},
            )
            await call(
                "rect", **draw, x=6, y=3, w=4, h=2, color=3, filled=True, mask={"only_on": [2]}
            )
            await call("outline", **draw, color=4, exclude_colors=[4])
            second = await call("outline", **draw, color=4, exclude_colors=[4])
            assert second["no_op"]
            await call("render_preview", rect={"x": 3, "y": 2, "w": 10, "h": 9}, scale=3)
            project_bytes = (tmp_path / "p/project.json").read_bytes()
            added = await call(
                "add_source", files=["design.png"], provenance={"license": "CC0-1.0"}
            )
            await call(
                "render_preview", guide={"source": added["result"]["source"]}, layout="strip"
            )
            assert (tmp_path / "p/project.json").read_bytes() == project_bytes

    asyncio.run(run())


def test_add_source_mcp_input_confinement(tmp_path):
    service = MCPService(root=tmp_path)
    result = service.call(
        "add_source",
        {"project": "p", "files": "../escape.png", "provenance": {"license": "unknown"}},
    )
    assert result.is_error
    assert result.structured_content["error"]["code"] == "E_PATH_NOT_ALLOWED"


def test_region_limit_before_mcp_schema_recursion(tmp_path):
    service = MCPService(root=tmp_path)
    value = {"type": "all"}
    for _ in range(32):
        value = {"type": "not", "of": [value]}
    result = service.call("erase", {"project": "p", "layer": "L1", "frame": 0, "region": value})
    assert result.is_error
    assert result.structured_content["error"]["code"] == "E_LIMIT_EXCEEDED"
