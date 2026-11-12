"""Tile production regressions, tested with indexed fixtures and exact vectors."""

import base64
import json
from copy import deepcopy

import numpy as np
import pytest
from click.testing import CliRunner

from cybersprite.cli import cli
from cybersprite.core.canonical import load_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.models import Grid, ImageCel, ImageLayer, LinkCel, Tile, TileCel
from cybersprite.core.normalize import normalize_cels
from cybersprite.core.pixels import pixels_from_rows, pixels_to_rows
from cybersprite.core.previews import preview_array, tileset_preview
from cybersprite.core.projects import create_project, new_project
from cybersprite.core.quality import report
from cybersprite.core.render import render
from cybersprite.formats.png import decode_png
from cybersprite.mcp.contracts import ORDER, describe
from cybersprite.ops import execute, registry
from tools.m7_cases import FLAGS, PALETTE, tile_project


@pytest.mark.parametrize(
    "origin,override", [((0, 0), False), ((2, 1), False), ((-2, -1), False), ((1, 2), True)]
)
def test_trimmed_top_row_grid_and_all_eight_matches(tmp_path, origin, override):
    p = new_project(width=12, height=9, frames=9, palette=PALETTE)
    p.canvas.grid = Grid(x=8 if override else origin[0], y=7 if override else origin[1], w=7, h=5)
    block = pixels_from_rows(["000000", "010200", "030102"], 3, 3)
    for f, flag in enumerate(FLAGS):
        data = block.T if "d" in flag else block
        if "x" in flag:
            data = data[:, ::-1]
        if "y" in flag:
            data = data[::-1]
        p.layers[0].cels.append(
            ImageCel(frame=f, x=origin[0], y=origin[1], w=3, h=3, pixels=pixels_to_rows(data))
        )
    p.layers[0].cels.append(LinkCel(frame=8, link=0))
    p = normalize_cels(p)
    assert p.layers[0].cels[0].y == origin[1] + 1
    assert p.layers[0].cels[2].y == origin[1]  # The y-flipped tile has an opaque top row.
    before = [render(p, f) for f in range(9)]
    root = tmp_path / "grid.csprite"
    create_project(root, p)
    args = dict(layer="L1", tile_w=3, tile_h=3, match_flips=dict(x=True, y=True, d=True))
    if override:
        args.update(origin_x=origin[0], origin_y=origin[1])
    result = execute("tileset_from_layer", root, args, preview="none")
    assert result["result"] == dict(tileset="TS1", tiles=1, tiles_total=2)
    assert result["validation"]["ok"] and result["changed"]["frames"] == []
    after = load_project(root)
    assert after.tilesets[0].tiles[1].pixels == pixels_to_rows(block)
    for f, flag in enumerate(FLAGS):
        cel = after.layers[0].cels[f]
        assert (cel.x, cel.y, cel.tiles) == (*origin, ["1" + flag])
        np.testing.assert_array_equal(render(after, f), before[f])
    assert after.layers[0].cels[8] == LinkCel(frame=8, link=0)
    np.testing.assert_array_equal(render(after, 8), before[8])


