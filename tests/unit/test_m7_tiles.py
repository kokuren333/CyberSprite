"""Tile contracts, exact D4 compositions, shared edits, and invariant preservation."""

import random
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from cybersprite.core.canonical import dumps_project, load_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.models import (
    ImageCel,
    LinkCel,
    Tile,
    TileCel,
    UserData,
)
from cybersprite.core.pixels import pixels_from_rows, pixels_to_rows
from cybersprite.core.projects import create_project, new_project
from cybersprite.core.quality import report
from cybersprite.core.registry import OpContext
from cybersprite.core.render import render, render_indexed
from cybersprite.core.validation import check_structure
from cybersprite.formats.common import export_policy
from cybersprite.formats.export import export_tileset
from cybersprite.formats.export_args import TilesetArgs
from cybersprite.ops import execute, registry
from tools.m7_cases import FLAGS, GLYPH, PALETTE, tile_project


def direct(p, opname, **args):
    op = registry().get(opname)
    return op.apply(OpContext(p, Path.cwd()), op.parse(args))


@pytest.fixture
def root(tmp_path):
    path = tmp_path / "tile.csprite"
    create_project(path, tile_project())
    return path


def run(root, opname, **args):
    return execute(opname, root, args, preview="none")


@pytest.mark.parametrize(
    "flip,expected",
    list(
        zip(
            FLAGS,
            [
                ["010000", "020000", "030302"],
                ["000001", "000002", "020303"],
                ["030302", "020000", "010000"],
                ["020303", "000002", "000001"],
                ["010203", "000003", "000002"],
                ["030201", "030000", "020000"],
                ["000002", "000003", "010203"],
                ["020000", "030000", "030201"],
            ],
            strict=True,
        )
    ),
)
def test_asymmetric_l_all_eight_hand_vectors(flip, expected):
    p = tile_project()
    p.layers[0].cels[0] = TileCel(frame=0, x=0, y=0, w=1, h=1, tiles=["1" + flip])
    np.testing.assert_array_equal(render_indexed(p)[:3, :3], pixels_from_rows(expected, 3, 3))


