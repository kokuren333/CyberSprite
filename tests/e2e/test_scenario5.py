"""Aseprite import/edit/export/readback through in-process and stdio MCP clients."""

import asyncio

import pytest

from tests.e2e.replay import SCENARIOS, replay


@pytest.mark.parametrize("stdio", [False, True])
def test_scenario5(tmp_path, stdio):
    directory = SCENARIOS / "scenario5"
    outputs, transcript = asyncio.run(replay(directory, tmp_path, stdio=stdio, exports=True))
    assert len(transcript) == 6
    assert transcript[-1]["revision"] == 1
    for name, data in outputs.items():
        assert data == (directory / "expected" / name).read_bytes(), name