def test_delete_tileset_contract_references_rollback_missing_and_undo(tmp_path):
    root = tmp_path / "delete.csprite"
    create_project(root, tile_project())
    op = registry().get("delete_tileset")
    assert op.idempotency == "C" and op.destructive and "delete_tileset" in ORDER
    schema = describe(op)
    assert schema["annotations"]["destructiveHint"]
    assert "missing_ok" in schema["inputSchema"]["properties"]
    original = (root / "project.json").read_bytes()
    for missing_ok in (False, True):
        with pytest.raises(CyberSpriteError) as error:
            execute("delete_tileset", root, dict(tileset="TS1", missing_ok=missing_ok))
        assert error.value.code == "E_IN_USE" and error.value.exit_code == 3
        assert error.value.details == dict(tileset="TS1", layers=[dict(id="L1", name="Map")])
        assert (root / "project.json").read_bytes() == original
    execute("add_tileset", root, dict(name="Free", tile_w=3, tile_h=3), preview="none")
    original = (root / "project.json").read_bytes()
    execute("delete_tileset", root, dict(tileset="Free"), dry_run=True, preview="path")
    assert (root / "project.json").read_bytes() == original
    with pytest.raises(CyberSpriteError):
        execute(
            "apply_ops",
            root,
            dict(
                ops=[
                    dict(op="delete_tileset", args=dict(tileset="TS2")),
                    dict(op="delete_tileset", args=dict(tileset="TS1")),
                ]
            ),
        )
    assert (root / "project.json").read_bytes() == original
    first = execute("delete_tileset", root, dict(tileset="TS2"), idempotency_key="delete-once")
    assert first["changed"]["tilesets"] == ["TS2"]
    assert execute("delete_tileset", root, dict(tileset="TS2"), idempotency_key="delete-once")[
        "replayed"
    ]
    assert execute("delete_tileset", root, dict(tileset="TS2", missing_ok=True))["no_op"]
    with pytest.raises(CyberSpriteError) as error:
        execute("delete_tileset", root, dict(tileset="TS2"))
    assert error.value.code == "E_TILESET_NOT_FOUND"
    execute("undo", root, preview="none")
    assert [ts.id for ts in load_project(root).tilesets] == ["TS1", "TS2"]
    execute(
        "add_tileset",
        root,
        dict(name="Free", tile_w=3, tile_h=3, if_exists="allow"),
        preview="none",
    )
    with pytest.raises(CyberSpriteError) as error:
        execute("delete_tileset", root, dict(tileset="Free", missing_ok=True))
    assert error.value.code == "E_AMBIGUOUS_REF"


@pytest.mark.parametrize("visibility", ["visible", "hidden", "occluded"])
def test_shared_tile_cels_include_links_and_only_actual_users(tmp_path, visibility):
    p = tile_project()
    p.tilesets[0].tiles.append(Tile(pixels=["020202"] * 3))
    other = deepcopy(p.layers[0])
    other.id, other.name = "L2", "Other"
    other.cels = [TileCel(frame=0, x=0, y=0, w=1, h=1, tiles=["2"])]
    p.layers.append(other)
    p.id_counters.layer = 2
    if visibility == "hidden":
        p.layers[0].visible = False
    if visibility == "occluded":
        p.layers.append(
            ImageLayer(
                id="L3",
                name="Cover",
                cels=[
                    ImageCel(frame=0, x=0, y=0, w=27, h=9, pixels=["03" * 27] * 9),
                    LinkCel(frame=1, link=0),
                ],
            )
        )
        p.id_counters.layer = 3
    root = tmp_path / "shared.csprite"
    create_project(root, p)
    result = execute(
        "set_tile_pixels", root, dict(tileset="TS1", tile=1, rows=["010000", "020000", "030301"])
    )
    changed = result["changed"]
    assert changed["data"] and changed["layers"] == ["L1"]
    assert changed["cels"] == [dict(layer="L1", frame=0), dict(layer="L1", frame=1)]
    assert [f["frame"] for f in changed["frames"]] == ([0, 1] if visibility == "visible" else [])
    assert changed["tilesets"] == ["TS1"] and result["validation"]["ok"]
    assert any(path.endswith("_tileset_TS1.png") for path in result["preview"]["paths"])
    same = execute(
        "set_tile_pixels", root, dict(tileset="TS1", tile=1, rows=["010000", "020000", "030301"])
    )
    assert same["no_op"] and same["changed"]["cels"] == []
    appended = execute(
        "set_tile_pixels", root, dict(tileset="TS1", tile="new", rows=["010101"] * 3)
    )
    assert appended["changed"]["cels"] == [] and appended["changed"]["layers"] == []
    assert appended["preview"]["paths"][0].endswith("_tileset_TS1.png")


def test_hidden_image_link_data_changes_are_reported(tmp_path):
    p = new_project(width=3, height=3, frames=2)
    p.layers[0].visible = False
    p.layers[0].cels = [
        ImageCel(frame=0, x=0, y=0, w=1, h=1, pixels=["01"]),
        LinkCel(frame=1, link=0),
    ]
    root = tmp_path / "hidden.csprite"
    create_project(root, p)
    changed = execute(
        "set_pixel", root, dict(layer="L1", frame=1, x=0, y=0, color=2), preview="none"
    )["changed"]
    assert changed["frames"] == [] and changed["data"]
    assert changed["cels"] == [dict(layer="L1", frame=0), dict(layer="L1", frame=1)]
    deleted = execute("clear_cel", root, dict(layer="L1", frame=1), preview="none")["changed"]
    assert dict(layer="L1", frame=1) in deleted["cels"]