@pytest.mark.parametrize("flip", [None, "h", "v"])
@pytest.mark.parametrize("rotate", [0, 90, 180, 270])
def test_transform_composes_all_flags_and_preserves_tiles(flip, rotate):
    p = tile_project()
    before = render(p)
    tiles = deepcopy(p.tilesets)
    expected = np.flip(before, axis=1 if flip == "h" else 0) if flip else before
    expected = np.rot90(expected, -(rotate // 90))
    direct(p, "transform_sprite", flip=flip, rotate=rotate)
    assert not check_structure(p)
    assert p.tilesets == tiles
    np.testing.assert_array_equal(render(p), expected)
    np.testing.assert_array_equal(render(p, 1), expected)


@pytest.mark.parametrize("flip", [None, "h", "v"])
@pytest.mark.parametrize("rotate", [0, 180])
def test_non_square_flip_ignores_d_and_keeps_warning(flip, rotate):
    p = tile_project(square=False)
    before = render(p)
    expected = np.flip(before, axis=1 if flip == "h" else 0) if flip else before
    direct(p, "transform_sprite", flip=flip, rotate=rotate)
    np.testing.assert_array_equal(render(p), np.rot90(expected, -(rotate // 90)))
    issues = report(p)["issues"]
    assert any(i["rule"] == "Q-TIL-02" and i["level"] == "warning" for i in issues)


@pytest.mark.parametrize("rotate", [90, 270])
def test_non_square_quarter_turn_atomic_rejection(tmp_path, rotate):
    root = tmp_path / "rect.csprite"
    create_project(root, tile_project(square=False))
    before = (root / "project.json").read_bytes()
    with pytest.raises(CyberSpriteError) as caught:
        run(root, "transform_sprite", rotate=rotate)
    assert caught.value.code == "E_UNSUPPORTED"
    assert (root / "project.json").read_bytes() == before


def test_tile_session_contracts_and_shared_edit(root):
    for name, idem in [
        ("add_tileset", "C"),
        ("set_tile_pixels", "C"),
        ("delete_tiles", "N"),
        ("move_tiles", "N"),
        ("set_tile", "I"),
        ("set_tiles", "I"),
        ("get_tiles", "R"),
        ("tileset_from_layer", "N"),
    ]:
        assert registry().get(name).idempotency == idem
    assert registry().get("delete_tiles").destructive
    assert registry().get("tileset_from_layer").destructive
    new = run(root, "add_tileset", name="Other", tile_w=2, tile_h=1, base_index=-3)
    assert new["result"] == {"id": "TS2"}
    assert run(root, "add_tileset", name="Other", tile_w=2, tile_h=1, if_exists="reuse")["no_op"]
    new = run(root, "set_tile_pixels", tileset="TS2", tile="new", rows=["12"], format="sym")
    assert new["result"] == {"tile": 1}
    changed = run(
        root, "set_tile_pixels", tileset="TS1", tile=1, rows=["010000", "020000", "030301"]
    )
    assert [f["frame"] for f in changed["changed"]["frames"]] == [0, 1]
    assert changed["validation"]["ok"]
    assert run(root, "set_tile_pixels", tileset="TS1", tile=1, rows=["010000", "020000", "030301"])[
        "no_op"
    ]


def test_grid_origin_queries_shared_placement_and_trim(root):
    result = execute("get_tiles", root, {"layer": "L1", "frame": 1})["result"]
    assert result == dict(
        col=0, row=0, w=8, h=1, rows=[" ".join("1" + f for f in FLAGS)], tileset="TS1"
    )
    args = dict(layer="L1", frame=1, col=8, row=1, tile=1, flip="xd")
    result = run(root, "set_tile", **args)
    assert result["changed"]["linked_frames"] == [0, 1]
    assert result["validation"]["ok"]
    assert run(root, "set_tile", **args)["no_op"]
    result = execute(
        "get_tiles", root, {"layer": "L1", "frame": 1, "rect": dict(x=7, y=0, w=2, h=2)}
    )["result"]
    assert result["rows"] == ["1xyd 0", "0 1xd"]
    run(root, "set_tiles", layer="L1", frame=1, col=0, row=0, rows=["0 " * 8 + "0"])
    p = load_project(root)
    cel = p.layers[0].cels[0]
    assert (cel.x, cel.y, cel.w, cel.h, cel.tiles) == (25, 5, 1, 1, ["1xd"])
    run(root, "set_tile", layer="L1", frame=1, col=8, row=1, tile=0)
    assert load_project(root).layers[0].cels == []
    assert execute("get_tiles", root, {"layer": "L1", "frame": 0})["result"]["rows"] == []


@pytest.mark.parametrize(
    "op,args,code",
    [
        ("set_tile_pixels", dict(tileset="TS1", tile=0, rows=GLYPH), "E_INVALID_ARGS"),
        ("set_tile_pixels", dict(tileset="TS1", tile=8, rows=GLYPH), "E_INVALID_ARGS"),
        ("set_tile_pixels", dict(tileset="TS1", tile=1, rows=["0101"]), "E_INVALID_ARGS"),
        (
            "set_tile_pixels",
            dict(tileset="TS1", tile=1, rows=["ff0000"] * 3),
            "E_INDEX_OUT_OF_RANGE",
        ),
        ("delete_tiles", dict(tileset="TS1", tiles=[0]), "E_INVALID_ARGS"),
        ("delete_tiles", dict(tileset="TS1", tiles=[1]), "E_INVALID_ARGS"),
        ("move_tiles", dict(tileset="TS1", **{"from": 1, "to": 1, "before": 0}), "E_INVALID_ARGS"),
        ("set_tile", dict(layer="L1", frame=0, col=9, row=0, tile=1), "E_OUT_OF_CANVAS"),
        ("set_tile", dict(layer="L1", frame=0, col=-1, row=0, tile=1), "E_OUT_OF_CANVAS"),
        ("set_tile", dict(layer="L1", frame=0, col=0, row=0, tile=0, flip="x"), "E_INVALID_ARGS"),
        ("set_tiles", dict(layer="L1", frame=0, col=0, row=0, rows=["1 1", "1"]), "E_INVALID_ARGS"),
        ("set_tiles", dict(layer="L1", frame=0, col=0, row=0, rows=["2"]), "E_INVALID_ARGS"),
        ("set_tiles", dict(layer="L1", frame=0, col=0, row=0, rows=[]), "E_INVALID_ARGS"),
        ("set_tiles", dict(layer="L1", frame=2, col=0, row=0, rows=["1"]), "E_FRAME_OUT_OF_RANGE"),
        ("add_tileset", dict(name="Glyphs", tile_w=3, tile_h=3), "E_EXISTS"),
        ("set_tile_pixels", dict(tileset="missing", tile=1, rows=GLYPH), "E_TILESET_NOT_FOUND"),
    ],
)
def test_tile_errors_rollback(root, op, args, code):
    before = (root / "project.json").read_bytes()
    with pytest.raises(CyberSpriteError) as caught:
        run(root, op, **args)
    assert caught.value.code == code
    assert (root / "project.json").read_bytes() == before


def test_delete_and_move_preserve_metadata_links_and_pixels(root):
    run(root, "set_tile_pixels", tileset="TS1", tile="new", rows=["020202"] * 3)
    run(root, "set_tile_pixels", tileset="TS1", tile="new", rows=["030303"] * 3)
    run(root, "set_tile", layer="L1", frame=0, col=8, row=0, tile=3, flip="xy")
    before = render(load_project(root))
    result = run(root, "move_tiles", tileset="TS1", **{"from": 3, "to": 3, "before": 1})
    assert result["result"]["mapping"] == {"0": 0, "1": 2, "2": 3, "3": 1}
    assert result["changed"]["frames"] == []
    np.testing.assert_array_equal(render(load_project(root)), before)
    result = run(root, "delete_tiles", tileset="TS1", tiles=[3, 3])
    assert result["changed"]["frames"] == []
    p = load_project(root)
    assert isinstance(p.layers[0].cels[1], LinkCel)
    assert p.layers[0].cels[0].tiles[0].endswith("1xy")
    np.testing.assert_array_equal(render(p), before)
    result = run(root, "delete_tiles", tileset="TS1", tiles=[1], on_used="clear")
    assert result["validation"]["ok"]
    assert load_project(root).layers[0].cels[0].tiles[0] == " ".join("1" + f for f in FLAGS)


@pytest.mark.parametrize("match", [False, True])
def test_from_layer_dedupes_flips_pads_edges_and_preserves_links(match):
    p = new_project(width=9, height=6, frames=3, palette=PALETTE)
    p.layers[0].cels = [
        ImageCel(
            frame=0,
            x=1,
            y=2,
            w=7,
            h=3,
            pixels=["01020102020103", "03000300000300", "01010101010101"],
            user_data=UserData(text="cel"),
        ),
        LinkCel(frame=1, link=0),
        ImageCel(frame=2, x=0, y=0, w=2, h=2, pixels=["0102", "0300"]),
    ]
    before = [render(p, f) for f in range(3)]
    result = direct(
        p,
        "tileset_from_layer",
        layer="L1",
        tile_w=2,
        tile_h=2,
        match_flips=dict(x=match, y=match, d=match),
    )
    # Canvas x=0 grid adds transparent left padding; the frame-2 block matches tile 2x.
    assert result == {
        "tileset": "TS1",
        "tiles": 7 if not match else 6,
        "tiles_total": 8 if not match else 7,
    }
    assert p.layers[0].id == "L1" and p.layers[0].name == "Layer 1"
    assert p.layers[0].cels[0].user_data.text == "cel"
    assert p.layers[0].cels[1] == LinkCel(frame=1, link=0)
    assert not check_structure(p)
    assert p.layers[0].cels[0].tiles == ["1 2 3 4", "5 6 6 6"]
    if match:
        assert p.layers[0].cels[2].tiles == ["2x"]
    for f in range(3):
        np.testing.assert_array_equal(render(p, f), before[f])


def test_replace_color_scale_tile_zero_and_undo(root):
    p = load_project(root)
    before = render(p)
    run(root, "scale_sprite", factor=2)
    p = load_project(root)
    assert (p.tilesets[0].tile_w, p.tilesets[0].tile_h) == (6, 6)
    np.testing.assert_array_equal(render(p), before.repeat(2, 0).repeat(2, 1))
    run(root, "undo")
    result = run(root, "replace_color", **{"from": 0, "to": 2, "tilesets": True})
    assert result["result"]["pixels_written"] == 4
    assert load_project(root).tilesets[0].tiles[0].pixels == ["000000"] * 3
    assert result["validation"]["ok"]


def test_quality_unused_duplicate_and_diagonal_resolution(root):
    run(root, "set_tile_pixels", tileset="TS1", tile="new", rows=GLYPH)
    issues = execute("validate", root)["result"]["issues"]
    assert any(i["rule"] == "Q-TIL-01" for i in issues)
    result = run(root, "delete_tiles", tileset="TS1", tiles=[2])
    assert any(i["rule"] == "Q-TIL-01" for i in result["validation"]["resolved_issues"])
    p = tile_project(square=False)
    direct(p, "set_tiles", layer="L1", frame=0, col=0, row=1, rows=["1 " * 8])
    assert not any(i["rule"].startswith("Q-TIL") for i in report(p)["issues"])


@pytest.mark.parametrize(
    "mutation,rule",
    [
        (lambda p: setattr(p.tilesets[0].tiles[0], "pixels", GLYPH), "S-09"),
        (lambda p: setattr(p.tilesets[0].tiles[1], "pixels", ["01"]), "S-09"),
        (lambda p: setattr(p.layers[0], "tileset", "TS99"), "S-10"),
        (lambda p: setattr(p.layers[0].cels[0], "tiles", ["0x " + "1 " * 7]), "S-10"),
        (lambda p: setattr(p.layers[0].cels[0], "tiles", ["2 " * 8]), "S-10"),
    ],
)
def test_structural_tile_invariants(mutation, rule):
    p = tile_project()
    mutation(p)
    assert rule in {i.rule for i in check_structure(p)}


@pytest.mark.parametrize("layout", ["horizontal", "vertical", "rows", "columns", "packed"])
def test_tileset_export_layout_metadata_and_scale(tmp_path, layout):
    import json

    from PIL import Image

    p = tile_project()
    p.tilesets[0].tiles[1].user_data = UserData(text="glyph", properties={"solid": True})
    p.tilesets[0].tiles.append(Tile(pixels=["020202"] * 3))
    with export_policy(tmp_path):
        result = export_tileset(
            p,
            TilesetArgs(
                tileset="TS1",
                out="tiles.png",
                data_out="tiles.json",
                layout=layout,
                scale=2,
                spacing=1,
                border=2,
                include_empty=True,
            ),
        )
    assert result["verified"] and result["validation_ok"]
    data = json.loads((tmp_path / "tiles.json").read_bytes())
    actual = np.asarray(Image.open(tmp_path / "tiles.png").convert("RGBA"))
    assert [t["index"] for t in data["tiles"]] == [0, 1, 2]
    assert data["tileset"] == "TS1" and data["name"] == "Glyphs"
    assert (data["tile_w"], data["tile_h"], data["base_index"]) == (3, 3, 1)
    assert data["size"] == {"w": actual.shape[1], "h": actual.shape[0]}
    assert [t["display_index"] for t in data["tiles"]] == [1, 2, 3]
    assert data["tiles"][1]["user_data"]["text"] == "glyph"
    table = np.array(
        [[0, 0, 0, 0], [136, 0, 0, 255], [0, 136, 0, 255], [0, 0, 136, 255]], dtype=np.uint8
    )
    for item in data["tiles"]:
        r = item["rect"]
        expected = table[pixels_from_rows(p.tilesets[0].tiles[item["index"]].pixels, 3, 3)]
        np.testing.assert_array_equal(
            actual[r["y"] : r["y"] + r["h"], r["x"] : r["x"] + r["w"]],
            expected.repeat(2, 0).repeat(2, 1),
        )


def test_seeded_mutations_keep_invariants_and_undo(root):
    rng = random.Random(501)
    for _ in range(25):
        before = load_project(root)
        if rng.randrange(2):
            args = dict(
                layer="L1",
                frame=rng.randrange(2),
                col=rng.randrange(8),
                row=0,
                tile=1,
                flip=rng.choice(FLAGS),
            )
            result = run(root, "set_tile", **args)
            assert run(root, "set_tile", **args)["no_op"]
        else:
            values = pixels_to_rows(
                np.array([[rng.randrange(4) for _ in range(3)] for _ in range(3)], dtype=np.uint8)
            )
            result = run(root, "set_tile_pixels", tileset="TS1", tile=1, rows=values)
        after = load_project(root)
        assert not check_structure(after)
        assert result["validation"]["ok"] == report(after)["ok"]
        if not result["no_op"]:
            run(root, "undo")
            restored = load_project(root)
            restored.revision = before.revision
            assert dumps_project(restored) == dumps_project(before)


def test_move_every_range_and_insertion_keeps_composite_and_user_data():
    original = tile_project()
    ts = original.tilesets[0]
    for i in range(2, 6):
        ts.tiles.append(Tile(pixels=[f"0{i % 3 + 1}" * 3] * 3, user_data=UserData(text=str(i))))
    original.layers[0].cels[0].tiles = ["1 2x 3y 4d 5xyd 1 2 3"]
    expected = render(original)
    for start in range(1, 6):
        for end in range(start, 6):
            for before in range(1, 7):
                p = deepcopy(original)
                result = direct(
                    p, "move_tiles", tileset="TS1", **{"from": start, "to": end, "before": before}
                )
                for old, new in result["mapping"].items():
                    assert p.tilesets[0].tiles[new] == ts.tiles[int(old)]
                assert not check_structure(p)
                np.testing.assert_array_equal(render(p), expected)


@pytest.mark.parametrize(
    "match", [{"x": True}, {"y": True}, {"d": True}, {"x": True, "y": True, "d": True}]
)
def test_conversion_dedupe_each_enabled_reflection(match):
    p = tile_project()
    data = render_indexed(p)
    from cybersprite.core.models import ImageLayer

    p.layers = [
        ImageLayer(
            id="L1",
            name="Image",
            cels=[
                ImageCel(frame=0, x=0, y=0, w=27, h=9, pixels=pixels_to_rows(data)),
            ],
        )
    ]
    # Place blocks on exact cell boundaries, independently of the source map origin.
    blocks = [pixels_from_rows(GLYPH, 3, 3)]
    for flag in FLAGS[1:]:
        block = blocks[0].T if "d" in flag else blocks[0]
        if "x" in flag:
            block = block[:, ::-1]
        if "y" in flag:
            block = block[::-1]
        blocks.append(block)
    p.layers[0].cels[0] = ImageCel(
        frame=0, x=0, y=0, w=24, h=3, pixels=pixels_to_rows(np.concatenate(blocks, axis=1))
    )
    before = render(p)
    direct(p, "tileset_from_layer", layer="L1", tile_w=3, tile_h=3, match_flips=match)
    assert len(p.tilesets[1].tiles) == (2 if len(match) == 3 else 5)
    np.testing.assert_array_equal(render(p), before)


def test_tile_ops_batch_rollback_dry_run_and_replay(root):
    before = (root / "project.json").read_bytes()
    args = dict(tileset="TS1", tile="new", rows=GLYPH)
    dry = execute("set_tile_pixels", root, args, dry_run=True, preview="none")
    assert dry["dry_run"] and (root / "project.json").read_bytes() == before
    first = execute("set_tile_pixels", root, args, idempotency_key="append-once", preview="none")
    again = execute("set_tile_pixels", root, args, idempotency_key="append-once", preview="none")
    assert again["replayed"] and again["result"] == first["result"]
    assert len(load_project(root).tilesets[0].tiles) == 3
    before = (root / "project.json").read_bytes()
    with pytest.raises(CyberSpriteError):
        run(
            root,
            "apply_ops",
            ops=[
                {"op": "set_tile_pixels", "args": args},
                {"op": "delete_tiles", "args": {"tileset": "TS1", "tiles": [1]}},
            ],
        )
    assert (root / "project.json").read_bytes() == before
    run(root, "update_layer", layer="L1", locked=True)
    for op, options in [
        ("set_tile_pixels", args),
        ("replace_color", {"from": 1, "to": 2, "tilesets": True}),
    ]:
        with pytest.raises(CyberSpriteError) as error:
            run(root, op, **options)
        assert error.value.code == "E_LAYER_LOCKED"


def test_export_more_than_frame_limit_and_empty_set(tmp_path):
    import json

    p = new_project(width=1, height=1, palette=PALETTE)
    direct(p, "add_tileset", name="Large", tile_w=1, tile_h=1)
    with export_policy(tmp_path):
        result = export_tileset(
            p, TilesetArgs(tileset="TS1", out="empty.png", data_out="empty.json")
        )
        assert (
            result["verified"] and json.loads((tmp_path / "empty.json").read_bytes())["tiles"] == []
        )
        p.tilesets[0].tiles.extend(Tile(pixels=["01"]) for _ in range(4097))
        result = export_tileset(
            p, TilesetArgs(tileset="TS1", out="large.png", data_out="large.json")
        )
        assert result["verified"]
        assert len(json.loads((tmp_path / "large.json").read_bytes())["tiles"]) == 4097
