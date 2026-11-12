"""Manual reference images (publication fix item 3, audit A-11 / R2-11, R2-16).

register_reference is the one path for CLI, MCP and GUI. These tests cover
registration and provenance, surface-decided placed_by, input limits and path
guards, and hash verification of registered (including unplaced) sources.
"""

import asyncio
import base64
import hashlib
import json

import numpy as np
import pytest
from click.testing import CliRunner

from cybersprite.cli import cli
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.limits import REFERENCE_BYTES
from cybersprite.core.sources import read_manifest
from cybersprite.formats.png import encode_png
from cybersprite.ops import execute


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_NOW", "2026-11-12T12:00:00+09:00")
    path = tmp_path / "ref.csprite"
    execute("new_project", path, {"width": 8, "height": 8})
    return path


def png(color=(200, 10, 10, 255), size=(3, 5)):
    return encode_png(np.full((size[1], size[0], 4), color, dtype=np.uint8))


def issues(root, rule):
    result = execute("validate", root)["result"]
    return [issue for issue in result["issues"] if issue["rule"] == rule]


def test_register_local_file_records_hash_and_provenance_outside_source(root, tmp_path):
    image = tmp_path / "saved-from-browser.png"
    image.write_bytes(png())
    project = (root / "project.json").read_bytes()
    value = execute(
        "register_reference",
        root,
        {"file": str(image), "rights_note": "third-party sprite, measure only"},
        actor="cli",
    )
    result = value["result"]
    assert value["revision"] == 0 and (root / "project.json").read_bytes() == project
    assert result["source"] == "SRC1" and result["placed_by"] == "human-cli"
    assert result["duplicate"] is False and (result["width"], result["height"]) == (3, 5)
    assert result["files"] == [".cybersprite/references/SRC1/reference_0000.png"]
    stored = root / result["files"][0]
    assert stored.read_bytes() == image.read_bytes()
    assert result["sha256"] == hashlib.sha256(image.read_bytes()).hexdigest()
    # SPEC §3.6: the reference bytes never enter source/; only the record does.
    assert [p.name for p in (root / "source").rglob("*") if p.is_file()] == ["manifest.json"]
    source = read_manifest(root).sources[0]
    assert (source.use, source.origin, source.placed_by) == ("reference", "manual", "human-cli")
    assert source.rights_note == "third-party sprite, measure only" and source.url == ""
    assert source.license == "unknown" and source.placements == [] and source.pipeline is None
    assert "saved-from-browser" not in (root / "source/manifest.json").read_text("utf-8")
    listed = execute("list_sources", root)["result"]["sources"][0]
    assert listed["placed_by"] == "human-cli" and listed["files"] == result["files"]
    assert issues(root, "Q-SRC-05") == []


def test_same_bytes_are_registered_once(root, tmp_path):
    image = tmp_path / "a.png"
    image.write_bytes(png())
    first = execute("register_reference", root, {"file": str(image), "rights_note": "x"})
    data = base64.b64encode(image.read_bytes()).decode()
    again = execute("register_reference", root, {"data": data, "rights_note": "y"}, actor="gui")
    assert again["result"]["duplicate"] is True
    assert again["result"]["source"] == first["result"]["source"]
    assert len(read_manifest(root).sources) == 1


def test_existing_sources_keep_their_manifest_bytes(root, tmp_path):
    design = tmp_path / "design.png"
    design.write_bytes(png((1, 2, 3, 255)))
    execute("add_source", root, {"files": str(design), "provenance": {"license": "CC0-1.0"}})
    text = (root / "source/manifest.json").read_text("utf-8")
    assert '"origin"' not in text and '"placed_by"' not in text
    shown = execute("get_source", root, {"id": "SRC1"})["result"]
    assert "origin" not in shown and "placed_by" not in shown
    info = execute("get_info", root, {"include": ["sources"]})["result"]["sources"]
    assert "origin" not in info["sources"][0]


@pytest.mark.parametrize(
    ("actor", "requested", "expected"),
    [
        ("cli", None, "human-cli"),
        ("cli", "agent", "agent"),
        ("gui", None, "human-gui"),
        ("agent:claude", None, "agent"),
        ("agent:claude", "agent", "agent"),
    ],
)
def test_surface_decides_placed_by(root, actor, requested, expected):
    args = {"data": base64.b64encode(png()).decode(), "rights_note": "own sketch"}
    if requested:
        args["placed_by"] = requested
    value = execute("register_reference", root, args, actor=actor)
    assert value["result"]["placed_by"] == expected
    assert read_manifest(root).sources[0].placed_by == expected


