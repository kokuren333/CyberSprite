"""Every M2 contract has a happy-path case and a primary failure case."""

from copy import deepcopy

import numpy as np
import pytest

from cybersprite.core.canonical import dumps_project, load_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.models import GroupLayer, LinkCel
from cybersprite.core.references import cel_at, cel_owner, walk_layers
from cybersprite.core.render import render, render_indexed
from cybersprite.core.validation import check_structure
from cybersprite.formats.png import decode_png
from cybersprite.ops import execute, registry

DRAW = {"layer": "L1", "frame": 0}


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_NOW", "2026-11-12T12:00:00+09:00")
    path = tmp_path / "sample.csprite"
    execute("new_project", path, {"width": 8, "height": 8, "frames": 3})
    execute(
        "draw_rows",
        path,
        {**DRAW, "x": 1, "y": 1, "rows": ["010100", "010201", "000101"]},
        preview="none",
    )
    execute("add_layer", path, {"name": "Upper"}, preview="none")
    execute(
        "set_pixel", path, {"layer": "L2", "frame": 0, "x": 5, "y": 5, "color": 2}, preview="none"
    )
    execute("add_tag", path, {"name": "loop", "from": 0, "to": 2}, preview="none")
    execute(
        "add_slice",
        path,
        {"name": "bounds", "keys": [{"frame": 0, "x": 0, "y": 0, "w": 4, "h": 4}]},
        preview="none",
    )
    return path


