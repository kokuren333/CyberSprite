"""Format contracts, fixed layout vectors, corruption checks, and export gates."""

import json
import random
import struct

import numpy as np
import pytest

from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.models import ImageCel, ImageLayer, Tag
from cybersprite.core.render import indexed_result, render
from cybersprite.formats.animation import (
    decode_apng,
    decode_gif,
    encode_apng,
    encode_gif,
    gif_durations,
)
from cybersprite.formats.common import (
    animation_sequence,
    export_policy,
    format_name,
    frame_sequence,
    write_verified,
)
from cybersprite.formats.export import (
    export_animation,
    export_aseprite,
    export_image,
    export_palette,
    export_sheet,
    export_tileset,
)
from cybersprite.formats.export_args import (
    AnimationArgs,
    AsepriteArgs,
    ImageArgs,
    PaletteArgs,
    SheetArgs,
    TilesetArgs,
)
from cybersprite.formats.input_adapter import load_external
from cybersprite.formats.palette_files import decode_palette, encode_palette, read_palette
from cybersprite.formats.png import _chunk, decode_png, encode_png
from cybersprite.formats.sheet import ceil_sqrt, layout_rectangles
from cybersprite.ops import execute, registry
from tools.m5_cases import animated_project, tile_project


@pytest.fixture
def policy(tmp_path):
    with export_policy(tmp_path):
        yield tmp_path


@pytest.mark.parametrize(
    "layout,positions,size",
    [
        ("horizontal", [(0, 0), (4, 0), (7, 0)], (11, 4)),
        ("vertical", [(0, 0), (0, 3), (0, 8)], (4, 9)),
        ("rows", [(0, 0), (4, 0), (0, 5)], (6, 6)),
        ("columns", [(0, 0), (0, 3), (4, 0)], (8, 7)),
        ("packed", [(0, 5), (0, 0), (0, 8)], (5, 9)),
    ],
)
def test_layout_fixed_vectors(layout, positions, size):
    a = SheetArgs(out="unused", layout=layout, spacing=1)
    pos, w, h = layout_rectangles([(3, 2), (2, 4), (4, 1)], a)
    assert pos == positions
    assert (w, h) == size


def test_layout_width_count_padding_and_limit():
    a = SheetArgs(out="x", width=12, columns=9, border=1, spacing=2)
    assert layout_rectangles([(4, 3)] * 3, a) == ([(1, 1), (7, 1), (1, 6)], 12, 10)
    a.power_of_two = True
    assert layout_rectangles([(4, 3)] * 3, a)[1:] == (16, 16)
    a = SheetArgs(out="x", layout="vertical", border=1, power_of_two=True)
    with pytest.raises(CyberSpriteError) as caught:
        layout_rectangles([(16384, 1)], a)
    assert caught.value.code == "E_LIMIT_EXCEEDED"
    for n, expected in [(0, 0), (1, 1), (2, 2), (4, 2), (5, 3), (10**24 + 1, 10**12 + 1)]:
        assert ceil_sqrt(n) == expected


@pytest.mark.parametrize(
    "direction,repeat,expected",
    [
        ("forward", 0, [0, 1, 2]),
        ("forward", 2, [0, 1, 2, 0, 1, 2]),
        ("reverse", 1, [2, 1, 0]),
        ("pingpong", 0, [0, 1, 2, 1]),
        ("pingpong", 3, [0, 1, 2, 1, 0, 1, 2]),
        ("pingpong_reverse", 0, [2, 1, 0, 1]),
        ("pingpong_reverse", 1, [2, 1, 0]),
    ],
)
def test_animation_sequence_vectors(direction, repeat, expected):
    p = animated_project()
    p.tags[0].direction, p.tags[0].repeat = direction, repeat
    assert animation_sequence(p, tag="Motion") == expected
    assert animation_sequence(p, [2, 0, 2], loop=1) == [2, 0, 2]
    assert animation_sequence(p, [2, 0, 2]) == [2, 0]
    p.tags[0].to = 0
    assert animation_sequence(p, tag="Motion") == [0]
    assert frame_sequence(p, "Motion") == [0]


