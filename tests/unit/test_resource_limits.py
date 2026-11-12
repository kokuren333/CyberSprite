"""No large allocations: spies prove limits precede codec/geometry work."""

import importlib
import random
import struct
from unittest.mock import Mock

import numpy as np
import pytest

from cybersprite import ops
from cybersprite.core import limits, raster
from cybersprite.core.canonical import load_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.projects import new_project
from cybersprite.core.registry import OpContext
from cybersprite.formats import aseprite_io, palette_files, sheet
from cybersprite.formats.export_args import SheetArgs
from cybersprite.formats.png import SIGNATURE, _chunk, decode_png, encode_png
from cybersprite.ops.drawing import drawing
from cybersprite.ops.ingest import decode_files
from cybersprite.pipeline._common import PipelineError
from cybersprite.pipeline.decode import decode_raster, split_sheet

render_module = importlib.import_module("cybersprite.core.render")
preview_module = importlib.import_module("cybersprite.core.previews")


def exceeded(call, name, requested=None, limit=None, error_type=CyberSpriteError):
    with pytest.raises(error_type) as caught:
        call()
    error = caught.value
    assert error.code == "E_LIMIT_EXCEEDED"
    assert error.details["limit_name"] == name
    assert error.details["requested"] > error.details["limit"]
    if requested is not None:
        assert error.details["requested"] == requested
    if limit is not None:
        assert error.details["limit"] == limit
    assert error.hint
    return error


class LazyImage:
    format = "GIF"
    mode = "RGBA"
    info = {}

    def __init__(self, width, height, frames):
        self.size = width, height
        self.n_frames = frames
        self.convert = Mock(side_effect=AssertionError("must not decode"))
        self.seek = Mock(side_effect=AssertionError("must not seek"))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.mark.parametrize(
    "w,h,count,name",
    [
        (8193, 1, 1, "source_width"),
        (1, 8193, 1, "source_height"),
        (1, 1, 4097, "source_frames"),
        (8192, 8192, 2, "decoded_bytes"),
    ],
)
def test_raster_header_before_seek_convert(monkeypatch, w, h, count, name):
    image = LazyImage(w, h, count)
    monkeypatch.setattr("cybersprite.pipeline.decode.Image.open", lambda _: image)
    exceeded(lambda: decode_raster("unused.gif"), name, error_type=PipelineError)
    image.convert.assert_not_called()
    image.seek.assert_not_called()


def test_wide_png_real_import_reproduction_before_convert(tmp_path, monkeypatch):
    from PIL import Image

    path = tmp_path / "wide.png"
    path.write_bytes(encode_png(np.full((1, 8193, 4), 255, dtype=np.uint8)))
    project = tmp_path / "project"
    ops.execute("new_project", project, {"width": 2, "height": 2})
    convert = Mock(side_effect=AssertionError("must not decode"))
    monkeypatch.setattr(Image.Image, "convert", convert)
    exceeded(
        lambda: ops.execute(
            "import_image",
            project,
            {
                "files": str(path),
                "preset": "exact",
                "provenance": {"license": "unknown"},
            },
            preview="none",
        ),
        "source_width",
        8193,
        8192,
    )
    convert.assert_not_called()
    assert load_project(project).revision == 0


@pytest.mark.parametrize("budget_name", ["source_frames", "decoded_bytes"])
def test_files_cumulative_budget_stops_before_next_decode(tmp_path, monkeypatch, budget_name):
    import cybersprite.ops.ingest as ingest

    path = tmp_path / "one.png"
    path.write_bytes(encode_png(np.zeros((1, 1, 4), dtype=np.uint8)))
    opened = []
    actual = ingest.decode_raster

    def decode(path, *, budget):
        opened.append(path)
        if len(opened) == 1:
            if budget_name == "source_frames":
                budget.frames = 4095
            else:
                budget.bytes = limits.DECODED_BYTES - 4
        return actual(path, budget=budget)

    monkeypatch.setattr(ingest, "decode_raster", decode)
    exceeded(lambda: decode_files([path] * 3), budget_name)
    assert len(opened) == 2


def test_palette_png_header_before_convert(monkeypatch):
    image = LazyImage(8193, 1, 1)
    monkeypatch.setattr("PIL.Image.open", lambda _: image)
    exceeded(lambda: palette_files.decode_palette(b"unused", "png"), "source_width")
    image.convert.assert_not_called()


