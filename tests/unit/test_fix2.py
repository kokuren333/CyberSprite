"""Animation production regressions: decoration, links, and export contracts."""

import base64
import json

import numpy as np
import pytest
from click.testing import CliRunner

from cybersprite.cli import cli
from cybersprite.core.canonical import load_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.history import retain_previews
from cybersprite.core.models import ImageCel, Tag
from cybersprite.core.previews import composite_preview, preview_array
from cybersprite.core.projects import new_project
from cybersprite.core.render import render
from cybersprite.formats.common import export_policy
from cybersprite.formats.export import export_palette, export_sheet
from cybersprite.formats.export_args import ExportResult, PaletteArgs, SheetArgs
from cybersprite.formats.palette_files import decode_palette
from cybersprite.formats.png import decode_png
from cybersprite.mcp.contracts import describe
from cybersprite.ops import execute, registry


@pytest.fixture
def animation(tmp_path):
    path = tmp_path / "animation.csprite"
    execute("new_project", path, {"width": 8, "height": 8, "frames": 10})
    execute("add_tag", path, {"name": "walk", "from": 0, "to": 7}, preview="none")
    return path


@pytest.mark.parametrize(
    "selection,expected",
    [(0, [0]), ([3, 1, 1], [1, 3]), ("2-4", [2, 3, 4]), ("tag:walk", list(range(8)))],
)
def test_preview_common_specifiers(animation, selection, expected):
    result = execute("render_preview", animation, {"frames": selection, "inline": False})["result"]
    assert [int(path.rsplit("_f", 1)[1][:-4]) for path in result["paths"]] == expected


@pytest.mark.parametrize("selection", ["all", "0-9", list(range(10))])
def test_preview_limit_message(animation, selection):
    with pytest.raises(CyberSpriteError) as error:
        execute("render_preview", animation, {"frames": selection})
    assert error.value.code == "E_LIMIT_EXCEEDED"
    assert "at most 8 frames per call; use layout=strip or a smaller range" in error.value.message


@pytest.mark.parametrize("layout", ["strip", "grid"])
@pytest.mark.parametrize("selection", ["all", "0-9", "tag:walk", list(range(10))])
def test_composite_all_selectors_inline_and_determinism(animation, layout, selection):
    args = {"frames": selection, "layout": layout, "background": "#123456"}
    before = (animation / "project.json").read_bytes()
    first = execute("render_preview", animation, args)["result"]
    second = execute("render_preview", animation, args)["result"]
    assert first == second
    assert len(first["paths"]) == len(first["images"]) == 1
    data = (animation / first["paths"][0]).read_bytes()
    assert data == base64.b64decode(first["images"][0])
    pixels = decode_png(data).rgba()
    assert pixels.shape[:2] == (first["height"], first["width"])
    assert max(pixels.shape[:2]) <= 1024
    assert (animation / "project.json").read_bytes() == before


def test_composite_label_gap_and_frame_positions_vector():
    p = new_project(width=2, height=2, frames=2)
    p.layers[0].cels = [ImageCel(frame=f, x=0, y=0, w=1, h=1, pixels=["01"]) for f in range(2)]
    image, scale = composite_preview(p, [0, 1], layout="strip", scale=1, background="#ffffff")
    assert image.shape == (9, 8, 4) and scale == 1
    assert image[0, :3].tolist() == [[32, 32, 32, 255]] * 3  # Digit zero.
    assert image[7, 0].tolist() == image[7, 5].tolist() == [0, 0, 0, 255]
    assert image[7, 3:5].tolist() == [[240, 240, 240, 255]] * 2


@pytest.mark.parametrize(
    "layout,count,width",
    [("strip", 4096, 1), ("grid", 4096, 1), ("strip", 3, 1200), ("grid", 3, 1200)],
)
def test_composite_frame_limit_and_oversize_sampling(layout, count, width):
    p = new_project(width=width, height=1, frames=count)
    image, _ = composite_preview(p, list(range(count)), layout=layout, rulers=True)
    assert max(image.shape[:2]) <= 1024


@pytest.mark.parametrize(
    "background,expected",
    [("#123456", [18, 52, 86, 255]), (2, [255, 255, 255, 255]), ("checker", [192, 192, 192, 255])],
)
def test_preview_background_is_decoration(background, expected):
    p = new_project(width=2, height=2)
    before = render(p, 0).copy()
    pixels, _ = preview_array(p, 0, scale=1, background=background)
    assert pixels[0, 0].tolist() == expected
    np.testing.assert_array_equal(render(p, 0), before)


def onion_project():
    p = new_project(width=4, height=1, frames=4)
    p.tags = [Tag(id="T1", name="walk", **{"from": 0}, to=3)]
    p.layers[0].cels = [ImageCel(frame=f, x=f, y=0, w=1, h=1, pixels=["01"]) for f in range(4)]
    return p


def test_onion_tints_alpha_and_loop_fixed_vectors():
    p = onion_project()
    before = render(p, 1).copy()
    pixels, _ = preview_array(p, 1, scale=1, onion={"prev": 1, "next": 1})
    assert pixels[0].tolist() == [
        [208, 144, 144, 255],
        [0, 0, 0, 255],
        [144, 160, 208, 255],
        [192, 192, 192, 255],
    ]
    np.testing.assert_array_equal(render(p, 1), before)
    plain, _ = preview_array(p, 0, scale=1, onion={"prev": 1})
    wrapped, _ = preview_array(p, 0, scale=1, onion={"prev": 1, "loop_tag": "walk"})
    assert plain[0, 3].tolist() == [192, 192, 192, 255]
    assert wrapped[0, 3].tolist() == [208, 144, 144, 255]
    reverse, _ = preview_array(p, 3, scale=1, onion={"next": 1, "loop_tag": "T1"})
    assert reverse[0, 0].tolist() == [144, 160, 208, 255]