def test_filename_placeholders_and_rejections(policy):
    p = animated_project()
    r = export_image(
        p, ImageArgs(out="{name}-{frame:03}-{frame1:02}-{tag}-{tagframe}.png", frames=[1])
    )
    assert r["files"][0]["path"] == "M5 fixture-001-02-Motion-1.png"
    for pattern in (
        "{__class__}",
        "{frame.real}",
        "{frame!r}",
        "{frame:{name}}",
        "{frame:99999999}",
    ):
        with pytest.raises(CyberSpriteError) as caught:
            format_name(pattern, frame=1)
        assert caught.value.code == "E_INVALID_ARGS"
    with pytest.raises(CyberSpriteError):
        export_image(p, ImageArgs(out="collision.png"))
    assert not (policy / "collision.png").exists()


@pytest.mark.parametrize("mode", ["indexed", "rgba"])
@pytest.mark.parametrize("compression", ["stored", "zlib"])
def test_image_modes_scaling_crop_trim_ratio_background(policy, mode, compression):
    p = animated_project()
    p.canvas.pixel_ratio.w = 2
    result = export_image(
        p,
        ImageArgs(
            out="x.png",
            frames=[0],
            color_mode=mode,
            scale=2,
            crop=dict(x=0, y=0, w=4, h=4),
            trim=True,
            apply_pixel_ratio=True,
            compression=compression,
        ),
    )
    image = decode_png((policy / "x.png").read_bytes())
    assert image.pixels.shape[:2] == (4, 8)
    assert result["verified"] and result["validation_ok"]
    assert result["files"][0]["pixel_sha256"]
    result = export_image(
        p, ImageArgs(out="slice.png", frames=[0], slice="Region", color_mode=mode, background=1)
    )
    assert (result["files"][0]["width"], result["files"][0]["height"]) == (6, 5)


@pytest.mark.parametrize("data_format", ["cybersprite", "json-hash", "json-array"])
def test_sheet_trim_merge_and_json_contracts(policy, data_format):
    p = animated_project()
    r = export_sheet(
        p,
        SheetArgs(
            out="sheet.png",
            data_out="sheet.json",
            data_format=data_format,
            frames=[2, 0],
            trim=True,
            merge_duplicates=True,
            border=1,
            spacing=2,
            inner=1,
        ),
    )
    data = json.loads((policy / "sheet.json").read_bytes())
    assert r["items"] == 2
    assert r["sheet"] == dict(width=6, height=6)
    assert b"fingerprint" not in (policy / "sheet.json").read_bytes()
    assert b"created_at" not in (policy / "sheet.json").read_bytes()
    if data_format == "cybersprite":
        assert [i["frame"] for i in data["items"]] == [0, 2]
        assert data["items"][0]["rect"] == data["items"][1]["rect"]
        assert data["tags"][0]["to"] == 2
    else:
        frames = list(data["frames"].values()) if data_format == "json-hash" else data["frames"]
        assert frames[0]["frame"] == frames[1]["frame"]
        meta = data["meta"]
        assert meta["frameTags"][0] == dict(
            name="Motion", **{"from": 0}, to=1, direction="pingpong", repeat="3", color="#112233ff"
        )
        assert meta["layers"][0] == dict(name="Group")
        assert meta["layers"][1]["group"] == "Group"
        keys = meta["slices"][0]["keys"]
        assert keys[0]["bounds"] == dict(x=0, y=0, w=6, h=5)
        assert "center" not in keys[1] and "pivot" not in keys[1]


