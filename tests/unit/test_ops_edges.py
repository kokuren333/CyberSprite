"""Cross-operation edges, palette readers, overlays and tile-aware common operations."""

import ast
from pathlib import Path

import numpy as np
import pytest

from cybersprite.core.canonical import load_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.models import Tile, TileCel, TilemapLayer, Tileset
from cybersprite.core.previews import preview_array
from cybersprite.core.projects import create_project, new_project
from cybersprite.core.render import render
from cybersprite.core.validation import check_structure
from cybersprite.formats.palette_files import presets, read_palette
from cybersprite.formats.png import decode_png
from cybersprite.ops import execute

DRAW = {"layer": "L1", "frame": 0}


@pytest.fixture
def project(tmp_path):
    p = tmp_path / "edges"
    execute("new_project", p, {"width": 8, "height": 8, "frames": 3})
    return p


def test_all_region_forms_and_cross_layer_copy(project):
    execute(
        "draw_rows", project, {**DRAW, "x": 1, "y": 1, "rows": ["010102", "010202"]}, preview="none"
    )
    execute(
        "erase",
        project,
        {**DRAW, "region": {"type": "mask", "x": 1, "y": 1, "rows": ["#.."]}},
        preview="none",
    )
    execute(
        "replace_color",
        project,
        {"from": 1, "to": 3, "region": {"type": "color", "color": 1}},
        preview="none",
    )
    execute("erase", project, {**DRAW, "region": {"type": "wand", "x": 3, "y": 1}}, preview="none")
    execute("add_layer", project, {"name": "Target"}, preview="none")
    execute(
        "transform_region",
        project,
        {
            **DRAW,
            "region": {"type": "all"},
            "action": "copy",
            "target_layer": "L2",
            "target_frame": 2,
            "dx": 1,
            "flip": "h",
            "rotate": 90,
        },
        preview="none",
    )
    assert load_project(project).layers[1].cels[0].frame == 2
    assert not check_structure(load_project(project))


def test_composite_fill_closure_and_merge_strict_errors(project):
    execute("set_pixel", project, {**DRAW, "x": 1, "y": 1, "color": 1}, preview="none")
    execute("update_layer", project, {"layer": "L1", "opacity": 128}, preview="none")
    for op, args in [
        ("fill", {**DRAW, "x": 1, "y": 1, "color": 2, "sample": "composite"}),
        ("flatten", {}),
    ]:
        with pytest.raises(CyberSpriteError) as error:
            execute(op, project, args, preview="none")
        assert error.value.code == "E_NOT_PALETTE_CLOSED"
    execute("flatten", project, {"flatten": "nearest"}, preview="none")
    assert not check_structure(load_project(project))


def test_background_resize_and_slice_transform(project):
    execute("update_layer", project, {"layer": "L1", "background": True}, preview="none")
    with pytest.raises(CyberSpriteError) as error:
        execute("set_cel", project, {**DRAW, "x": 1}, preview="none")
    assert error.value.code == "E_INVALID_ARGS"
    execute(
        "add_slice",
        project,
        {
            "name": "slice",
            "keys": [
                {
                    "frame": 0,
                    "x": 1,
                    "y": 2,
                    "w": 3,
                    "h": 4,
                    "center": {"x": 1, "y": 1, "w": 1, "h": 2},
                    "pivot": {"x": 1, "y": 2},
                }
            ],
        },
        preview="none",
    )
    execute("resize_canvas", project, {"width": 5, "height": 5, "anchor": "c"}, preview="none")
    key = load_project(project).slices[0].keys[0]
    assert (key.x, key.y) == (0, 1)
    execute("transform_sprite", project, {"rotate": 90}, preview="none")
    key = load_project(project).slices[0].keys[0]
    assert (key.x, key.y, key.w, key.h) == (0, 0, 4, 3)
    assert (key.pivot.x, key.pivot.y) == (1, 1)
    assert not check_structure(load_project(project))


def test_palette_readers_and_shrink_nearest_opaque_only(project, tmp_path):
    assert len(presets()) == 5
    assert len(read_palette("cs-circuit-16")) == 17
    assert read_palette("cs-circuit-16")[0] == "#00000000"
    values = {
        "gpl": "GIMP Palette\nName: Test\nColumns: 2\n# own test\n0 0 0 black\n255 255 255 white\n",
        "pal": "JASC-PAL\n0100\n2\n0 0 0\n255 255 255\n",
        "hex": "000000\n#ffffffff\n",
    }
    for suffix, value in values.items():
        path = tmp_path / f"palette.{suffix}"
        path.write_text(value, encoding="utf-8", newline="\n")
        assert read_palette(str(path)) == ["#000000ff", "#ffffffff"]
    execute("set_pixel", project, {**DRAW, "x": 0, "y": 0, "color": 16}, preview="none")
    execute(
        "set_palette",
        project,
        {"colors": ["#00000000", "#ffffffff"], "on_shrink": "remap_nearest"},
        preview="none",
    )
    assert execute("get_pixels", project, DRAW)["result"]["rows"] == ["01"]
    with pytest.raises(CyberSpriteError) as error:
        read_palette(str(tmp_path / "palette.png"))
    assert error.value.code == "E_IO"
    bad = tmp_path / "bad.pal"
    bad.write_text("JASC-PAL\n0100\n2\n0 0 0\n", encoding="utf-8")
    with pytest.raises(CyberSpriteError) as error:
        read_palette(str(bad))
    assert error.value.code == "E_INVALID_ARGS"


