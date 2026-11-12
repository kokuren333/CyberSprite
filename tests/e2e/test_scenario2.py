"""Corpus reject/adjust/accept/touch-up/export through real MCP clients."""

import asyncio

import pytest

pytest.importorskip("mcp.server")

from tests.e2e.replay import SCENARIOS, replay  # noqa: E402


@pytest.mark.parametrize("stdio", [False, True])
def test_scenario2(tmp_path, stdio):
    directory = SCENARIOS / "scenario2"
    outputs, transcript = asyncio.run(replay(directory, tmp_path, stdio=stdio, exports=True))
    assert len(transcript) == 8
    assert transcript[0]["accepted"] is False
    assert transcript[3]["accepted"] is True
    assert transcript[-2]["images"] == 1
    for name, data in outputs.items():
        assert data == (directory / "expected" / name).read_bytes()