def test_sheet_split_order_empty_and_duplicate_names(policy):
    p = animated_project()
    p.layers.append(
        ImageLayer(id="L4", name="Top", cels=[ImageCel(frame=1, x=0, y=0, w=1, h=1, pixels=["01"])])
    )
    p.id_counters.layer = 4
    p.tags.append(Tag(id="T2", name="One", **{"from": 1}, to=1))
    p.id_counters.tag = 2
    a = SheetArgs(
        out="split.png",
        data_out="split.json",
        split_layers=True,
        split_tags=True,
        split_slices=True,
        trim=True,
        ignore_empty=True,
        data_format="cybersprite",
        item_name="{layer}-{tag}-{slice}-{frame}",
    )
    export_sheet(p, a)
    data = json.loads((policy / "split.json").read_bytes())
    assert [i["name"] for i in data["items"]] == [
        "Cells-Motion-Region-0",
        "Cells-Motion-Region-1",
        "Cells-Motion-Region-2",
        "Cells-One-Region-1",
        "Top-Motion-Region-1",
        "Top-One-Region-1",
    ]
    a.include_hidden = True
    a.ignore_empty = False
    a.data_format = "json-hash"
    a.item_name = "same"
    with pytest.raises(CyberSpriteError, match="unique"):
        export_sheet(p, a)
    a = SheetArgs(out="empty.png", layers=["Empty"], include_hidden=True)
    assert export_sheet(p, a)["items"] == 3
    a.ignore_empty = True
    assert export_sheet(p, a)["items"] == 0


@pytest.mark.parametrize("count", [2, 3, 4, 16, 17, 255, 256])
def test_lzw_against_independent_decoder_at_width_transitions(count):
    rng = random.Random(401 + count)
    colors = ["#" + bytes([i, (i * 13) % 256, (i * 71) % 256, 255]).hex() for i in range(count)]
    image = np.array(
        [[rng.randrange(count) for _ in range(303)] for _ in range(91)], dtype=np.uint8
    )
    raw = encode_gif(
        [image, image[::-1].copy()], colors, 0, [15, 100], loop=2, transparent=[False, False]
    )
    actual, times, loop = decode_gif(raw)
    expected = np.array([tuple(bytes.fromhex(c[1:])) for c in colors], dtype=np.uint8)[image]
    np.testing.assert_array_equal(actual[0], expected)
    np.testing.assert_array_equal(actual[1], expected[::-1])
    assert times == [20, 100] and loop == 2
    size = 1 << max(1, (count - 1).bit_length())
    assert raw[13 + 3 * count : 13 + 3 * size] == b"\0" * (3 * (size - count))
    assert raw == encode_gif(
        [image, image[::-1].copy()], colors, 0, [15, 100], loop=2, transparent=[False, False]
    )


@pytest.mark.parametrize("loop,stored", [(0, 0), (1, None), (2, 1), (65535, 65534)])
def test_gif_loop_extension_semantics(loop, stored):
    image = np.ones((2, 2), dtype=np.uint8)
    data = encode_gif([image], ["#00000000", "#ffffffff"], 0, [1], loop=loop)
    pos = data.find(b"NETSCAPE2.0")
    assert (pos < 0) == (stored is None)
    if stored is not None:
        assert struct.unpack_from("<H", data, pos + 13)[0] == stored
    assert decode_gif(data)[2] == loop
    assert gif_durations([1, 10, 14, 15, 24, 25, 65535]) == [20, 20, 20, 20, 20, 30, 65540]


@pytest.mark.parametrize("mode", ["indexed", "rgba"])
@pytest.mark.parametrize("compression", ["stored", "zlib"])
def test_apng_roundtrip_and_control_corruption(mode, compression):
    p = animated_project()
    frames = [indexed_result(p, f).pixels if mode == "indexed" else render(p, f) for f in range(3)]
    palette = indexed_result(p, 0).palette if mode == "indexed" else None
    data = encode_apng(frames, [35, 60, 65535], palette, compression=compression, loop=3)
    decoded, times, loop = decode_apng(data)
    assert times == [35, 60, 65535] and loop == 3
    for actual, expected in zip(decoded, frames, strict=True):
        np.testing.assert_array_equal(actual.pixels, expected)
    with pytest.raises(ValueError):
        decode_apng(data[:-1])
    pos = data.index(b"fcTL") - 4
    bad_control = _chunk(b"fcTL", struct.pack(">IIIIIHHBB", 99, 8, 6, 0, 0, 35, 1000, 0, 0))
    with pytest.raises(ValueError, match="control"):
        decode_apng(data[:pos] + bad_control + data[pos + len(bad_control) :])