@pytest.mark.parametrize(
    ("actor", "requested"),
    [
        ("gui", "agent"),
        ("gui", "human-cli"),
        ("agent:x", "human-gui"),
        ("agent:x", "human-cli"),
        ("cli", "human-gui"),
    ],
)
def test_callers_cannot_claim_another_surface(root, actor, requested):
    args = {"data": base64.b64encode(png()).decode(), "rights_note": "x", "placed_by": requested}
    with pytest.raises(CyberSpriteError) as error:
        execute("register_reference", root, args, actor=actor)
    assert error.value.code == "E_INVALID_ARGS"
    assert not (root / "source/manifest.json").exists()


def test_dry_run_writes_nothing(root):
    args = {"data": base64.b64encode(png()).decode(), "rights_note": "x"}
    value = execute("register_reference", root, args, dry_run=True)
    assert value["dry_run"] and value["result"]["source"] is None and value["result"]["files"] == []
    assert not (root / "source/manifest.json").exists()
    assert not (root / ".cybersprite/references").exists()


@pytest.mark.parametrize(
    ("args", "code"),
    [
        ({"rights_note": "x"}, "E_INVALID_ARGS"),  # neither file nor data
        ({"data": "AAAA", "file": "x.png", "rights_note": "x"}, "E_INVALID_ARGS"),
        ({"data": base64.b64encode(b"x" * 10).decode()}, "E_INVALID_ARGS"),  # no rights note
        ({"data": base64.b64encode(b"x" * 10).decode(), "rights_note": ""}, "E_INVALID_ARGS"),
        ({"data": "not base64!", "rights_note": "x"}, "E_INVALID_ARGS"),
        ({"data": base64.b64encode(b"plain text").decode(), "rights_note": "x"}, "E_IO"),
        ({"data": "A" * (REFERENCE_BYTES * 2), "rights_note": "x"}, "E_INVALID_ARGS"),
    ],
)
def test_invalid_inputs_are_refused_without_writes(root, args, code):
    with pytest.raises(CyberSpriteError) as error:
        execute("register_reference", root, args)
    assert error.value.code == code
    assert not (root / "source/manifest.json").exists()


def test_file_size_limit_is_checked_before_reading(root, tmp_path):
    big = tmp_path / "big.png"
    with big.open("wb") as stream:
        stream.write(b"\x89PNG\r\n\x1a\n")
        stream.truncate(REFERENCE_BYTES + 1)
    with pytest.raises(CyberSpriteError) as error:
        execute("register_reference", root, {"file": str(big), "rights_note": "x"})
    assert error.value.code == "E_LIMIT_EXCEEDED"
    assert error.value.details["limit_name"] == "reference_bytes"
    assert error.value.details["limit"] == REFERENCE_BYTES


def test_decoder_pixel_limit_applies(root, tmp_path):
    import struct
    import zlib

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    header = struct.pack(">IIBBBBB", 9000, 1, 8, 6, 0, 0, 0)
    bomb = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IEND", b"")
    with pytest.raises(CyberSpriteError) as error:
        execute(
            "register_reference",
            root,
            {"data": base64.b64encode(bomb).decode(), "rights_note": "x"},
        )
    assert error.value.code == "E_LIMIT_EXCEEDED"


def test_registered_sources_are_hash_checked_even_when_unplaced(root, tmp_path):
    """R2-16 minimum: references and unplaced design originals get Q-SRC-05."""
    reference = execute(
        "register_reference",
        root,
        {"data": base64.b64encode(png()).decode(), "rights_note": "x"},
    )["result"]
    design = tmp_path / "design.png"
    design.write_bytes(png((1, 2, 3, 255)))
    added = execute(
        "add_source", root, {"files": str(design), "provenance": {"license": "unknown"}}
    )
    assert issues(root, "Q-SRC-05") == []
    stored_reference = root / reference["files"][0]
    stored_design = root / added["result"]["files"][0]
    original = stored_reference.read_bytes()
    stored_reference.write_bytes(png((0, 0, 0, 255)))
    stored_design.unlink()
    found = issues(root, "Q-SRC-05")
    # Issues at the same location are merged into one message.
    assert [issue["level"] for issue in found] == ["warning"]
    assert "reference source SRC1" in found[0]["message"]
    assert "design source SRC2" in found[0]["message"]
    assert execute("validate", root)["result"]["ok"] is True  # a warning, not an export block
    stored_reference.write_bytes(original)
    stored_design.write_bytes(design.read_bytes())
    assert issues(root, "Q-SRC-05") == []


