"""Hand vectors and surface contracts for platform-independent M12 engineering."""

import base64
import json

import numpy as np
import pytest
from click.testing import CliRunner

from cybersprite.core import raster
from cybersprite.core.canonical import load_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.pixels import resolve_color
from cybersprite.core.previews import preview_array
from cybersprite.core.quality import report, validation_delta
from cybersprite.core.render import render_indexed
from cybersprite.core.sources import read_manifest
from cybersprite.formats.png import decode_png, encode_png
from cybersprite.ops import execute, registry

DRAW = {"layer": "L1", "frame": 0}


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_NOW", "2026-11-12T12:00:00+09:00")
    path = tmp_path / "engineering.csprite"
    execute("new_project", path, {"width": 16, "height": 12, "frames": 2})
    return path


def op(root, operation, **args):
    return execute(operation, root, args, preview="none")


def image(root):
    return render_indexed(load_project(root), 0)


@pytest.mark.parametrize(
    "shape,expected",
    [
        ({"type": "ellipse", "x": 0, "y": 0, "w": 5, "h": 3}, [".###.", "#####", ".###."]),
        ({"type": "polygon", "points": [[0, 0], [4, 0], [0, 2]]}, ["#####", "###..", "#...."]),
    ],
)
def test_shape_region_hand_vectors(shape, expected):
    actual = raster.region_mask(shape, 5, 3)
    assert actual.tolist() == [[c == "#" for c in row] for row in expected]


@pytest.mark.parametrize(
    "shape",
    [
        {"type": "ellipse", "x": -2, "y": 1, "w": 7, "h": 5},
        {"type": "ellipse", "x": 2, "y": 1, "w": 1, "h": 7},
        {"type": "polygon", "points": [[-2, 1], [6, 1], [3, 7], [1, 3]]},
        {"type": "polygon", "points": [[1, 1], [6, 6], [6, 1], [1, 6]]},
        {"type": "polygon", "points": [[2, 1], [2, 7]]},
    ],
)
def test_shape_regions_equal_drawing_ops(root, shape):
    args = {k: v for k, v in shape.items() if k != "type"}
    op(root, shape["type"], **DRAW, **args, color=1, filled=True)
    selected = raster.region_mask(shape, 16, 12)
    assert np.array_equal(image(root) == 1, selected)


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("and", [False, True, False, False]),
        ("or", [True, True, True, False]),
        ("not", [False, False, True, True]),
    ],
)
def test_combinator_hand_vectors(kind, expected):
    a = {"type": "rect", "x": 0, "y": 0, "w": 2, "h": 1}
    b = {"type": "rect", "x": 1, "y": 0, "w": 2, "h": 1}
    spec = {"type": kind, "of": [a] if kind == "not" else [a, b]}
    assert raster.region_mask(spec, 4, 1).tolist() == [expected]


@pytest.mark.parametrize(
    "value,code",
    [
        ({"type": "not", "of": []}, "E_INVALID_ARGS"),
        ({"type": "and", "of": []}, "E_INVALID_ARGS"),
        ({"type": "not", "of": [{"type": "all"}] * 2}, "E_INVALID_ARGS"),
        ({"type": "or", "of": [{"type": "all"}] * 256}, "E_LIMIT_EXCEEDED"),
    ],
)
def test_region_limits_and_errors(value, code):
    with pytest.raises(CyberSpriteError) as error:
        registry().get("erase").parse({**DRAW, "region": value})
    assert error.value.code == code


def test_depth_checked_before_recursive_model_parsing():
    value = {"type": "all"}
    for _ in range(16):
        value = {"type": "not", "of": [value]}
    with pytest.raises(CyberSpriteError, match="depth") as error:
        registry().get("erase").parse({**DRAW, "region": value})
    assert error.value.code == "E_LIMIT_EXCEEDED"
    with pytest.raises(raster.RasterError) as error:
        raster.region_mask({"type": "ellipse", "x": 0, "y": 0, "w": 100000000, "h": 1}, 2, 2)
    assert error.value.code == "E_LIMIT_EXCEEDED"


def test_mask_before_drawing_duplicates_names_and_link_safety(root):
    op(root, "set_palette_color", index=1, color="#123456ff", name="shadow")
    op(root, "draw_rows", **DRAW, x=2, y=3, rows=["11122"], format="sym")
    op(root, "link_cel", layer="L1", source_frame=0, frames=[1])
    result = op(
        root,
        "set_pixels",
        layer="L1",
        frame=1,
        pixels=[[2, 3, 2], [2, 3, 3], [3, 3, 4], [4, 3, 4], [5, 3, 4]],
        mask={
            "only_on": ["@shadow"],
            "not_on": [2],
            "region": {"type": "rect", "x": 2, "y": 3, "w": 2, "h": 1},
        },
    )
    assert result["result"]["pixels_written"] == 2
    assert result["changed"]["linked_frames"] == [0, 1]
    assert image(root)[3, 2:7].tolist() == [3, 4, 1, 2, 2]
    assert np.array_equal(image(root), render_indexed(load_project(root), 1))