def test_animation_auto_mode_transparency_and_nearest(policy):
    p = animated_project()
    r = export_animation(p, AnimationArgs(out="x.gif", frames=[0, 1], loop=1))
    assert any(w.get("code") == "W_GIF_DURATION_ROUNDED" for w in r["warnings"])
    decoded, times, plays = decode_gif((policy / "x.gif").read_bytes())
    np.testing.assert_array_equal(decoded[0], render(p))
    np.testing.assert_array_equal(decoded[1], render(p, 1))
    p.layers[0].children[0].opacity = 128
    assert export_animation(p, AnimationArgs(out="x.apng", frames=[0]))["verified"]
    assert decode_apng((policy / "x.apng").read_bytes())[0][0].palette is None
    with pytest.raises(CyberSpriteError) as caught:
        export_animation(p, AnimationArgs(out="x.gif"))
    assert caught.value.code == "E_NOT_PALETTE_CLOSED"
    assert export_animation(p, AnimationArgs(out="x.gif", flatten="nearest"))["verified"]


@pytest.mark.parametrize("format", ["gpl", "pal", "hex", "png"])
def test_palette_codecs_and_export(policy, format):
    p = animated_project()
    assert export_palette(p, PaletteArgs(out="palette." + format))["verified"]
    expected = (
        p.palette.colors if format in ("hex", "png") else [c[:7] + "ff" for c in p.palette.colors]
    )
    assert read_palette(str(policy / ("palette." + format))) == expected
    if format == "gpl":
        assert decode_palette((policy / "palette.gpl").read_bytes(), format)[1] == p.palette.names
    p.palette.colors.append(p.palette.colors[0])
    assert export_palette(p, PaletteArgs(out="duplicates." + format))["verified"]


def test_palette_png_first_appearance_and_limit(policy):
    image = np.array([[[1, 2, 3, 4], [4, 3, 2, 1], [1, 2, 3, 4]]], dtype=np.uint8)
    assert decode_palette(encode_png(image), "png")[0] == ["#01020304", "#04030201"]
    with pytest.raises(CyberSpriteError) as caught:
        encode_palette(["#00000000"] * 257, {}, "hex")
    assert caught.value.code == "E_LIMIT_EXCEEDED"


def test_validation_gate_overwrite_and_delete_on_self_verify_failure(policy):
    p = animated_project()
    p.validation.palette_max = 1
    with pytest.raises(CyberSpriteError) as caught:
        export_image(p, ImageArgs(out="bad{frame}.png"))
    assert caught.value.code == "E_VALIDATION_FAILED"
    assert not list(policy.glob("*.png"))
    r = export_image(p, ImageArgs(out="bad{frame}.png", allow_invalid=True))
    assert not r["validation_ok"] and r["verified"]
    assert any(w.get("code") == "W_EXPORT_INVALID" for w in r["warnings"])
    with pytest.raises(CyberSpriteError) as caught:
        export_image(p, ImageArgs(out="bad{frame}.png", allow_invalid=True, overwrite=False))
    assert caught.value.code == "E_EXISTS"
    with pytest.raises(CyberSpriteError) as caught:
        write_verified(policy / "corrupt.png", b"corrupt", lambda raw: decode_png(raw))
    assert caught.value.code == "E_INTERNAL" and not (policy / "corrupt.png").exists()
    with pytest.raises(CyberSpriteError) as caught:
        export_image(p, ImageArgs(out="../outside.png", frames=[0], allow_invalid=True))
    assert caught.value.code == "E_PATH_NOT_ALLOWED"