def test_onion_preserves_ghost_alpha_and_rejects_outside_tag():
    p = onion_project()
    p.palette.colors[1] = "#00000080"
    image, _ = preview_array(p, 1, scale=1, onion={"prev": 1}, background="#000000")
    assert image[0, 0].tolist() == [56, 24, 24, 255]
    p.tags[0].from_ = 1
    with pytest.raises(CyberSpriteError, match="within loop_tag"):
        preview_array(p, 0, onion={"prev": 1, "loop_tag": "walk"})


def test_link_owner_and_separate_transaction_groups(animation):
    for owner, target in [(0, 1), (2, 3)]:
        execute(
            "set_pixel",
            animation,
            {"layer": "L1", "frame": owner, "x": 0, "y": 0, "color": 1},
            preview="none",
        )
        execute(
            "link_cel",
            animation,
            {"layer": "L1", "source_frame": owner, "frames": target},
            preview="none",
        )
    layers = execute("get_info", animation, {"include": ["layers"]})["result"]["layers"]
    assert layers[0]["link_groups"] == [[0, 1], [2, 3]]
    assert [cel.get("link") for cel in layers[0]["cels"]] == [None, 0, None, 2]
    result = execute(
        "apply_ops",
        animation,
        {
            "ops": [
                {"op": "set_pixel", "args": {"layer": "L1", "frame": f, "x": 1, "y": 0, "color": 2}}
                for f in [0, 1, 2, 3]
            ]
        },
        preview="none",
    )
    assert result["changed"]["linked_frames"] == [0, 1, 2, 3]
    assert result["changed"]["link_groups"] == [[0, 1], [2, 3]]


@pytest.mark.parametrize("format", ["gpl", "pal", "hex", "png"])
def test_palette_real_transparent_rgb_and_data_contract(tmp_path, format):
    p = new_project(width=2, height=2, palette=["#102030ff", "#44556600"])
    p.palette.transparent_index = 1
    with export_policy(tmp_path):
        result = export_palette(p, PaletteArgs(out="palette." + format))
    ExportResult.model_validate(result)
    colors, _ = decode_palette((tmp_path / ("palette." + format)).read_bytes(), format)
    assert colors[1][:7] == "#445566"
    file = result["files"][0]
    if format == "png":
        assert {"width", "height", "pixel_sha256"} <= file.keys()
        assert colors[1] == "#44556600"
        assert not any(w.get("code") == "W_PALETTE_TRANSPARENT_ENTRY" for w in result["warnings"])
    else:
        assert set(file) == {"kind", "path", "bytes", "sha256"} and file["kind"] == "data"
        warning = next(
            w for w in result["warnings"] if w.get("code") == "W_PALETTE_TRANSPARENT_ENTRY"
        )
        assert warning["index"] == 1 and "index 1" in warning["message"]
        assert colors[1] == "#445566ff"


def test_sheet_data_and_mcp_output_schema(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    p = new_project(width=2, height=2)
    with export_policy(tmp_path):
        result = export_sheet(p, SheetArgs(out="sheet.png", data_out="sheet.json"))
    schema = describe(registry().get("export_sheet"))["outputSchema"]
    envelope = {
        "ok": True,
        "op": "export_sheet",
        "project": "p.csprite",
        "revision": 0,
        "result": result,
    }
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(envelope)
    assert set(result["files"][1]) == {"kind", "path", "bytes", "sha256"}
    result["files"][1]["width"] = 0
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(envelope)


def test_cli_preview_specifiers_layout_and_onion_shorthand(animation, tmp_path):
    runner = CliRunner()
    out = tmp_path / "walk.png"
    result = runner.invoke(
        cli,
        [
            "-p",
            str(animation),
            "preview",
            "--frames",
            "tag:walk",
            "--layout",
            "strip",
            "--background",
            "#ffffff",
            "--onion",
            "1,1",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["result"]["paths"] == [str(out)]
    assert max(decode_png(out.read_bytes()).rgba().shape[:2]) <= 1024
    assert load_project(animation).revision == 1


@pytest.mark.parametrize("command", ["image", "sheet", "anim", "aseprite", "tileset", "palette"])
def test_export_help_placeholder_descriptions(command):
    result = CliRunner().invoke(cli, ["export", command, "--help"])
    assert result.exit_code == 0
    assert "{frame:02}" in result.output and "{frame1}" in result.output


@pytest.mark.parametrize("op", ["add_tag", "update_tag", "add_slice", "update_slice"])
def test_display_color_arg_descriptions(op):
    description = registry().get(op).args.model_fields["color"].description
    assert "#rrggbb" in description and "need not belong" in description


def test_composite_retention(tmp_path):
    folder = tmp_path / ".cybersprite/previews"
    folder.mkdir(parents=True)
    for revision in range(101):
        for suffix in ["strip", "grid", "f0"]:
            (folder / f"r{revision:06d}_{suffix}.png").write_bytes(b"preview")
    retain_previews(tmp_path)
    assert len(list(folder.iterdir())) == 300
    assert not list(folder.glob("r000000_*"))
