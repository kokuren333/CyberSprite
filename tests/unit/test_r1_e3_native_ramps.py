"""Native bitplane vectors and material ramps through real Ops and round trips."""

import json
from pathlib import Path
from random import Random

import numpy as np
import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from cybersprite import ops
from cybersprite.cli import cli
from cybersprite.core.canonical import dumps_project, load_project, loads_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.models import ImageCel, Palette
from cybersprite.core.pixels import pixels_to_rows, resolve_color
from cybersprite.core.projects import create_project, new_project
from cybersprite.core.quality import report
from cybersprite.core.render import render
from cybersprite.formats.aseprite_io import encode_aseprite, read_aseprite
from cybersprite.formats.common import export_policy
from cybersprite.formats.native import (
    GBExporter,
    NativeArgs,
    NativeOptions,
    decode_gb,
    encode_gb,
    export_native,
)
from cybersprite.platforms import resolve


@pytest.fixture(autouse=True)
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_CONFIG_DIR", str(tmp_path / "config"))


def vector():
    spec = json.loads(Path("tests/vectors/native/gb-2bpp.json").read_text("utf-8"))
    image = np.array([[int(c) for c in row] for row in spec["rows"]], dtype=np.uint8)
    return image, bytes.fromhex(spec["hex"])


def native_project():
    p = new_project(width=8, height=8, palette=["#00000000", "#000000ff", "#ffffffff", "#555555ff"])
    data, _ = vector()
    p.layers[0].cels = [ImageCel(frame=0, x=0, y=0, w=8, h=8, pixels=pixels_to_rows(data))]
    p.platform = resolve("dmg")
    return p


def test_hand_vector_and_seeded_native_property():
    data, raw = vector()
    assert encode_gb([data]) == raw
    assert np.array_equal(decode_gb(raw)[0], data)
    rng = Random(1501)
    samples = [
        np.array([[rng.randrange(4) for _ in range(8)] for _ in range(8)], dtype=np.uint8)
        for _ in range(100)
    ]
    assert all(
        np.array_equal(a, b) for a, b in zip(samples, decode_gb(encode_gb(samples)), strict=True)
    )
    with pytest.raises(CyberSpriteError):
        decode_gb(b"\0")


def test_native_real_op_and_plugin_point(tmp_path):
    p, root = native_project(), tmp_path / "p"
    create_project(root, p)
    with export_policy(tmp_path):
        result = ops.execute("export_native", root, {"out": "tiles.2bpp", "layer": "L1"})
        via_plugin = ops.execute(
            "export_plugin",
            root,
            {"out": "plugin.2bpp", "format": "gb-2bpp", "options": {"layer": "L1"}},
        )
    assert result["result"]["validation_ok"] and result["result"]["verified"]
    assert via_plugin["result"]["verified"]
    assert (tmp_path / "tiles.2bpp").read_bytes() == vector()[1]
    assert (tmp_path / "plugin.2bpp").read_bytes() == vector()[1]
    assert CliRunner().invoke(cli, ["export", "native", "--help"]).exit_code == 0


@pytest.mark.parametrize(
    "problem", ["rows", "alpha", "alpha0", "size", "forbidden", "color", "opacity"]
)
def test_native_refuses_loss_even_with_quality_disabled(tmp_path, problem):
    p = native_project()
    p.validation.severity.update({f"Q-PLT-0{i}": "off" for i in range(1, 9)})
    if problem == "rows":
        p.palette.colors.extend(["#ffffffff"] * 4)
        p.layers[0].cels[0].pixels[0] = "0105010101010101"
    elif problem == "alpha":
        p.palette.colors[1] = "#00000080"
    elif problem == "alpha0":
        p.palette.colors[1] = "#00000000"
    elif problem == "size":
        p.canvas.width = 9
    elif problem == "forbidden":
        p.palette.colors.extend(["#ffffffff"] * 4)
        p.layers[0].cels[0].pixels[0] = "04" * 8
    elif problem == "color":
        p.palette.colors[1] = "#123456ff"
    else:
        p.layers[0].opacity = 128
    out = tmp_path / "unchanged.2bpp"
    out.write_bytes(b"previous")
    with export_policy(tmp_path), pytest.raises(CyberSpriteError):
        export_native(p, NativeArgs(out=out.name, layer="L1", allow_invalid=True), tmp_path / "p")
    assert out.read_bytes() == b"previous"


