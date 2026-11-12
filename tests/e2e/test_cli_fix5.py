"""The key=value interface uses the same list grammar as generated options."""

import json

import pytest
from click.testing import CliRunner

from cybersprite.cli import cli
from cybersprite.core.canonical import load_project


@pytest.mark.parametrize("frames", ["2,4", "[2,4]"])
def test_op_comma_frames_and_string_lists(tmp_path, frames):
    runner = CliRunner()
    project = tmp_path / "list.csprite"
    created = runner.invoke(cli, ["new", str(project), "--size", "4x4", "--frames", "5"])
    assert created.exit_code == 0, created.output
    result = runner.invoke(
        cli,
        [
            "-p",
            str(project),
            "op",
            "set_frame_duration",
            f"frames={frames}",
            "duration_ms=120",
            "--preview",
            "none",
        ],
    )
    assert result.exit_code == 0, result.output
    assert [f.duration_ms for f in load_project(project).frames] == [100, 100, 120, 100, 120]
    result = runner.invoke(cli, ["-p", str(project), "op", "get_info", "include=summary,layers"])
    assert result.exit_code == 0, result.output
    assert set(json.loads(result.output)["result"]) == {"summary", "layers"}


def test_op_invalid_comma_item_is_an_argument_error(tmp_path):
    result = CliRunner().invoke(
        cli,
        [
            "-p",
            str(tmp_path),
            "op",
            "set_frame_duration",
            "frames=2,bad",
            "duration_ms=120",
        ],
    )
    assert result.exit_code == 2, result.output