def test_pillow_bomb_header_is_a_product_limit(tmp_path, monkeypatch):
    from PIL import Image

    data = (
        SIGNATURE
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", 32768, 32768, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", b"")
        + _chunk(b"IEND", b"")
    )
    path = tmp_path / "bomb.png"
    path.write_bytes(data)
    convert = Mock(side_effect=AssertionError("must not decode"))
    monkeypatch.setattr(Image.Image, "convert", convert)
    exceeded(lambda: decode_raster(path), "source_area", 32768**2, error_type=PipelineError)
    exceeded(lambda: palette_files.decode_palette(data, "png"), "source_area", 32768**2)
    convert.assert_not_called()


@pytest.mark.parametrize(
    "shape,name", [((1, 4097, 4), "source_frames"), ((8192, 8192, 4), "decoded_bytes")]
)
def test_split_budget_before_copy(shape, name):
    image = Mock(shape=shape, nbytes=shape[0] * shape[1] * 4)
    cell = 1 if name == "source_frames" else 8192
    exceeded(
        lambda: split_sheet([image], dict(cell_w=cell, cell_h=cell)), name, error_type=PipelineError
    )


@pytest.mark.parametrize(
    "offset,value,name",
    [(8, 8193, "source_width"), (10, 8193, "source_height"), (6, 4097, "source_frames")],
)
def test_aseprite_header_before_parser(monkeypatch, offset, value, name):
    data = bytearray(aseprite_io.encode_aseprite(new_project(width=2, height=2)))
    struct.pack_into("<H", data, offset, value)
    parse = Mock(side_effect=AssertionError("must not parse/decompress"))
    monkeypatch.setattr(aseprite_io.ap.Sprite, "from_bytes", parse)
    exceeded(lambda: aseprite_io.decode_aseprite(bytes(data)), name)
    parse.assert_not_called()


def test_aseprite_cel_budget_before_parser(monkeypatch):
    from tools.m5_cases import animated_project

    data = aseprite_io.encode_aseprite(animated_project())
    monkeypatch.setattr(limits, "DECODED_BYTES", 1)
    parse = Mock(side_effect=AssertionError("must not parse/decompress"))
    monkeypatch.setattr(aseprite_io.ap.Sprite, "from_bytes", parse)
    exceeded(lambda: aseprite_io.decode_aseprite(data), "decoded_bytes")
    parse.assert_not_called()


@pytest.mark.parametrize(
    "name,args,target",
    [
        ("line", dict(x0=0, y0=0, x1=10**9, y1=0), "line_points"),
        ("rect", dict(x=0, y=0, w=10**9, h=10**9), "rect_points"),
        ("ellipse", dict(x=0, y=0, w=10**9, h=10**9), "ellipse_points"),
        ("polygon", dict(points=[[0, 0], [10**9, 0], [0, 10**9]], filled=True), "polygon_points"),
        ("stroke", dict(points=[[0, 0], [10**9, 0]]), "stroke_path"),
        ("line", dict(x0=0, y0=0, x1=1000, y1=0, brush={"size": 64}), "line_points"),
    ],
)
def test_op_work_before_geometry(tmp_path, monkeypatch, name, args, target):
    p = new_project(width=2, height=2)
    enumerate_points = Mock(side_effect=AssertionError("must not enumerate"))
    monkeypatch.setattr(raster, target, enumerate_points)

    def call():
        parsed = ops.registry().get(name).parse(dict(layer="L1", frame=0, color=1, **args))
        drawing(OpContext(p, tmp_path), parsed, name)

    exceeded(call, "drawing_work_per_op")
    enumerate_points.assert_not_called()


@pytest.mark.parametrize(
    "call",
    [
        lambda: raster.line_points(0, 0, 10**9, 0),
        lambda: raster.rect_points(0, 0, 10**9, 10**9),
        lambda: raster.ellipse_mask(10**9, 10**9),
        lambda: raster.polygon_points([(0, 0), (10**9, 0)]),
        lambda: raster.stroke_path([(0, 0), (10**9, 0)]),
        lambda: raster.stamp([(0, 0)] * 1000, {"size": 64}),
    ],
)
def test_core_geometry_has_independent_budget(call):
    exceeded(call, "drawing_work_per_op")


@pytest.mark.parametrize(
    "name,args,count,target",
    [
        ("line", dict(x0=-50, y0=-50, x1=-20, y1=-40), 31, "line_points"),
        ("rect", dict(x=-50, y=-50, w=10, h=10, filled=True), 100, "rect_points"),
        ("rect", dict(x=50, y=50, w=10, h=10), 36, "rect_points"),
    ],
)
def test_off_canvas_line_rect_return_before_enumeration(
    tmp_path, monkeypatch, name, args, count, target
):
    p = new_project(width=2, height=2)
    parsed = ops.registry().get(name).parse(dict(layer="L1", frame=0, color=1, **args))
    enumerate_points = Mock(side_effect=AssertionError("must not enumerate"))
    monkeypatch.setattr(raster, target, enumerate_points)
    ctx = OpContext(p, tmp_path)
    assert drawing(ctx, parsed, name) == {"pixels_written": 0}
    assert ctx.clipped_pixels == count
    enumerate_points.assert_not_called()


