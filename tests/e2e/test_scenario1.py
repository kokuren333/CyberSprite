"""Scenario 1 is fixed by canonical project bytes and CSPX1 pixel hashes."""

import asyncio

import pytest

pytest.importorskip("mcp.server")

from cybersprite import ops  # noqa: E402
from tests.e2e.replay import SCENARIOS, replay  # noqa: E402


@pytest.mark.parametrize("stdio", [False, True])
def test_scenario1_non_export(tmp_path, stdio):
    directory = SCENARIOS / "scenario1"
    outputs, transcript = asyncio.run(replay(directory, tmp_path, stdio=stdio))
    for name, data in outputs.items():
        assert data == (directory / "expected" / name).read_bytes()
    assert len(transcript) == 7
    assert transcript[-1]["images"] == 4
    assert transcript[-1]["revision"] == 4


def test_scenario1_exports(tmp_path):
    names = {op.name for op in ops.registry().all()}
    required = {"export_sheet", "export_animation"}
    if not required <= names:
        pytest.skip("M5 export_sheet/export_animation are not registered; re-enabled on merge")
    directory = SCENARIOS / "scenario1"
    outputs, transcript = asyncio.run(replay(directory, tmp_path, stdio=True, exports=True))
    assert len(transcript) == 9
    for name, data in outputs.items():
        assert data == (directory / "expected" / name).read_bytes()