def test_mask_intersection_empty_and_transform(root):
    op(root, "draw_rows", **DRAW, x=1, y=1, rows=["123"], format="sym")
    op(root, "link_cel", layer="L1", source_frame=0, frames=[1])
    op(root, "replace_color", **{"from": 1, "to": 4, "mask": {"not_on": [1]}})
    assert image(root)[1, 1] == 1
    shifted = op(
        root, "transform_region", **DRAW, region={"type": "all"}, dx=2, mask={"only_on": [2]}
    )
    assert shifted["changed"]["linked_frames"] == [0, 1]
    assert np.array_equal(image(root), render_indexed(load_project(root), 1))
    assert image(root)[1, 1:5].tolist() == [1, 0, 3, 2]
    result = op(root, "fill", **DRAW, x=0, y=0, color=3, mask={"only_on": []})
    assert result["no_op"]


@pytest.mark.parametrize(
    "operation,args",
    [
        ("set_pixel", {"x": 0, "y": 0, "color": 3}),
        ("set_pixels", {"pixels": [[0, 0, 3], [2, 2, 3]]}),
        ("draw_rows", {"x": 0, "y": 0, "rows": ["030303"]}),
        ("line", {"x0": 0, "y0": 0, "x1": 6, "y1": 6, "color": 3}),
        ("rect", {"x": 0, "y": 0, "w": 4, "h": 4, "color": 3, "filled": True}),
        ("ellipse", {"x": 0, "y": 0, "w": 4, "h": 4, "color": 3, "filled": True}),
        ("polygon", {"points": [[0, 0], [4, 0], [0, 4]], "color": 3, "filled": True}),
        ("stroke", {"points": [[0, 0], [6, 6]], "color": 3}),
        ("fill", {"x": 0, "y": 0, "color": 3}),
        ("erase", {"region": {"type": "all"}}),
        ("outline", {"color": 3}),
        ("transform_region", {"region": {"type": "all"}, "dx": 2}),
        ("cleanup_pixels", {}),
    ],
)
def test_every_drawing_op_honors_empty_mask(root, operation, args):
    op(root, "set_pixel", **DRAW, x=2, y=2, color=1)
    before = (root / "project.json").read_bytes()
    result = op(root, operation, **DRAW, **args, mask={"only_on": []})
    assert result["no_op"] and result["result"]["pixels_written"] == 0
    assert (root / "project.json").read_bytes() == before


def test_nested_colour_region_resolves_names(root):
    op(root, "set_palette_color", index=1, color="#123456ff", name="shadow")
    op(root, "draw_rows", **DRAW, x=0, y=0, rows=["010201"])
    op(
        root,
        "line",
        **DRAW,
        x0=0,
        y0=0,
        x1=2,
        y1=0,
        color=3,
        mask={
            "region": {
                "type": "and",
                "of": [
                    {"type": "color", "color": "@shadow"},
                    {"type": "not", "of": [{"type": "rect", "x": 0, "y": 0, "w": 1, "h": 1}]},
                ],
            }
        },
    )
    assert image(root)[0, :3].tolist() == [1, 2, 3]


def test_outline_idempotency_and_default_n(root):
    op(root, "rect", **DRAW, x=5, y=4, w=3, h=3, color=1, filled=True)
    args = {**DRAW, "color": 2, "exclude_colors": [2]}
    first = op(root, "outline", **args)
    before = (root / "project.json").read_bytes()
    second = op(root, "outline", **args)
    assert not first["no_op"] and second["no_op"]
    assert (root / "project.json").read_bytes() == before
    assert registry().get("outline").idempotency == "N"
    assert not op(root, "outline", **DRAW, color=2)["no_op"]


def test_names_ambiguity_candidates_and_legend(root):
    op(root, "set_palette_color", index=1, color="#123456ff", name="body.base")
    op(
        root,
        "draw_rows",
        **DRAW,
        x=0,
        y=0,
        rows=["b.s"],
        format="sym",
        legend={"b": "@body.base", "s": 2},
    )
    assert image(root)[0, :3].tolist() == [1, 0, 2]
    p = load_project(root)
    with pytest.raises(CyberSpriteError) as unknown:
        resolve_color(p.palette, "@body.bse")
    assert unknown.value.code == "E_INVALID_ARGS"
    assert "body.base" in unknown.value.details["candidates"]
    op(root, "set_palette_color", index=2, color="#abcdefee", name="body.base")
    with pytest.raises(CyberSpriteError) as ambiguous:
        op(root, "set_pixel", **DRAW, x=0, y=0, color="@body.base")
    assert ambiguous.value.code == "E_AMBIGUOUS_REF"
    assert ambiguous.value.details["candidates"] == [1, 2]
    for legend, fmt in [({".": 1}, "sym"), ({"xx": 1}, "sym"), ({"b": 1}, "hex")]:
        with pytest.raises(CyberSpriteError):
            op(root, "draw_rows", **DRAW, x=0, y=0, rows=["0101"], format=fmt, legend=legend)