@pytest.mark.parametrize("name", ["polygon", "stroke"])
def test_vertex_limit_before_segment_enumeration(monkeypatch, name):
    enumerate_points = Mock(side_effect=AssertionError("must not enumerate"))
    monkeypatch.setattr(raster, "line_points", enumerate_points)
    call = raster.polygon_points if name == "polygon" else raster.stroke_path
    exceeded(lambda: call([(0, 0)] * 65_537), "drawing_vertices")
    enumerate_points.assert_not_called()


def test_transaction_work_cumulative_and_rollback(tmp_path, monkeypatch):
    project = tmp_path / "p"
    ops.execute("new_project", project, {"width": 2, "height": 2})
    before = (project / "project.json").read_bytes()
    monkeypatch.setattr(limits, "WORK_PER_TRANSACTION", 3)
    point = dict(op="set_pixel", args=dict(layer="L1", frame=0, x=0, y=0, color=1))
    error = exceeded(
        lambda: ops.execute("apply_ops", project, {"ops": [point] * 4}, preview="none"),
        "drawing_work_per_transaction",
        4,
        3,
    )
    assert error.op_index == 3
    assert (project / "project.json").read_bytes() == before


def test_far_existing_cel_union_before_allocation(tmp_path, monkeypatch):
    from cybersprite.core.models import ImageCel
    from cybersprite.ops import common

    p = new_project(width=2, height=2)
    layer = p.layers[0]
    layer.cels = [ImageCel(frame=0, x=32767, y=32767, w=1, h=1, pixels=["01"])]
    allocate = Mock(side_effect=AssertionError("must not allocate"))
    monkeypatch.setattr(common.np, "full", allocate)
    exceeded(
        lambda: common.write_points(OpContext(p, tmp_path), layer, 0, [(0, 0, 1)]), "output_bytes"
    )
    allocate.assert_not_called()


@pytest.mark.parametrize("indexed", [False, True])
def test_render_budget_before_canvas_and_repeat(monkeypatch, indexed):
    p = new_project(width=4096, height=4096)
    allocate = Mock(side_effect=AssertionError("must not allocate"))
    monkeypatch.setattr(render_module.np, "zeros", allocate)
    monkeypatch.setattr(render_module.np, "repeat", allocate)
    render = render_module.render_indexed if indexed else render_module.render
    exceeded(lambda: render(p, options={"scale": 64}), "output_bytes", 274_877_906_944, 268_435_456)
    allocate.assert_not_called()


def test_render_crop_and_ratio_counted_before_repeat(monkeypatch):
    p = new_project(width=4096, height=4096)
    p.canvas.pixel_ratio.w = 2
    # Cropping the same project makes a large integer scale safe.
    assert (
        render_module._options(
            p,
            0,
            {
                "crop": dict(x=0, y=0, w=1, h=1),
                "scale": 64,
            },
        ).scale
        == 64
    )
    exceeded(
        lambda: render_module._options(
            p,
            0,
            {
                "scale": 2,
                "apply_pixel_ratio": True,
            },
        ),
        "output_bytes",
        536_870_912,
    )


def test_preview_budget_includes_rulers_before_render(monkeypatch):
    p = new_project(width=4096, height=4096)
    render = Mock(side_effect=AssertionError("must not render"))
    monkeypatch.setattr(preview_module, "render", render)
    exceeded(lambda: preview_module.preview_array(p, 0, scale=2, rulers=True), "output_bytes")
    render.assert_not_called()


def test_sheet_layout_budget_before_allocation(monkeypatch):
    args = SheetArgs.model_validate(dict(out="unused.png", width=16384, height=16384))
    allocate = Mock(side_effect=AssertionError("must not allocate"))
    monkeypatch.setattr(sheet.np, "full", allocate)
    exceeded(
        lambda: sheet.build_sheet(new_project(width=2, height=2), args, []),
        "output_bytes",
        1_073_741_824,
    )
    allocate.assert_not_called()


def test_png_reader_budget_before_inflate(monkeypatch):
    import zlib

    data = (
        SIGNATURE
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", 16384, 16384, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", b"")
        + _chunk(b"IEND", b"")
    )
    inflate = Mock(side_effect=AssertionError("must not inflate"))
    monkeypatch.setattr(zlib, "decompressobj", inflate)
    exceeded(lambda: decode_png(data), "output_bytes")
    inflate.assert_not_called()


