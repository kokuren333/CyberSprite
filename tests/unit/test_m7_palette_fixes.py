"""Production regressions: preserve GPL names and report only composited frame changes."""

import json

import pytest
from click.testing import CliRunner

from cybersprite.cli import cli
from cybersprite.core.canonical import load_project
from cybersprite.ops import execute


def test_gpl_names_new_load_replace_and_append(tmp_path):
    gpl = tmp_path / "named.gpl"
    gpl.write_bytes(b"GIMP Palette\nName: Authored\n0 0 0 Ink\n255 255 255 Paper white\n")
    root = tmp_path / "named.csprite"
    result = CliRunner().invoke(cli, ["new", str(root), "--size", "2x2", "--palette", str(gpl)])
    assert result.exit_code == 0, result.output
    assert load_project(root).palette.names == {"0": "Ink", "1": "Paper white"}
    execute(
        "set_palette", root, {"colors": ["#000000ff", "#ffffffff"], "names": {}}, preview="none"
    )
    execute("load_palette", root, {"source": str(gpl)}, preview="none")
    assert load_project(root).palette.names == {"0": "Ink", "1": "Paper white"}
    execute("set_palette", root, {"colors": ["#ff0000ff"]}, preview="none")
    execute("load_palette", root, {"source": str(gpl), "mode": "append"}, preview="none")
    assert load_project(root).palette.names == {"0": "Ink", "1": "Ink", "2": "Paper white"}


@pytest.mark.parametrize(
    "op,args",
    [
        ("set_palette_color", {"index": 1, "color": "#ffffffff", "name": "White renamed"}),
        ("set_palette_frozen", {"frozen": True}),
        (
            "set_palette",
            {"colors": ["#00000000", "#ffffffff", "#ffffffff"], "names": {"1": "White"}},
        ),
        ("remap_palette", {"order": [0, 2, 1]}),
        ("set_frame_duration", {"frames": "all", "duration_ms": 120}),
        ("update_layer", {"layer": "L1", "name": "Renamed"}),
    ],
)
def test_metadata_and_same_color_remap_report_no_frames(tmp_path, op, args):
    root = tmp_path / "metadata.csprite"
    execute(
        "new_project",
        root,
        {"width": 2, "height": 2, "palette": ["#00000000", "#ffffffff", "#ffffffff"]},
    )
    execute(
        "set_pixel", root, {"layer": "L1", "frame": 0, "x": 0, "y": 0, "color": 1}, preview="none"
    )
    result = execute(op, root, args, preview="none")
    assert result["changed"]["data"]
    assert result["changed"]["frames"] == []
    assert result["preview"]["paths"] == []


def test_cli_export_hint_mentions_cwd(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    root = cwd / "sprite.csprite"
    execute("new_project", root, {"width": 2, "height": 2})
    result = CliRunner().invoke(cli, ["-p", str(root), "export", "image", "--out", "../bad.png"])
    assert result.exit_code != 0
    value = json.loads(result.output)
    assert value["error"]["code"] == "E_PATH_NOT_ALLOWED"
    assert (
        f"run from a parent directory or use a path under {cwd.as_posix()}"
        in value["error"]["hint"]
    )
    assert not (tmp_path / "bad.png").exists()
