"""Streamable HTTP uses the SDK client against a loopback-only ASGI server."""

import asyncio
import socket
import threading

import pytest

pytest.importorskip("mcp.server")

import uvicorn  # noqa: E402
from mcp import Client  # noqa: E402

from cybersprite.mcp.server import create_server  # noqa: E402


def test_streamable_http_stateless(tmp_path):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    port = listener.getsockname()[1]
    app = create_server(root=tmp_path).streamable_http_app(stateless_http=True, host="127.0.0.1")
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    try:

        async def run():
            async with Client(f"http://127.0.0.1:{port}/mcp", mode="2026-07-28") as client:
                listed = await client.list_tools()
                assert listed.tools[0].name == "new_project"
                result = await client.call_tool(
                    "new_project", {"project": "http.csprite", "width": 1, "height": 1}
                )
                assert result.structured_content["ok"]
            # A new client reads the project using only its explicit path.
            async with Client(f"http://127.0.0.1:{port}/mcp", mode="2026-07-28") as client:
                result = await client.call_tool("get_info", {"project": "http.csprite"})
                assert result.structured_content["revision"] == 0

        asyncio.run(run())
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
    assert not thread.is_alive()