def test_native_color_slot_mapping_and_protected_destination(tmp_path):
    p = native_project()
    p.palette.colors.append("#aaaaaaff")
    p.platform = resolve("dmg/background")
    data, expected = vector()
    p.layers[0].cels[0].pixels = pixels_to_rows(data + 1)
    with export_policy(tmp_path):
        result = export_native(p, NativeArgs(out="background.2bpp", layer="L1", allow_invalid=True))
    assert result["verified"] and (tmp_path / "background.2bpp").read_bytes() == expected
    root = tmp_path / "p"
    create_project(root, native_project())
    before = (root / "project.json").read_bytes()
    with export_policy(tmp_path), pytest.raises(CyberSpriteError) as error:
        export_native(native_project(), NativeArgs(out="p/project.json", layer="L1"), root)
    assert error.value.code == "E_PATH_NOT_ALLOWED"
    assert (root / "project.json").read_bytes() == before


def test_native_corrupt_decoder_preserves_output(tmp_path, monkeypatch):
    out = tmp_path / "tiles.2bpp"
    out.write_bytes(b"previous")
    monkeypatch.setattr(GBExporter, "decode", lambda self, _: [np.zeros((8, 8, 4), dtype=np.uint8)])
    with export_policy(tmp_path), pytest.raises(CyberSpriteError, match="differs"):
        export_native(native_project(), NativeArgs(out=out.name, layer="L1"))
    assert out.read_bytes() == b"previous"


def test_native_tileset_includes_zero_and_linked_frames(tmp_path):
    root = tmp_path / "p"
    create_project(root, native_project())
    added = ops.execute(
        "add_tileset", root, {"name": "native", "tile_w": 8, "tile_h": 8}, preview="none"
    )
    ts = added["result"]["id"]
    ops.execute(
        "set_tile_pixels",
        root,
        {"tileset": ts, "tile": "new", "rows": pixels_to_rows(vector()[0]), "format": "hex"},
        preview="none",
    )
    with export_policy(tmp_path):
        exported = ops.execute("export_native", root, {"out": "set.2bpp", "tileset": ts})
    assert exported["result"]["verified"]
    assert (tmp_path / "set.2bpp").read_bytes() == b"\0" * 16 + vector()[1]
    ops.execute("add_frame", root, {}, preview="none")
    ops.execute("link_cel", root, {"layer": "L1", "source_frame": 0, "frames": [1]}, preview="none")
    with export_policy(tmp_path):
        ops.execute("export_native", root, {"out": "linked.2bpp", "layer": "L1"})
    assert (tmp_path / "linked.2bpp").read_bytes() == vector()[1] * 2


def test_native_rejects_sidecars_before_output(tmp_path):
    with export_policy(tmp_path), pytest.raises(CyberSpriteError) as error:
        export_native(native_project(), NativeArgs(out="out.2bpp", layer="L1", map_out="map.json"))
    assert error.value.code == "E_UNSUPPORTED" and not (tmp_path / "out.2bpp").exists()


def ramp_project(root):
    colors = ["#00000000", "#000000ff", "#555555ff", "#aaaaaaff", "#ffffffff"]
    ops.execute("new_project", root, {"width": 8, "height": 8, "palette": colors}, preview="none")
    ops.execute(
        "set_palette",
        root,
        {"colors": colors, "ramps": [{"name": "body", "indices": [1, 2, 3, 4]}]},
        preview="none",
    )
    return colors


def test_ramp_refs_shift_mask_link_and_undo(tmp_path):
    root = tmp_path / "p"
    ramp_project(root)
    ops.execute(
        "draw_rows",
        root,
        {"layer": "L1", "frame": 0, "x": 2, "y": 2, "rows": ["01020304"], "format": "hex"},
        preview="none",
    )
    palette = load_project(root).palette
    assert resolve_color(palette, "@body:0") == 1 and resolve_color(palette, "@body:3") == 4
    for ref in ("@body:-1", "@body:4", "@missing:0", "@body:01"):
        with pytest.raises(CyberSpriteError):
            resolve_color(palette, ref)
    result = ops.execute(
        "shift_ramp",
        root,
        {"layer": "L1", "frame": 0, "direction": "lighter", "mask": {"only_on": [1, 3]}},
        preview="none",
    )
    assert result["result"]["pixels_written"] == 2
    assert result["validation"]["ok"]
    data = ops.execute("get_pixels", root, {"layer": "L1", "frame": 0, "format": "hex"})
    assert "02020404" in "".join(data["result"]["rows"])
    ops.execute("undo", root, {}, preview="none")
    assert resolve_color(load_project(root).palette, "@body:2") == 3
    assert ops.execute("get_palette", root)["result"]["ramps"][0]["name"] == "body"