def test_tileset_preview_vectors_transport_and_cli(tmp_path):
    p = tile_project()
    p.tilesets[0].base_index = -4
    root = tmp_path / "preview.csprite"
    create_project(root, p)
    original = (root / "project.json").read_bytes()
    result = execute("render_preview", root, dict(tileset="Glyphs", scale=4))["result"]
    raw = (root / result["paths"][0]).read_bytes()
    image = decode_png(raw).rgba()
    assert raw == base64.b64decode(result["images"][0])
    assert image.shape == (19, 26, 4) and (result["width"], result["height"]) == (26, 19)
    # Existing 3x5 digit vectors: data index zero, then one (independent of base_index).
    assert image[0, :3, 0].tolist() == [32, 32, 32]
    assert image[0, 14:17, 0].tolist() == [240, 32, 240]
    assert image[7, 0].tolist() == [192, 192, 192, 255]
    assert image[7, 4].tolist() == [224, 224, 224, 255]
    assert image[7, 14].tolist() == [136, 0, 0, 255]
    assert execute("render_preview", root, dict(tileset="TS1", scale=4))["result"] == result
    assert (root / "project.json").read_bytes() == original
    runner = CliRunner()
    cli_result = runner.invoke(
        cli, ["-p", str(root), "preview", "--tileset", "TS1", "--scale", "4"]
    )
    assert cli_result.exit_code == 0, cli_result.output
    assert json.loads(cli_result.output)["result"]["paths"] == result["paths"]
    schema_result = runner.invoke(cli, ["schema", "op", "delete_tileset"])
    assert schema_result.exit_code == 0 and "missing_ok" in schema_result.output
    read_result = runner.invoke(cli, ["-p", str(root), "op", "get_tiles", "layer=L1", "frame=0"])
    assert (
        read_result.exit_code == 0 and json.loads(read_result.output)["result"]["tileset"] == "TS1"
    )
    deleted = runner.invoke(cli, ["-p", str(root), "op", "delete_tileset", "tileset=TS1"])
    assert deleted.exit_code == 3 and json.loads(deleted.output)["error"]["code"] == "E_IN_USE"


def test_large_tileset_preview_bounds():
    p = tile_project()
    ts = p.tilesets[0]
    ts.tiles.extend(deepcopy(ts.tiles[1]) for _ in range(1022))
    image, _ = tileset_preview(p, ts, scale=64)
    assert max(image.shape[:2]) <= 1024


def test_pixel_grid_blend_vector_keeps_document_grid_strong():
    p = new_project(width=4, height=4)
    p.layers[0].cels = [ImageCel(frame=0, x=0, y=0, w=4, h=4, pixels=["01" * 4] * 4)]
    p.canvas.grid = Grid(x=0, y=0, w=2, h=2)
    image, _ = preview_array(p, 0, scale=4, grid=True)
    assert image[5, 5].tolist() == [0, 0, 0, 255]
    assert image[4, 5].tolist() == [40, 40, 40, 255]
    assert image[4, 4].tolist() == [40, 40, 40, 255]  # Intersection blended once.
    assert image[8, 5].tolist() == [96, 96, 96, 255]


def test_empty_tileset_does_not_change_colors_used(tmp_path):
    root = tmp_path / "empty.csprite"
    execute("new_project", root, dict(width=3, height=3, transparent_index=2))
    assert execute("validate", root)["result"]["metrics"]["colors_used"] == 0
    result = execute("add_tileset", root, dict(name="Empty", tile_w=3, tile_h=3))
    assert "colors_used" not in result["validation"]["metrics_delta"]
    assert report(load_project(root))["metrics"]["colors_used"] == 0
    assert result["preview"]["paths"][0].endswith("_tileset_TS1.png")


def test_transform_description_declares_both_orders():
    description = registry().get("transform_region").description.lower()
    assert "flip is applied first, then clockwise rotation" in description
    assert "transpose, then x flip, then y flip" in description
