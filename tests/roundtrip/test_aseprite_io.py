"""Both normative round-trip directions, using exclusively authored fixtures."""

import struct
from copy import deepcopy

import numpy as np
import pytest

from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.models import ImageCel
from cybersprite.core.render import render
from cybersprite.formats.aseprite_io import (
    ap,
    decode_aseprite,
    encode_aseprite,
    equivalent,
    from_native,
    to_native,
)
from tools.m5_cases import animated_project, tile_project


@pytest.mark.parametrize("factory", [animated_project, tile_project])
def test_project_native_project(factory):
    p = factory()
    q, dropped = decode_aseprite(encode_aseprite(p))
    assert not dropped
    assert equivalent(p, q)
    for frame in range(len(p.frames)):
        np.testing.assert_array_equal(render(p, frame), render(q, frame))
    assert encode_aseprite(q) == encode_aseprite(p)


@pytest.mark.parametrize("factory", [animated_project, tile_project])
def test_native_project_native(factory):
    native = to_native(factory())
    first = native.to_bytes()
    p, _ = decode_aseprite(first)
    q, _ = decode_aseprite(encode_aseprite(p))
    assert equivalent(p, q)
    for frame in range(len(p.frames)):
        np.testing.assert_array_equal(render(p, frame), render(q, frame))


@pytest.mark.parametrize(
    "mode,raw",
    [
        (ap.ColorMode.RGBA, bytes.fromhex("123456ff00000000123456ff")),
        (ap.ColorMode.GRAYSCALE, bytes.fromhex("12ff000012ff")),
    ],
)
def test_rgba_and_grayscale_lossless_import(mode, raw):
    native = ap.Sprite(3, 1, mode)
    native.frames[0].set_cel(0, ap.Pixels(3, 1, raw, mode))
    p, dropped = decode_aseprite(native.to_bytes(), name="Native")
    assert not dropped
    assert len(p.palette.colors) == 2
    expected = (
        [[[0x12, 0x34, 0x56, 255], [0, 0, 0, 0], [0x12, 0x34, 0x56, 255]]]
        if mode == ap.ColorMode.RGBA
        else [[[0x12] * 3 + [255], [0, 0, 0, 0], [0x12] * 3 + [255]]]
    )
    np.testing.assert_array_equal(render(p), np.array(expected, dtype=np.uint8))