def test_preview_limit_inline_cap_and_diff_point_values(project, tmp_path):
    execute("add_frame", project, {"count": 3}, preview="none")
    result = execute(
        "apply_ops",
        project,
        {
            "ops": [
                {"op": "set_pixel", "args": {**DRAW, "frame": f, "x": 1, "y": 1, "color": 1}}
                for f in range(6)
            ]
        },
    )
    assert len(result["preview"]["paths"]) == 4 and result["preview"]["omitted_frames"] == [4, 5]
    difference = execute("diff_preview", project, {"inline": False})["result"]
    assert len(difference["frames"]) == 4 and difference["omitted_frames"] == [4, 5]
    assert difference["frames"][0]["changes"] == [[1, 1, 0, 1]]
    with pytest.raises(CyberSpriteError) as error:
        execute("diff_preview", project, {"frames": [99], "inline": False})
    assert error.value.code == "E_FRAME_OUT_OF_RANGE"
    p = new_project(width=1025, height=1)
    image, scale = preview_array(p, 0, inline=True, rulers=True)
    assert max(image.shape[:2]) <= 1024 and scale == 1
    p = load_project(project)
    image, scale = preview_array(p, 0, grid=True, rulers=True, onion={"next": 1})
    assert scale == 16 and tuple(image[0, 0]) == (240, 240, 240, 255)
    assert decode_png((project / result["preview"]["paths"][0]).read_bytes()).pixels.shape == (
        128,
        128,
        4,
    )


def test_tilemap_frame_copy_resize_crop_and_scale(tmp_path):
    p = new_project(width=4, height=4, frames=2)
    p.tilesets = [
        Tileset(
            id="TS1",
            name="test",
            tile_w=2,
            tile_h=2,
            tiles=[Tile(pixels=["0000", "0000"]), Tile(pixels=["0101", "0101"])],
        )
    ]
    p.layers += [
        TilemapLayer(
            id="L2",
            name="tiles",
            tileset="TS1",
            cels=[TileCel(frame=0, x=0, y=0, w=2, h=2, tiles=["1 1", "1 1"])],
        ),
        TilemapLayer(id="L3", name="target", tileset="TS1"),
    ]
    p.id_counters.layer, p.id_counters.tileset = 3, 1
    root = tmp_path / "tiles"
    create_project(root, p)
    execute(
        "copy_cel",
        root,
        {"layer": "L2", "frame": 0, "to_layer": "L3", "to_frame": 1},
        preview="none",
    )
    assert load_project(root).layers[2].cels[0].frame == 1
    execute("crop_canvas", root, {"rect": {"x": 1, "y": 1, "w": 2, "h": 2}}, preview="none")
    p = load_project(root)
    before = render(p, 0)
    assert np.all(before[:, :, 3] == 255) and len(p.tilesets[0].tiles) > 2
    execute("scale_sprite", root, {"factor": 2}, preview="none")
    p = load_project(root)
    assert np.array_equal(render(p, 0), np.repeat(np.repeat(before, 2, 0), 2, 1))
    assert not check_structure(p)
    before = render(p, 0)
    execute("transform_sprite", root, {"rotate": 90}, preview="none")
    np.testing.assert_array_equal(render(load_project(root), 0), np.rot90(before, -1))


def test_new_engineering_modules_use_no_float_random_or_implicit_clock():
    root = Path(__file__).resolve().parents[2] / "src/cybersprite"
    paths = list((root / "ops").glob("*.py")) + [
        root / "core" / name
        for name in ("history.py", "transactions.py", "quality.py", "registry.py", "previews.py")
    ]
    for path in paths:
        tree = ast.parse(path.read_text("utf-8"))
        for node in ast.walk(tree):
            assert not (isinstance(node, ast.Constant) and type(node.value) is float), path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "float", path
            if isinstance(node, ast.Import):
                assert all(
                    a.name.split(".")[0] not in ("random", "time", "datetime") for a in node.names
                ), path
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in ("random", "time", "datetime"), path


@pytest.mark.parametrize(
    ("op", "args"),
    [
        ("add_layer", {"name": "x" * 256}),
        ("line", {**DRAW, "x0": 0, "y0": 0, "x1": 1, "y1": 1, "color": 1, "brush": {"size": 65}}),
        ("apply_ops", {"ops": [{"op": "set_pixel", "args": {}}] * 1001}),
    ],
)
def test_resource_caps_use_limit_error(project, op, args):
    with pytest.raises(CyberSpriteError) as error:
        execute(op, project, args, preview="none")
    assert error.value.code == "E_LIMIT_EXCEEDED"


def test_identity_region_transform_counts_final_changed_pixels(project):
    execute("set_pixel", project, {**DRAW, "x": 1, "y": 1, "color": 1}, preview="none")
    result = execute(
        "transform_region", project, {**DRAW, "region": {"type": "all"}}, preview="none"
    )
    assert result["no_op"] and result["result"]["pixels_written"] == 0


def test_linked_z_index_is_local_to_the_requested_frame(project):
    execute("set_pixel", project, {**DRAW, "x": 1, "y": 1, "color": 1}, preview="none")
    execute(
        "link_cel", project, {"layer": "L1", "source_frame": 0, "frames": [1, 2]}, preview="none"
    )
    result = execute("set_cel", project, {**DRAW, "frame": 1, "z_index": 1}, preview="none")
    assert result["changed"]["linked_frames"] == []
    # The z-index changes data, but this single-layer composite remains identical.
    assert result["changed"]["frames"] == [] and result["changed"]["data"]
    assert load_project(project).layers[0].cels[1].z_index == 1