@pytest.mark.parametrize("grid", [False, True])
@pytest.mark.parametrize("scale", [1, 4])
def test_preview_crop_equals_full_preview(root, grid, scale):
    op(root, "set_pixel", **DRAW, x=5, y=4, color=2)
    p = load_project(root)
    options = {"scale": scale, "grid": grid, "onion": {"prev": 0, "next": 1}}
    full, _ = preview_array(p, 0, **options)
    crop, _ = preview_array(p, 0, rect={"x": 3, "y": 3, "w": 7, "h": 5}, **options)
    assert np.array_equal(crop, full[3 * scale : 8 * scale, 3 * scale : 10 * scale])


@pytest.mark.parametrize("layout", ["frames", "strip", "grid"])
def test_preview_crop_layouts_and_rulers(root, layout):
    original = (root / "project.json").read_bytes()
    result = execute(
        "render_preview",
        root,
        {
            "frames": [0, 1],
            "layout": layout,
            "rect": {"x": 7, "y": 3, "w": 5, "h": 7},
            "scale": 4,
            "rulers": True,
        },
    )
    assert len(result["result"]["paths"]) == (2 if layout == "frames" else 1)
    assert max(result["result"]["width"], result["result"]["height"]) <= 1024
    assert (root / "project.json").read_bytes() == original
    with pytest.raises(CyberSpriteError) as error:
        execute("render_preview", root, {"rect": {"x": -1, "y": 0, "w": 2, "h": 2}})
    assert error.value.code == "E_OUT_OF_CANVAS"


def test_delta_points_worsening_and_severity(root):
    op(root, "set_validation", settings={"orphan_pixels_max": 0})
    first = op(root, "set_pixel", **DRAW, x=1, y=1, color=1)
    assert first["validation"]["new_points_count"] == 2  # both pixel rules
    second = op(root, "set_pixel", **DRAW, x=5, y=5, color=1)
    updated = second["validation"]["updated_issues"]
    assert all(i["before"]["count"] == 1 and i["after"]["count"] == 2 for i in updated)
    assert all(i["where"]["layer"] == "L1" for i in updated)
    assert second["validation"]["new_points_count"] == 2
    severity = op(root, "set_validation", settings={"severity": {"Q-PIX-02": "error"}})
    entry = next(i for i in severity["validation"]["updated_issues"] if i["rule"] == "Q-PIX-02")
    assert entry["before"]["level"] == "info" and entry["after"]["level"] == "error"
    resolved = op(root, "set_pixel", **DRAW, x=1, y=1, color=0)
    assert resolved["validation"]["resolved_points_count"] == 2


def test_delta_full_sets_beyond_64_samples(root):
    p = load_project(root)
    from cybersprite.core.models import ImageCel

    p.canvas.width = p.canvas.height = 32
    data = np.zeros((32, 32), dtype=np.uint8)
    data[::2, ::2] = 1
    from cybersprite.core.pixels import pixels_to_rows

    p.layers[0].cels = [ImageCel(frame=0, x=0, y=0, w=32, h=32, pixels=pixels_to_rows(data))]
    before = report(p)
    data[30, 30] = 0
    p.layers[0].cels[0].pixels = pixels_to_rows(data)
    after = report(p)
    delta = validation_delta(before, after)
    assert delta["resolved_points_count"] == 1
    assert delta["resolved_points"][0]["x"] == 30
    assert delta["updated_issues"][0]["before"]["count"] == 256
    all_resolved = validation_delta(before, report(load_project(root)))
    assert all_resolved["resolved_points_count"] == 256
    assert len(all_resolved["resolved_points"]) == 64


def test_pixel_issue_layer_tracks_occlusion_and_multiple_contributors(root):
    op(root, "set_pixel", **DRAW, x=2, y=2, color=1)
    op(root, "add_layer", name="Front")
    op(root, "set_pixel", layer="L2", frame=0, x=2, y=2, color=2)
    result = execute("validate", root)["result"]
    issue = next(i for i in result["issues"] if i["rule"] == "Q-PIX-02")
    assert issue["where"]["layer"] == "L2"
    op(root, "set_pixel", **DRAW, x=8, y=8, color=1)
    result = execute("validate", root)["result"]
    issue = next(i for i in result["issues"] if i["rule"] == "Q-PIX-02")
    assert issue["where"]["layer"] is None