def test_selective_outline_and_ramp_craft(tmp_path):
    root = tmp_path / "p"
    ramp_project(root)
    ops.execute(
        "set_pixel",
        root,
        {"layer": "L1", "frame": 0, "x": 3, "y": 3, "color": "@body:2"},
        preview="none",
    )
    ops.execute(
        "outline", root, {"layer": "L1", "frame": 0, "color": 4, "selective": True}, preview="none"
    )
    p = load_project(root)
    image = render(p, 0)
    assert image[3, 2].tolist() == [0, 0, 0, 255]
    p.platform = resolve({"craft": {"ramp_steps": [3, 4]}})
    result = report(p)
    assert result["metrics"]["platform"]["craft"]["frames"][0]["ramp_steps"] == {"body": 2}
    assert any(
        i["rule"] == "Q-CRF-01" and i["where"]["metric"] == "ramp_steps.body"
        for i in result["issues"]
    )


def test_shift_linked_frames_and_clamped_endpoints(tmp_path):
    root = tmp_path / "p"
    ramp_project(root)
    ops.execute(
        "set_pixel",
        root,
        {"layer": "L1", "frame": 0, "x": 3, "y": 3, "color": "@body:0"},
        preview="none",
    )
    ops.execute("add_frame", root, {}, preview="none")
    ops.execute("link_cel", root, {"layer": "L1", "source_frame": 0, "frames": [1]}, preview="none")
    dark = ops.execute(
        "shift_ramp", root, {"layer": "L1", "frame": 1, "direction": "darker"}, preview="none"
    )
    assert dark["no_op"]
    changed = ops.execute(
        "shift_ramp", root, {"layer": "L1", "frame": 1, "direction": "lighter"}, preview="none"
    )
    assert changed["changed"]["linked_frames"] == [0, 1]
    p = load_project(root)
    assert np.array_equal(render(p, 0), render(p, 1))


def test_ramp_remove_unused_and_collision_rollback(tmp_path):
    root = tmp_path / "p"
    ramp_project(root)
    ops.execute(
        "set_pixel", root, {"layer": "L1", "frame": 0, "x": 0, "y": 0, "color": 2}, preview="none"
    )
    ops.execute("remap_palette", root, {"remove_unused": True}, preview="none")
    assert load_project(root).palette.ramps[0].indices == [1]


@pytest.mark.parametrize(
    "ramps",
    [
        [{"name": "a", "indices": [0]}],
        [{"name": "a", "indices": [1, 1]}],
        [{"name": "a", "indices": [9]}],
        [{"name": "a", "indices": []}],
        [{"name": "a", "indices": [1]}, {"name": "a", "indices": [2]}],
        [{"name": "a", "indices": [1]}, {"name": "b", "indices": [1]}],
    ],
)
def test_invalid_ramps(ramps):
    with pytest.raises(ValidationError):
        Palette(colors=["#00000000", "#000000ff", "#ffffffff"], ramps=ramps)


def test_ramp_canonical_remap_and_aseprite(tmp_path):
    root = tmp_path / "p"
    colors = ramp_project(root)
    p = load_project(root)
    assert loads_project(dumps_project(p)).palette.ramps == p.palette.ramps
    with pytest.raises(CyberSpriteError):
        ops.execute("set_palette", root, {"colors": colors[:2]}, preview="none")
    ops.execute("remap_palette", root, {"order": [0, 4, 3, 2, 1]}, preview="none")
    p = load_project(root)
    assert p.palette.ramps[0].indices == [4, 3, 2, 1]
    path = tmp_path / "roundtrip.aseprite"
    path.write_bytes(encode_aseprite(p))
    restored, _ = read_aseprite(path)
    assert restored.palette.ramps == p.palette.ramps
    exporter = GBExporter()
    assert exporter.options_model is NativeOptions


@pytest.mark.parametrize(
    "name,size,rows,bits",
    [
        ("cgb", (160, 144), 8, 5),
        ("sfc", (256, 224), 8, 5),
        ("md", (320, 224), 4, 3),
        ("gba", (240, 160), 16, 5),
    ],
)
def test_verified_system_constants(name, size, rows, bits):
    p = resolve(name)
    assert (p.system.screen.w, p.system.screen.h) == size
    assert p.system.palette.rows == rows and p.system.color.bits.r == bits
    assert p.system.tile.w == p.system.tile.h == 8


def test_nes_requires_user_palette():
    with pytest.raises(CyberSpriteError, match="no hardware RGB table"):
        resolve("nes")
    p = resolve("nes", overrides={"/system/color/master_colors": [[0, 0, 0], [255, 255, 255]]})
    assert p.system.palette.row_size == 4 and p.system.tile.unique_max == 512