def test_export_ops_ingest_manifest_and_input_adapter(policy, monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_NOW", "2026-11-12T00:00:00Z")
    p = animated_project()
    export_aseprite(p, AsepriteArgs(out="source.aseprite"))
    target = policy / "import.csprite"
    envelope = execute("import_aseprite", target, {"file": "source.aseprite"})
    assert envelope["result"]["source"] == "SRC1"
    manifest = json.loads((target / "source/manifest.json").read_bytes())
    assert manifest["sources"][0]["license"] == "unknown"
    assert manifest["sources"][0]["imported_at"] == "2026-11-12T00:00:00Z"
    source = target / manifest["sources"][0]["files"][0]["path"]
    assert source.read_bytes() == (policy / "source.aseprite").read_bytes()
    before = (target / "project.json").read_bytes()
    assert execute("export_image", target, {"out": "op{frame}.png"})["result"]["verified"]
    assert (target / "project.json").read_bytes() == before
    assert (
        execute("import_aseprite", target, {"file": "source.aseprite", "if_exists": "open"})[
            "result"
        ]["source"]
        is None
    )
    q = load_external(policy / "source.aseprite", {})
    assert q.name == p.name
    assert load_external(policy / "op0.png", {}).canvas.width == 8
    for name in (
        "export_image",
        "export_sheet",
        "export_animation",
        "export_palette",
        "export_aseprite",
        "export_tileset",
    ):
        assert registry().get(name).idempotency == "E"
        assert registry().get(name).kind == "export"
    assert registry().get("import_aseprite").idempotency == "C"


def test_tileset_export_data_and_rendered_pixels(policy):
    p = tile_project()
    r = export_tileset(
        p, TilesetArgs(out="tiles.png", data_out="tiles.json", tileset="TS1", include_empty=True)
    )
    assert r["verified"]
    image = decode_png((policy / "tiles.png").read_bytes())
    data = json.loads((policy / "tiles.json").read_bytes())
    assert [i["index"] for i in data["tiles"]] == [0, 1]
    assert image.pixels.tolist() == [[0, 0, 1, 2], [0, 0, 3, 0]]


def test_policy_allows_resolved_external_directory_and_rejects_symlink(policy, tmp_path):
    from cybersprite.formats.common import output_path

    external = tmp_path.parent / (tmp_path.name + "-allowed")
    external.mkdir()
    with export_policy(policy, [external]):
        assert output_path(str(external / "image.png")) == external / "image.png"
    with pytest.raises(CyberSpriteError) as caught:
        output_path(str(external / "image.png"))
    assert caught.value.code == "E_PATH_NOT_ALLOWED"
    try:
        (policy / "link").symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires Windows Developer Mode or administrator rights.")
    with pytest.raises(CyberSpriteError) as caught:
        output_path("link/image.png")
    assert caught.value.code == "E_PATH_NOT_ALLOWED"


def test_animation_identity_includes_all_frames(policy):
    p = animated_project()
    a = AnimationArgs(out="first.apng", frames=[0, 1], compression="stored")
    before = export_animation(p, a)["files"][0]["pixel_sha256"]
    p.layers[0].children[0].cels[1].pixels = ["0102", "0201"]
    a.out = "second.apng"
    after = export_animation(p, a)["files"][0]["pixel_sha256"]
    assert before != after


def test_gif_background_transparent_index_is_opaque(policy):
    p = animated_project()
    p.palette.colors[0] = "#44556600"
    p.layers = [ImageLayer(id="L1", name="Background", background=True)]
    # Full-size background ensures the transparent index is rendered as opaque here.
    p.layers[0].cels = [
        ImageCel(frame=f, x=0, y=0, w=8, h=6, pixels=["00" * 8] * 6) for f in range(3)
    ]
    assert export_animation(p, AnimationArgs(out="background.gif", frames=[0, 1]))["verified"]
