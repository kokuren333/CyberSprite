"""Scenario 3 traverses real MCP calls, shared tile correction, and verified tile export."""

import asyncio

import pytest

from tests.e2e.replay import SCENARIOS, replay


@pytest.mark.parametrize("stdio", [False, True])
def test_scenario3_tiles(tmp_path, stdio):
    directory = SCENARIOS / "scenario3"
    outputs, transcript = asyncio.run(replay(directory, tmp_path, stdio=stdio, exports=True))
    assert len(transcript) == 10
    assert transcript[-2]["images"] == 2
    assert transcript[-1]["revision"] == 6
    for name, data in outputs.items():
        assert data == (directory / "expected" / name).read_bytes(), name
