"""Older MCP protocol versions (e.g. 2025-06-18, used by some clients) require every tool's
outputSchema to be a JSON object schema with a root ``"type": "object"``."""

import pytest

pytest.importorskip("mcp.server")
from cybersprite.mcp.server import MCPService  # noqa: E402


def test_every_output_schema_has_object_root(tmp_path):
    service = MCPService(root=tmp_path)
    assert service.contracts
    for name, contract in service.contracts.items():
        assert contract["outputSchema"].get("type") == "object", name
        assert contract["inputSchema"].get("type") == "object", name
