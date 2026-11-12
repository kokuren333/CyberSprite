"""Real M3/M5/M6 commands and production-session regressions."""

from pathlib import Path

import numpy as np
import pytest
from click.testing import CliRunner

from cybersprite.core.canonical import load_project
from cybersprite.core.projects import create_project
from cybersprite.core.render import render
from cybersprite.formats.png import decode_png
from cybersprite.ops import DRAWING, registry
from tests.e2e.test_cli_m3 import invoke
from tools.m5_cases import tile_project

CORPUS = Path(__file__).resolve().parents[1] / "pipeline/corpus/originals/hero_16x16.png"


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    invoke(runner, "new", "sprite", "--size", "16x16", "--palette", "gray-4")
    return runner


@pytest.mark.parametrize(
    "command,extension,options",
    [
        ("image", "png", []),
        ("sheet", "png", ["--data-out", "sheet.json", "--data-format", "json-hash"]),
        ("anim", "gif", []),
        ("anim", "apng", []),
        ("aseprite", "aseprite", []),
        ("palette", "hex", []),
        ("tileset", "png", ["--tileset", "TS1"]),
    ],
)
def test_real_export_commands(session, command, extension, options):
    if command == "tileset":
        create_project("tiles", tile_project())
    project = "tiles" if command == "tileset" else "sprite"
    result = invoke(
        session, "-p", project, "export", command, "--out", f"out.{extension}", *options
    )
    assert result["result"]["validation_ok"] and result["result"]["verified"]
    assert all(Path(item["path"]).is_file() for item in result["result"]["files"])
    rejected = invoke(
        session,
        "-p",
        project,
        "export",
        command,
        "--out",
        f"../outside.{extension}",
        *options,
        code=4,
    )
    assert rejected["error"]["code"] == "E_PATH_NOT_ALLOWED"


def test_imports_share_one_manifest_and_cli_pipeline(session):
    invoke(session, "-p", "sprite", "export", "aseprite", "--out", "roundtrip.aseprite")
    imported = invoke(session, "import", "aseprite", "roundtrip.aseprite", "--out", "reimported")
    assert imported["result"]["source"] == "SRC1"
    np.testing.assert_array_equal(
        render(load_project("sprite"), 0), render(load_project("reimported"), 0)
    )
    imported = invoke(
        session,
        "-p",
        "reimported",
        "import",
        "image",
        CORPUS,
        "--preset",
        "exact",
        "--provenance",
        '{"license":"unknown"}',
    )
    assert imported["result"]["accepted"] and imported["result"]["source"] == "SRC2"
    listed = invoke(session, "-p", "reimported", "source", "list")
    assert [s["id"] for s in listed["result"]["sources"]] == ["SRC1", "SRC2"]
    assert (
        invoke(session, "-p", "reimported", "source", "show", "SRC1")["result"]["pipeline"] is None
    )
    retried = invoke(
        session, "-p", "reimported", "import", "image", "--source", "SRC2", "--preset", "exact"
    )
    assert retried["result"]["accepted"]
    output = invoke(
        session,
        "convert",
        CORPUS,
        "converted.png",
        "--preset",
        "exact",
        "--stages",
        "stages",
        "--sheet-cell",
        "8x8",
    )
    assert output["result"]["accepted"] and len(output["result"]["outputs"]) == 4
    assert all(Path(p).is_file() for p in output["result"]["stage_paths"])
    assert decode_png(Path("converted.png").read_bytes()).pixels.shape == (8, 8)
    assert invoke(session, "pipeline", "detect-grid", CORPUS)["result"]["detected"]


def test_label_counts_history_previews_and_read_options(session):
    result = invoke(
        session,
        "-p",
        "sprite",
        "op",
        "rect",
        "layer=L1",
        "frame=0",
        "x=1",
        "y=1",
        "w=4",
        "h=4",
        "color=1",
        "--label",
        "single rectangle",
    )
    assert result["result"]["pixels_written"] == 12
    history = invoke(session, "-p", "sprite", "history")
    assert history["result"]["entries"][0]["label"] == "single rectangle"
    for command in ("undo", "redo"):
        result = invoke(session, "-p", "sprite", command)
        assert result["preview"]["paths"]
        assert all((Path("sprite") / p).is_file() for p in result["preview"]["paths"])
    invoke(
        session,
        "-p",
        "sprite",
        "preview",
        "--frames",
        "0",
        "--onion",
        "0,0",
        "--out",
        "preview.png",
    )
    assert Path("preview.png").is_file()
    assert (
        invoke(
            session, "-p", "sprite", "pixels", "--layer", "L1", "--as", "sym", "--rect", "0,0,4,4"
        )["result"]["w"]
        == 4
    )
    assert invoke(session, "-p", "sprite", "validate", "--frames", "0")["result"]["ok"]
    for name in sorted(DRAWING):
        assert "pixels_written" in registry().get(name).result.model_fields


def test_every_argument_has_field_documentation(session):
    for op in registry().all():
        assert op.description
        schema = op.describe()["inputSchema"]
        assert all(field.get("description") for field in schema["properties"].values()), op.name
    result = invoke(session, "ops", "describe", "draw_rows")
    description = result["result"]["inputSchema"]["properties"]["format"]["description"]
    assert (
        "two hexadecimal digits" in description
        and "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ" in description
    )
    assert ". for the transparent index" in description