def test_references_cannot_be_imported_to_the_canvas(root):
    execute(
        "register_reference",
        root,
        {"data": base64.b64encode(png()).decode(), "rights_note": "x"},
    )
    with pytest.raises(CyberSpriteError) as error:
        execute("import_image", root, {"source": "SRC1"})
    assert error.value.code == "E_INVALID_ARGS"
    assert "measuring only" in error.value.message


def test_reference_files_are_protected_from_outputs(root, tmp_path, monkeypatch):
    execute(
        "register_reference",
        root,
        {"data": base64.b64encode(png()).decode(), "rights_note": "x"},
    )
    stored = root / ".cybersprite/references/SRC1/reference_0000.png"
    before = stored.read_bytes()
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    for args in (
        [
            "-p",
            "ref.csprite",
            "render",
            "--out",
            "ref.csprite/.cybersprite/references/SRC1/reference_0000.png",
        ],
        [
            "-p",
            "ref.csprite",
            "export",
            "image",
            "--out",
            "ref.csprite/.cybersprite/references/x.png",
        ],
    ):
        result = runner.invoke(cli, args)
        assert result.exit_code == 4, result.stdout
        assert json.loads(result.stdout)["error"]["code"] == "E_PATH_NOT_ALLOWED"
    assert stored.read_bytes() == before


def test_cli_command_registers_and_lists(root, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "saved.png").write_bytes(png())
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["-p", "ref.csprite", "source", "reference", "saved.png", "--rights-note", "own photo"],
    )
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["result"]["placed_by"] == "human-cli"
    result = runner.invoke(
        cli,
        [
            "-p",
            "ref.csprite",
            "source",
            "reference",
            "saved.png",
            "--rights-note",
            "x",
            "--placed-by",
            "agent",
        ],
    )
    assert json.loads(result.stdout)["result"]["duplicate"] is True
    listed = json.loads(runner.invoke(cli, ["-p", "ref.csprite", "source", "list"]).stdout)
    assert listed["result"]["sources"][0]["origin"] == "manual"


def test_mcp_registers_as_agent_within_the_root(tmp_path, monkeypatch):
    pytest.importorskip("mcp.server")
    from jsonschema import Draft202012Validator
    from mcp import Client

    from cybersprite.mcp.server import MCPService, create_server

    monkeypatch.setenv("CYBERSPRITE_NOW", "2026-11-12T12:00:00+09:00")
    (tmp_path / "saved.png").write_bytes(png())
    service = MCPService(root=tmp_path)
    assert "register_reference" in {tool.name for tool in service.tools()}

    async def run():
        async with Client(create_server(root=tmp_path)) as client:
            await client.call_tool("new_project", {"project": "p", "width": 8, "height": 8})
            response = await client.call_tool(
                "register_reference",
                {"project": "p", "file": "saved.png", "rights_note": "measure only"},
            )
            value = response.structured_content
            assert not response.is_error, value
            Draft202012Validator(service.contracts["register_reference"]["outputSchema"]).validate(
                value
            )
            assert value["result"]["placed_by"] == "agent"
            # Paths come back relative to the MCP root, like other source files.
            assert value["result"]["files"] == ["p/.cybersprite/references/SRC1/reference_0000.png"]
            listed = await client.call_tool("list_sources", {"project": "p"})
            entry = listed.structured_content["result"]["sources"][0]
            assert entry["placed_by"] == "agent"
            assert entry["files"] == value["result"]["files"]
            claimed = await client.call_tool(
                "register_reference",
                {"project": "p", "file": "saved.png", "rights_note": "x", "placed_by": "human-gui"},
            )
            assert claimed.is_error

    asyncio.run(run())
    escaped = service.call(
        "register_reference", {"project": "p", "file": "../escape.png", "rights_note": "x"}
    )
    assert escaped.is_error
    assert escaped.structured_content["error"]["code"] == "E_PATH_NOT_ALLOWED"


def test_gui_service_records_human_gui(tmp_path, monkeypatch):
    pytest.importorskip("starlette")
    from cybersprite.server.app import Service

    monkeypatch.setenv("CYBERSPRITE_NOW", "2026-11-12T12:00:00+09:00")
    execute("new_project", tmp_path / "g.csprite", {"width": 8, "height": 8})
    service = Service(tmp_path, "g.csprite")
    project = service.path("g.csprite")
    data = base64.b64encode(png()).decode()
    value = service.run_op("register_reference", project, {"data": data, "rights_note": "x"})
    assert value["result"]["placed_by"] == "human-gui"
    # Root-relative, ready for the GUI file route (/files/...).
    assert value["result"]["files"] == ["g.csprite/.cybersprite/references/SRC1/reference_0000.png"]
    listed = service.run_op("list_sources", project, {})
    assert listed["result"]["sources"][0]["placed_by"] == "human-gui"