def test_add_source_provenance_guide_and_byte_invariance(root, tmp_path):
    design = np.full((5, 7, 4), (123, 45, 67, 255), dtype=np.uint8)
    source = tmp_path / "design.png"
    source.write_bytes(encode_png(design))
    original = (root / "project.json").read_bytes()
    args = {"files": str(source), "provenance": {"license": "unknown", "provider": "user"}}
    dry = execute("add_source", root, args, dry_run=True)
    assert dry["result"]["source"] is None and not (root / "source/manifest.json").exists()
    added = execute("add_source", root, args, idempotency_key="design")
    replay = execute("add_source", root, args, idempotency_key="design")
    assert replay["replayed"] and replay["result"] == added["result"]
    stored = read_manifest(root).sources[0]
    assert stored.use == "design" and stored.pipeline is None and stored.placements == []
    assert stored.license == "unknown" and stored.provider == "user"
    assert (root / stored.files[0].path).read_bytes() == source.read_bytes()
    for layout, guide_file in (
        ("frames", None),
        ("strip", stored.files[0].path),
        ("grid", str((root / stored.files[0].path).resolve())),
    ):
        result = execute(
            "render_preview",
            root,
            {
                "frames": [0, 1],
                "layout": layout,
                "scale": 3,
                "rect": {"x": 2, "y": 1, "w": 4, "h": 4},
                "guide": {"source": stored.id, "file": guide_file},
            },
        )
        raw = base64.b64decode(result["result"]["images"][0])
        decoded = decode_png(raw)
        assert np.any(np.all(decoded.pixels[:, :, :3] == [123, 45, 67], axis=2))
    assert (root / "project.json").read_bytes() == original
    with pytest.raises(CyberSpriteError):
        execute("add_source", root, {"files": str(source), "provenance": {}})
    with pytest.raises(CyberSpriteError):
        execute("render_preview", root, {"guide": {"source": stored.id, "file": "../design.png"}})


def test_source_retry_precedes_revision_check(root, tmp_path):
    file = tmp_path / "design.png"
    file.write_bytes(encode_png(np.full((2, 2, 4), 255, dtype=np.uint8)))
    args = {"files": str(file), "provenance": {"license": "unknown"}}
    added = execute("add_source", root, args, idempotency_key="retry", expect_revision=0)
    op(root, "set_pixel", **DRAW, x=1, y=1, color=1)
    before = (root / "project.json").read_bytes()
    replay = execute("add_source", root, args, idempotency_key="retry", expect_revision=0)
    assert replay["replayed"] and replay["result"] == added["result"]
    assert (root / "project.json").read_bytes() == before
    assert len(read_manifest(root).sources) == 1
    with pytest.raises(CyberSpriteError) as error:
        execute("add_source", root, args, idempotency_key="new", expect_revision=0)
    assert error.value.code == "E_REVISION_CONFLICT"
    with pytest.raises(CyberSpriteError) as error:
        execute(
            "add_source",
            root,
            {**args, "provenance": {"license": "CC0-1.0"}},
            idempotency_key="retry",
            expect_revision=0,
        )
    assert error.value.code == "E_INVALID_ARGS"


def test_design_header_limit_precedes_pixel_decode(monkeypatch):
    from unittest.mock import MagicMock

    from cybersprite.formats import design_sources

    decoder = MagicMock()
    decoder.__enter__.return_value = decoder
    decoder.size = (8193, 1)
    monkeypatch.setattr(design_sources.Image, "open", lambda stream: decoder)
    with pytest.raises(CyberSpriteError) as error:
        design_sources.decode_design(b"header-only fixture")
    assert error.value.code == "E_LIMIT_EXCEEDED"
    decoder.convert.assert_not_called()


def test_cli_contract_rect_names_mask_and_source(root, tmp_path):
    from cybersprite.cli import cli as command

    runner = CliRunner()

    def cli(*args):
        result = runner.invoke(command, ["--project", str(root), *args])
        assert result.exit_code == 0, result.output
        return json.loads(result.output)

    cli(
        "op",
        "set_pixel",
        "layer=L1",
        "frame=0",
        "x=2",
        "y=2",
        "color=1",
        'mask={"only_on":[0]}',
        "--preview",
        "none",
    )
    crop = cli("preview", "--rect", "1,1,4,3", "--scale", "2")
    assert crop["result"]["width"] == 8 and crop["result"]["height"] == 6
    file = tmp_path / "source.png"
    file.write_bytes(encode_png(np.full((2, 2, 4), 255, dtype=np.uint8)))
    value = cli("source", "add", str(file), "--provenance", '{"license":"CC0-1.0"}')
    assert value["result"]["source"] == "SRC1"