def test_seeded_permitted_drawing_matches_unclipped_vectors(tmp_path):
    rng = random.Random(1031)
    p = new_project(width=13, height=11)
    for _ in range(100):
        a, b = [(rng.randrange(-20, 25), rng.randrange(-20, 25)) for _ in range(2)]
        geometry = raster.line_points(*a, *b)
        expected = {(x, y) for x, y in geometry if 0 <= x < 13 and 0 <= y < 11}
        project = p.model_copy(deep=True)
        ctx = OpContext(project, tmp_path)
        args = (
            ops.registry()
            .get("line")
            .parse(dict(layer="L1", frame=0, color=1, x0=a[0], y0=a[1], x1=b[0], y1=b[1]))
        )
        drawing(ctx, args, "line")
        image = render_module.render_indexed(project)
        assert {(int(x), int(y)) for y, x in np.argwhere(image == 1)} == expected
        assert ctx.clipped_pixels == len(geometry) - len(expected)


@pytest.mark.parametrize("surface", ["op", "export"])
def test_frame_range_checked_before_expansion(monkeypatch, surface):
    from cybersprite.formats.common import frame_sequence
    from cybersprite.ops.common import frames

    p = new_project(width=2, height=2)
    function = frames if surface == "op" else frame_sequence
    module = importlib.import_module(function.__module__)
    expand = Mock(side_effect=AssertionError("must not expand range"))
    monkeypatch.setattr(module, "range", expand, raising=False)
    with pytest.raises(CyberSpriteError) as error:
        function(p, "0-1000000000")
    assert error.value.code == "E_FRAME_OUT_OF_RANGE"
    expand.assert_not_called()


def test_animation_repeat_budget_before_expansion(monkeypatch):
    from cybersprite.core.models import Tag
    from cybersprite.formats import common

    p = new_project(width=4096, height=4096, frames=2)
    p.tags = [Tag(id="T1", name="repeat", from_=0, to=1, repeat=65535)]
    expand = Mock(side_effect=AssertionError("must not expand tag"))
    monkeypatch.setattr(common, "range", expand, raising=False)
    exceeded(lambda: common.animation_sequence(p, tag="T1"), "output_bytes")
    expand.assert_not_called()


def test_sheet_item_budget_before_render(monkeypatch):
    p = new_project(width=2, height=2)
    args = SheetArgs.model_validate(dict(out="unused.png"))
    monkeypatch.setattr(sheet, "OUTPUT_BYTES", 1)
    render = Mock(side_effect=AssertionError("must not render"))
    monkeypatch.setattr(sheet, "indexed_result", render)
    exceeded(lambda: sheet.enumerate_items(p, args), "output_bytes")
    render.assert_not_called()


def test_sheet_candidate_count_before_loops(monkeypatch):
    p = new_project(width=2, height=2)
    args = SheetArgs.model_validate(dict(out="unused.png"))
    monkeypatch.setattr(sheet, "OUTPUT_ITEMS", 0)
    render = Mock(side_effect=AssertionError("must not render"))
    monkeypatch.setattr(sheet, "indexed_result", render)
    exceeded(lambda: sheet.enumerate_items(p, args), "output_items", 1, 0)
    render.assert_not_called()


def test_sheet_ignored_frames_still_consume_work(monkeypatch):
    p = new_project(width=2, height=2, frames=2)
    args = SheetArgs.model_validate(dict(out="unused.png", ignore_empty=True))
    monkeypatch.setattr(sheet, "OUTPUT_BYTES", 20)
    render = Mock(wraps=sheet.indexed_result)
    monkeypatch.setattr(sheet, "indexed_result", render)
    exceeded(lambda: sheet.enumerate_items(p, args), "output_bytes", 32, 20)
    assert render.call_count == 1


def test_animation_decoders_budget_before_frames(monkeypatch):
    from cybersprite.formats.animation import decode_apng, decode_gif

    image = LazyImage(8192, 8192, 2)
    monkeypatch.setattr("PIL.Image.open", lambda _: image)
    exceeded(lambda: decode_gif(b"unused"), "output_bytes")
    image.convert.assert_not_called()
    data = (
        SIGNATURE
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", 8192, 8192, 8, 6, 0, 0, 0))
        + _chunk(b"acTL", struct.pack(">II", 2, 0))
        + _chunk(b"IEND", b"")
    )
    decode = Mock(side_effect=AssertionError("must not decode frame"))
    monkeypatch.setattr("cybersprite.formats.animation.decode_png", decode)
    exceeded(lambda: decode_apng(data), "output_bytes")
    decode.assert_not_called()