CASES = {
    "set_pixel": {**DRAW, "x": 0, "y": 0, "color": 1},
    "set_pixels": {**DRAW, "pixels": [[1, 1, 2], [2, 2, 1]]},
    "draw_rows": {**DRAW, "x": 0, "y": 0, "rows": [".12", "21."], "format": "sym"},
    "line": {**DRAW, "x0": 0, "y0": 0, "x1": 7, "y1": 5, "color": 1},
    "rect": {**DRAW, "x": 0, "y": 0, "w": 5, "h": 4, "color": 1},
    "ellipse": {**DRAW, "x": 0, "y": 0, "w": 5, "h": 4, "color": 1, "filled": True},
    "polygon": {**DRAW, "points": [[0, 0], [4, 0], [2, 6]], "color": 1, "filled": True},
    "stroke": {**DRAW, "points": [[0, 0], [4, 2], [2, 6]], "color": 1, "pixel_perfect": True},
    "fill": {**DRAW, "x": 0, "y": 0, "color": 2},
    "erase": {**DRAW, "region": {"type": "rect", "x": 1, "y": 1, "w": 1, "h": 1}},
    "replace_color": {"from": 1, "to": 3},
    "transform_region": {**DRAW, "region": {"type": "all"}, "dx": 1, "rotate": 90},
    "outline": {**DRAW, "color": 3},
    "add_frame": {"at": 1, "cels": "link"},
    "delete_frames": {"frames": [0]},
    "move_frames": {"from": 0, "to": 0, "before": 3},
    "reverse_frames": {"from": 0, "to": 2},
    "set_frame_duration": {"frames": "tag:loop", "duration_ms": 120},
    "set_cel": {**DRAW, "x": 2, "y": -1, "opacity": 200},
    "clear_cel": DRAW,
    "copy_cel": {**DRAW, "to_frame": 1},
    "link_cel": {"layer": "L1", "source_frame": 0, "frames": [1, 2]},
    "unlink_cel": DRAW,
    "set_palette": {
        "colors": ["#00000000", "#000000ff", "#ffffffff"],
        "on_shrink": "to_transparent",
    },
    "set_palette_color": {"index": 1, "color": "#abcd12ff", "name": "test"},
    "add_palette_colors": {"colors": ["#abcd12ff"]},
    "remap_palette": {"sort_by": "usage"},
    "load_palette": {"source": "cs-circuit-32"},
    "set_palette_frozen": {"frozen": True},
    "add_layer": {"name": "Group", "type": "group"},
    "update_layer": {"layer": "L2", "name": "Renamed", "locked": True},
    "delete_layer": {"layer": "L2"},
    "duplicate_layer": {"layer": "L1"},
    "merge_layers": {"layers": ["L1", "L2"]},
    "flatten": {},
    "add_tag": {"name": "extra", "from": 1, "to": 2},
    "update_tag": {"tag": "T1", "from": 1, "repeat": 2},
    "delete_tag": {"tag": "T1"},
    "add_slice": {"name": "extra", "keys": [{"frame": 1, "x": 1, "y": 1, "w": 2, "h": 2}]},
    "update_slice": {"slice": "S1", "set_key": {"frame": 1, "x": 1, "y": 2, "w": 2, "h": 2}},
    "delete_slice": {"slice": "S1"},
    "resize_canvas": {"width": 10, "height": 9, "anchor": "c"},
    "crop_canvas": {"rect": "content"},
    "scale_sprite": {"factor": 2},
    "transform_sprite": {"flip": "h", "rotate": 90},
    "set_project_meta": {"name": "Changed", "grid": {"x": 0, "y": 0, "w": 4, "h": 4}},
    "set_validation": {"settings": {"palette_max": 4}},
    "apply_ops": {"ops": [{"op": "set_pixel", "args": {**DRAW, "x": 0, "y": 0, "color": 2}}]},
    "undo": {},
    "redo": {},
    "get_info": {
        "include": [
            "summary",
            "layers",
            "frames",
            "tags",
            "slices",
            "tilesets",
            "palette",
            "sources",
            "validation",
            "history",
        ]
    },
    "get_pixels": {**DRAW, "format": "sym"},
    "get_palette": {},
    "validate": {},
    "get_history": {},
    "render_preview": {
        "frames": [0, 1],
        "grid": True,
        "rulers": True,
        "onion": {"next": 1},
        "inline": False,
    },
    "diff_preview": {"inline": False},
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_op_happy_path_and_undo(project, name):
    if name == "redo":
        execute("undo", project, {}, preview="none")
    if name == "unlink_cel":
        execute(
            "link_cel", project, {"layer": "L1", "source_frame": 0, "frames": 1}, preview="none"
        )
    before = load_project(project)
    kwargs = {"preview": "none"} if registry().get(name).kind == "mutate" else {}
    result = execute(name, project, deepcopy(CASES[name]), **kwargs)
    assert result["ok"]
    current = load_project(project)
    assert not check_structure(current)
    if name in ("render_preview", "diff_preview"):
        for path in result["result"]["paths"]:
            assert decode_png((project / path).read_bytes()).pixels.size
    if (
        registry().get(name).kind == "mutate"
        and not result["no_op"]
        and name not in ("undo", "redo")
    ):
        execute("undo", project, {}, preview="none")
        restored = load_project(project)
        restored.revision = before.revision
        assert dumps_project(restored) == dumps_project(before)


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_op_rejects_unknown_argument_without_changing_files(project, name):
    before = {
        str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
    with pytest.raises(CyberSpriteError) as error:
        execute(name, project, {**CASES[name], "unknown_argument": True})
    assert error.value.code == "E_INVALID_ARGS"
    after = {str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    assert before == after


@pytest.mark.parametrize("name", [n for n in CASES if registry().get(n).idempotency == "I"])
def test_class_i_second_call_is_no_op(project, name):
    execute(name, project, deepcopy(CASES[name]), preview="none")
    assert execute(name, project, deepcopy(CASES[name]), preview="none")["no_op"]


def test_registry_coverage_and_contracts():
    from cybersprite.formats.export_args import EXPORT_ARGS
    from cybersprite.ops import TILES

    assert {op.name for op in registry().all()} == set(CASES) | set(EXPORT_ARGS) | TILES | {
        "new_project",
        "cleanup_pixels",
        "import_aseprite",
        "import_image",
        "add_source",
        "register_reference",  # Registration, guards and hashes: test_publication_references.py.
        "list_sources",
        "get_source",
        "list_generators",
        "generate_image",
        "export_plugin",
        "export_native",  # Native vectors and failure paths: test_r1_e3_native_ramps.py.
        "shift_ramp",  # Material, mask, link and undo paths: test_r1_e3_native_ramps.py.
        "move_cel",
        "set_platform",
        "list_platforms",
        "conform_palette",
        "set_frame_ticks",
    }
    for op in registry().all():
        description = op.describe()
        assert description["inputSchema"]["additionalProperties"] is False
        assert description["outputSchema"]["additionalProperties"] is False
        assert description["resultSchema"]["additionalProperties"] is False
        assert "project" in description["inputSchema"]["required"]
        assert description["annotations"]["readOnlyHint"] == (op.kind == "query")
    with pytest.raises(CyberSpriteError, match="Unknown") as error:
        registry().get("set_pixe")
    assert error.value.code == "E_UNKNOWN_OP" and "set_pixel" in error.value.details["candidates"]


def test_new_project_and_cleanup_contracts(tmp_path):
    p = tmp_path / "new"
    result = execute("new_project", p, {"width": 4, "height": 3, "background": 1})
    assert result["result"]["summary"]["palette_size"] == 17
    assert load_project(p).layers[0].background
    assert (
        execute("new_project", p, {"width": 4, "height": 3, "if_exists": "open"})["revision"] == 0
    )
    for args, code in [
        ({"width": 4, "height": 3}, "E_EXISTS"),
        ({"width": 5, "height": 3, "if_exists": "open"}, "E_INVALID_ARGS"),
    ]:
        with pytest.raises(CyberSpriteError) as error:
            execute("new_project", p, args)
        assert error.value.code == code
    cleaned = execute("cleanup_pixels", p, {"layer": "L1"}, preview="none")
    assert cleaned["no_op"] and cleaned["result"]["positions"] == []


@pytest.mark.parametrize(
    ("name", "args", "code"),
    [
        ("set_pixel", {**DRAW, "x": 0, "y": 0, "color": 256}, "E_INDEX_OUT_OF_RANGE"),
        ("set_pixel", {**DRAW, "x": 0, "y": 0, "color": "#010203"}, "E_COLOR_NOT_IN_PALETTE"),
        (
            "set_pixel",
            {**DRAW, "layer": "missing", "x": 0, "y": 0, "color": 1},
            "E_LAYER_NOT_FOUND",
        ),
        ("fill", {**DRAW, "x": -1, "y": 0, "color": 1}, "E_OUT_OF_CANVAS"),
        (
            "stroke",
            {**DRAW, "points": [[0, 0]], "color": 1, "brush": {"size": 2}, "pixel_perfect": True},
            "E_INVALID_ARGS",
        ),
        ("set_pixels", {**DRAW}, "E_INVALID_ARGS"),
        ("draw_rows", {**DRAW, "x": 0, "y": 0, "rows": ["ff"]}, "E_INDEX_OUT_OF_RANGE"),
        ("set_cel", {**DRAW, "frame": 1, "x": 1}, "E_CEL_NOT_FOUND"),
        ("copy_cel", {**DRAW, "to_frame": 3}, "E_FRAME_OUT_OF_RANGE"),
        ("delete_frames", {"frames": "all"}, "E_INVALID_ARGS"),
        ("move_frames", {"from": 2, "to": 0, "before": 0}, "E_INVALID_ARGS"),
        ("set_palette", {"colors": ["#00000000"]}, "E_INDEX_OUT_OF_RANGE"),
        ("remap_palette", {"order": [0]}, "E_INVALID_ARGS"),
        ("add_layer", {"name": "Upper"}, "E_EXISTS"),
        ("add_tag", {"name": "loop", "from": 0, "to": 1}, "E_EXISTS"),
        ("update_tag", {"tag": "missing", "name": "x"}, "E_TAG_NOT_FOUND"),
        (
            "add_slice",
            {"name": "bounds", "keys": [{"frame": 0, "x": 0, "y": 0, "w": 1, "h": 1}]},
            "E_EXISTS",
        ),
        ("update_slice", {"slice": "missing", "name": "x"}, "E_SLICE_NOT_FOUND"),
        ("merge_layers", {"layers": ["L1"]}, "E_INVALID_ARGS"),
        ("resize_canvas", {"width": 8193, "height": 1}, "E_LIMIT_EXCEEDED"),
    ],
)
def test_primary_semantic_errors(project, name, args, code):
    before = (project / "project.json").read_bytes()
    with pytest.raises(CyberSpriteError) as error:
        execute(name, project, args, preview="none")
    assert error.value.code == code
    assert (project / "project.json").read_bytes() == before


def test_clipping_shared_edit_unlink_and_owner_deletion(project):
    execute(
        "link_cel", project, {"layer": "L1", "source_frame": 0, "frames": [1, 2]}, preview="none"
    )
    result = execute(
        "set_pixels",
        project,
        {**DRAW, "frame": 2, "pixels": [[-1, 0, 1], [0, 0, 3], [0, 0, 2]]},
        preview="none",
    )
    assert result["changed"]["clipped_pixels"] == 1
    assert result["result"]["pixels_written"] == 1
    assert result["changed"]["linked_frames"] == [0, 1, 2]
    p = load_project(project)
    assert isinstance(cel_at(p.layers[0], 2), LinkCel)
    execute("unlink_cel", project, {**DRAW, "frame": 0}, preview="none")
    p = load_project(project)
    assert not isinstance(cel_at(p.layers[0], 0), LinkCel)
    assert cel_at(p.layers[0], 2).link == 1
    old = render(p, 2)
    execute("clear_cel", project, {**DRAW, "frame": 1}, preview="none")
    assert np.array_equal(render(load_project(project), 2), old)


def test_lock_ancestor_and_background_rules(project):
    group = execute("add_layer", project, {"name": "Group", "type": "group"}, preview="none")[
        "result"
    ]["id"]
    execute("update_layer", project, {"layer": "L2", "parent": group}, preview="none")
    execute("update_layer", project, {"layer": group, "locked": True}, preview="none")
    with pytest.raises(CyberSpriteError) as error:
        execute(
            "set_pixel",
            project,
            {"layer": "L2", "frame": 0, "x": 1, "y": 1, "color": 1},
            preview="none",
        )
    assert error.value.code == "E_LAYER_LOCKED"
    execute("update_layer", project, {"layer": group, "locked": False}, preview="none")
    with pytest.raises(CyberSpriteError) as error:
        execute("update_layer", project, {"layer": group, "parent": group}, preview="none")
    assert error.value.code == "E_INVALID_ARGS"
    execute("update_layer", project, {"layer": "L2", "background": True}, preview="none")
    p = load_project(project)
    assert p.layers[0].id == "L2" and len(p.layers[0].cels) == 3
    execute("clear_cel", project, {"layer": "L2", "frame": 0}, preview="none")
    assert not check_structure(load_project(project))


def test_palette_remapping_preserves_picture(project):
    before = render(load_project(project), 0)
    result = execute(
        "remap_palette",
        project,
        {"order": list(reversed(range(17))), "keep_transparent_first": False},
        preview="none",
    )
    p = load_project(project)
    assert p.palette.transparent_index == 16
    assert result["result"]["mapping"]["0"] == 16
    assert np.array_equal(render(p, 0), before)
    execute("set_palette_frozen", project, {"frozen": True}, preview="none")
    with pytest.raises(CyberSpriteError) as error:
        execute("set_palette_color", project, {"index": 1, "color": "#123456"}, preview="none")
    assert error.value.code == "E_PALETTE_FROZEN"


def test_offcanvas_pixels_survive_regular_edits_and_resize(project):
    execute("set_cel", project, {**DRAW, "x": -1}, preview="none")
    p = load_project(project)
    first = cel_owner(p.layers[0], cel_at(p.layers[0], 0))
    saved = array_copy = bytes.fromhex(first.pixels[0])[0]
    execute("set_pixel", project, {**DRAW, "x": 7, "y": 7, "color": 2}, preview="none")
    p = load_project(project)
    first = cel_owner(p.layers[0], cel_at(p.layers[0], 0))
    assert first.x == -1 and bytes.fromhex(first.pixels[0])[0] == saved == array_copy
    execute("crop_canvas", project, {"rect": {"x": 0, "y": 0, "w": 4, "h": 4}}, preview="none")
    assert cel_at(load_project(project).layers[0], 0).x >= 0


def test_canonical_indexed_rgba_equivalence(project):
    p = load_project(project)
    image = render_indexed(p, 0)
    from cybersprite.core.pixels import rgba

    colors = np.array(
        [
            rgba(c) if i != p.palette.transparent_index else (0, 0, 0, 0)
            for i, c in enumerate(p.palette.colors)
        ],
        dtype=np.uint8,
    )
    assert np.array_equal(render(p, 0), colors[image])
    assert not any(isinstance(node, GroupLayer) for node, _ in walk_layers(p.layers))