def test_quantize_required_and_explicit_quantize():
    native = ap.Sprite(257, 1)
    raw = b"".join(bytes([i % 256, i // 256, 12, 255]) for i in range(257))
    native.frames[0].set_cel(0, ap.Pixels(257, 1, raw, ap.ColorMode.RGBA))
    with pytest.raises(CyberSpriteError, match="palette budget") as caught:
        decode_aseprite(native.to_bytes())
    assert caught.value.code == "E_NEEDS_QUANTIZE"
    p, _ = decode_aseprite(native.to_bytes(), quantize=dict(mode="extract", max_colors=4))
    assert len(p.palette.colors) <= 5


def test_changed_frame_palettes_are_merged_and_links_materialized():
    native = to_native(animated_project())
    native.frames[1].palette = ap.Palette(
        [ap.Color(0, 0, 0, 0), ap.Color(9, 8, 7), ap.Color(6, 5, 4), ap.Color(3, 2, 1)]
    )
    p, dropped = decode_aseprite(native.to_bytes())
    assert any(d["element"] == "frame_palettes" for d in dropped)
    assert len(p.palette.colors) == 7
    assert isinstance(p.layers[0].children[0].cels[-1], ImageCel)
    assert tuple(render(p, 2)[1, 1]) == (9, 8, 7, 255)


def test_known_differences_and_dropped_report():
    native = to_native(animated_project())
    native.layers[0].opacity = 128  # SPEC 5.9.3: CyberSprite propagates group opacity.
    native.layers[2].reference = True
    native.layers[1].uuid = __import__("uuid").UUID(int=3)
    native.frames[0].cel(1).extra = ap.CelExtra(0, 0, 65536, 65536)
    native.color_profile = ap.ColorProfile(ap.ColorProfileType.ICC, icc=b"authored profile fixture")
    native.pixel_width = 3
    native.unknown_chunks = [ap.UnknownChunk(0, 0x7777, b"original fixture")]
    p, dropped = decode_aseprite(native.to_bytes())
    kinds = {d["element"] for d in dropped}
    assert {
        "reference_layer",
        "layer_uuid",
        "cel_extra",
        "embedded_icc",
        "pixel_ratio",
        "unknown_chunk",
    } <= kinds
    assert p.canvas.pixel_ratio.w == 1
    assert p.canvas.color_profile == "srgb"
    assert render(p)[1, 1, 3] == 128
    native_pixels = np.frombuffer(native.flatten(0), dtype=np.uint8).reshape(6, 8, 4)
    assert native_pixels[1, 1, 3] == 255  # Known indexed/group opacity difference.
    assert to_native(p).layers[1].uuid is None


def test_old_empty_tile_convention_is_remapped():
    native = to_native(tile_project())
    ts = native.tilesets[0]
    ts.flags &= ~4
    ts.tile_count = 1
    ts.pixels = ap.Pixels(2, 2, bytes.fromhex("01020300"), ap.ColorMode.INDEXED)
    ts.tile_user_data = [ts.tile_user_data[-1]]
    native.frames[0].cel(0).tilemap = ap.Tilemap(
        2, 1, 32, 0x1FFFFFFF, 0x80000000, 0x40000000, 0x20000000, bytes.fromhex("00000000ffffff1f")
    )
    p, _ = decode_aseprite(native.to_bytes())
    assert len(p.tilesets[0].tiles) == 2
    assert p.layers[0].cels[0].tiles == ["1"]  # Normalization removes the trailing empty tile.


def test_external_only_tileset_is_rejected():
    native = to_native(tile_project())
    native.tilesets[0].pixels = None
    native.tilesets[0].flags = 1
    native.tilesets[0].external_file_id = 1
    native.tilesets[0].external_tileset_id = 0
    with pytest.raises(CyberSpriteError) as caught:
        from_native(native)
    assert caught.value.code == "E_UNSUPPORTED"


def test_link_with_independent_position_becomes_data_cel():
    native = to_native(animated_project())
    native.frames[2].cel(1).x = 4
    p, _ = decode_aseprite(native.to_bytes())
    assert isinstance(p.layers[0].children[0].cels[-1], ImageCel)
    assert p.layers[0].children[0].cels[-1].x == 4


def test_roundtrip_ignores_only_normative_fields():
    p = animated_project()
    q = deepcopy(p)
    q.revision = 10
    q.extensions["test.authored"] = {}
    assert equivalent(p, q)
    q.name = "changed"
    assert not equivalent(p, q)


def test_empty_native_cel_is_lost_as_documented():
    native = ap.Sprite(1, 1, ap.ColorMode.INDEXED)
    native.palette = ap.Palette([ap.Color(0, 0, 0, 0)])
    native.frames[0].set_cel(0, ap.Pixels(1, 1, b"\0", ap.ColorMode.INDEXED))
    p, _ = decode_aseprite(native.to_bytes())
    assert p.layers[0].cels == []


@pytest.mark.parametrize("factory", [animated_project, tile_project])
def test_native_independent_normal_renderer_matches(factory):
    p = factory()
    native = ap.Sprite.from_bytes(encode_aseprite(p))
    for frame in range(len(p.frames)):
        actual = np.frombuffer(native.flatten(frame), dtype=np.uint8).reshape(
            p.canvas.height, p.canvas.width, 4
        )
        np.testing.assert_array_equal(actual, render(p, frame))


def test_native_tag_and_slice_colors_and_nonexact_float_metadata():
    p = animated_project()
    p.user_data.properties["float"]["value"] = 1.1
    p.user_data.properties["$ext"] = {}
    native = to_native(p)
    assert tuple(native.tags[0].user_data.color) == (17, 34, 51, 255)
    assert tuple(native.slices[0].user_data.color) == (102, 119, 136, 153)
    q, _ = decode_aseprite(native.to_bytes())
    assert equivalent(p, q)
    assert q.tags[0].user_data.color == "#12345678"


def test_native_layer_flags_and_all_blend_values():
    from cybersprite.core.models import ImageLayer
    from cybersprite.formats.aseprite_io import BLENDS

    p = animated_project()
    p.layers = [
        ImageLayer(
            id=f"L{i + 1}",
            name=f"Mode {i}",
            blend_mode=mode,
            visible=False,
            locked=True,
            continuous=True,
            background=(i == 0),
        )
        for i, mode in enumerate(BLENDS)
    ]
    p.id_counters.layer = len(p.layers)
    p.layers[0].cels = [
        ImageCel(frame=f, x=0, y=0, w=8, h=6, pixels=["00" * 8] * 6) for f in range(3)
    ]
    q, _ = decode_aseprite(encode_aseprite(p))
    assert equivalent(p, q)


@pytest.mark.parametrize("kind", [4, 17])
def test_old_palette_chunks_are_read_without_a_new_palette(kind):
    # Build an authored legacy palette payload, replacing only the native palette chunk.
    native = ap.Sprite(1, 1, ap.ColorMode.INDEXED)
    native.palette = ap.Palette([ap.Color(0, 0, 0), ap.Color(20, 40, 60)])
    native.frames[0].set_cel(0, ap.Pixels(1, 1, b"\x01", ap.ColorMode.INDEXED))
    data = native.to_bytes()
    chunks, offset = [], 144
    while offset < len(data):
        size, type_id = struct.unpack_from("<IH", data, offset)
        if type_id != 0x2019:
            chunks.append(data[offset : offset + size])
        offset += size
    rgb = bytes([0, 0, 0, 20, 40, 60]) if kind == 4 else bytes([0, 0, 0, 5, 10, 15])
    payload = struct.pack("<HBB", 1, 0, 2) + rgb
    chunks.insert(0, struct.pack("<IH", len(payload) + 6, kind) + payload)
    frame = bytearray(data[128:144])
    struct.pack_into("<I", frame, 0, 16 + sum(map(len, chunks)))
    struct.pack_into("<H", frame, 6, len(chunks))
    struct.pack_into("<I", frame, 12, len(chunks))
    header = bytearray(data[:128])
    struct.pack_into("<I", header, 0, 128 + 16 + sum(map(len, chunks)))
    p, _ = decode_aseprite(bytes(header + frame) + b"".join(chunks))
    assert p.palette.colors[1] == "#14283cff"


def test_large_roundtrip_metadata_uses_native_string_vector():
    p = animated_project()
    p.user_data.properties["wide"] = {f"field-{i:04d}": i for i in range(4000)}
    native = to_native(p)
    marker = next(
        prop
        for m in native.user_data.properties
        for prop in m.properties
        if prop.name == "$cybersprite"
    )
    assert marker.kind == ap.PropertyType.VECTOR
    q, _ = decode_aseprite(native.to_bytes())
    assert equivalent(p, q)


def test_quantizing_frame_palettes_preserves_transparent_pixels():
    native = ap.Sprite(2, 1, ap.ColorMode.INDEXED)
    native.palette = ap.Palette([ap.Color(i, 0, 0) for i in range(256)])
    native.frames[0].set_cel(0, ap.Pixels(2, 1, b"\0\x01", ap.ColorMode.INDEXED))
    frame = ap.Frame(palette=ap.Palette([ap.Color(i, 1, 0) for i in range(256)]))
    frame.set_cel(0, ap.Pixels(2, 1, b"\0\x01", ap.ColorMode.INDEXED))
    native.frames.append(frame)
    p, _ = decode_aseprite(native.to_bytes(), quantize=dict(mode="extract", max_colors=4))
    assert not render(p)[0, 0, 3]
    assert not render(p, 1)[0, 0, 3]


def test_native_edits_take_precedence_over_roundtrip_hints():
    native = to_native(animated_project())
    native.tags[0].user_data.color = ap.Color(4, 5, 6)
    native.slices[0].user_data.color = ap.Color(9, 8, 7)
    native.slices[0].keys[1].pivot = (2, 3)
    native.layers[1].lock_movement = False
    prop = next(p for m in native.user_data.properties for p in m.properties if p.name == "float")
    prop.value = 7.5
    prop = next(p for m in native.user_data.properties for p in m.properties if p.name == "null")
    prop.value = "edited"
    p, _ = decode_aseprite(native.to_bytes())
    assert p.tags[0].color == "#040506"
    assert p.slices[0].color == "#090807ff"
    assert p.slices[0].keys[1].pivot.model_dump() == dict(x=2, y=3)
    assert p.user_data.properties["float"]["value"] == 7.5
    assert p.user_data.properties["null"] == "edited"
    assert p.layers[0].children[0].user_data.properties["$ase"]["lock_movement"] is False
