"""Hand-computed review, craft and platform row/flip acceptance vectors."""

from types import SimpleNamespace

import numpy as np
import pytest
from click.testing import CliRunner

from cybersprite import ops
from cybersprite.cli import cli
from cybersprite.config import UserConfig
from cybersprite.core import canonical
from cybersprite.core.craft import measure
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.models import ImageCel, Slice, Tag, TileCel, TilemapLayer, Tileset
from cybersprite.core.palette_units import resources, violations
from cybersprite.core.pixels import pixels_to_rows
from cybersprite.core.projects import new_project
from cybersprite.core.quality import report, validation_delta
from cybersprite.core.review_sheet import luminance, playback_frames, review_sheet
from cybersprite.formats.png import decode_png
from cybersprite.platforms import plugin_definitions, resolve
from cybersprite.plugins import PluginManager


@pytest.fixture(autouse=True)
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_CONFIG_DIR", str(tmp_path / "config"))


def project(pixels, *, platform=None, palette=None):
    data = np.array(pixels, dtype=np.uint8)
    p = new_project(width=data.shape[1], height=data.shape[0], palette=palette)
    p.layers[0].cels = [
        ImageCel(frame=0, x=0, y=0, w=data.shape[1], h=data.shape[0], pixels=pixels_to_rows(data))
    ]
    p.platform = resolve(platform) if platform else None
    return p


def test_craft_hand_vector():
    image = np.zeros((5, 5, 4), dtype=np.uint8)
    image[1:4, 1:4] = (255, 255, 255, 255)
    assert measure(image) == dict(
        fill_permille=360,
        depth_max=2,
        flat_permille=111,
        region_density_x100=11,
        outline={"dark_permille": 1000},
    )
    assert measure(np.zeros((1, 1, 4), dtype=np.uint8)) == dict(
        fill_permille=0,
        depth_max=0,
        flat_permille=0,
        region_density_x100=0,
        outline={"dark_permille": 0},
    )
    assert measure(np.full((3, 3, 4), 255, dtype=np.uint8))["depth_max"] == 2
    image[2, 2] = (0, 0, 0, 255)
    values = measure(image)
    assert values["flat_permille"] == 0
    assert values["region_density_x100"] == 22
    assert values["outline"]["dark_permille"] == 0


def test_craft_info_fixed_and_independent_metric_delta():
    p = project([[1]], platform={"craft": {"fill_permille": [0, 0], "depth_max": [0, 0]}})
    p.validation.severity["Q-CRF-01"] = "error"
    before = report(p)
    issues = [i for i in before["issues"] if i["rule"] == "Q-CRF-01"]
    assert len(issues) == 2 and {i["level"] for i in issues} == {"info"}
    assert before["ok"]
    assert before["metrics"]["platform"]["craft"]["frames"][0]["fill_permille"] == 1000
    p.platform.craft.depth_max = [0, 1]
    delta = validation_delta(before, report(p))
    assert [i["where"]["metric"] for i in delta["resolved_issues"]] == ["depth_max"]
    p.validation.severity["Q-CRF-01"] = "off"
    after = report(p)
    assert not any(i["rule"] == "Q-CRF-01" for i in after["issues"])
    assert "craft" in after["metrics"]["platform"]


def test_parts_keyframes_and_missing():
    p = project(
        [[1]],
        platform={
            "craft": {"parts": {"eye.near.w/head.w": [300, 400], "missing.h/head.h": [1, 10]}}
        },
    )
    p.slices = [
        Slice(id="S1", name="part.eye.near", keys=[dict(frame=0, x=0, y=0, w=3, h=2)]),
        Slice(id="S2", name="part.head", keys=[dict(frame=0, x=0, y=0, w=10, h=8)]),
    ]
    p.id_counters.slice = 2
    result = report(p)
    parts = result["metrics"]["platform"]["craft"]["frames"][0]["parts"]
    assert parts == {"eye.near.w/head.w": 300, "missing.h/head.h": None}
    assert not any(i["rule"] == "Q-CRF-01" for i in result["issues"])


@pytest.mark.parametrize("unit,expected", [("object", 1), ("layer", 1), ("tile", 0), ("block", 0)])
def test_palette_unit_rows(unit, expected):
    platform = {
        "system": {
            "palette": {"rows": 2, "row_size": 4, "unit": unit, "block": {"w": 1, "h": 1}},
            "tile": {"w": 1, "h": 1},
        }
    }
    p = project([[1, 5]], platform=platform, palette=["#00000000"] + ["#ffffffff"] * 8)
    assert len(violations(p)) == expected
    if expected:
        location = violations(p)[0]
        assert location["rows"] == [0, 1] and location["layer"] == "L1"
        assert any(i["rule"] == "Q-PLT-04" for i in report(p)["issues"])


@pytest.mark.parametrize(
    "slot0,data,expected",
    [
        ("transparent", [0, 1], False),
        ("transparent", [4, 5], True),
        ("shared", [0, 5], False),
        ("shared", [4, 5], True),
        ("color", [1, 4], False),
        ("color", [4, 5], True),
        ("color", [0, 1], True),
        ("transparent", [9, 9], True),
    ],
)
def test_slot0_hand_vectors(slot0, data, expected):
    p = project(
        [data],
        palette=["#00000000"] + ["#ffffffff"] * 9,
        platform={"system": {"palette": {"rows": 2, "row_size": 4, "slot0": slot0}}},
    )
    assert bool(violations(p)) is expected


def test_unique_flipped_tile_hand_vector():
    p = project(
        [[1, 0, 0, 1], [0, 0, 0, 0]],
        platform={"system": {"tile": {"w": 2, "h": 2, "unique_max": 1, "flips": {"x": True}}}},
    )
    result = report(p)
    assert result["metrics"]["platform"]["unique_tiles"] == 2
    assert result["metrics"]["platform"]["unique_tiles_with_flips"] == 1
    assert not any(i["rule"] == "Q-PLT-06" for i in result["issues"])
    p.platform.system.tile.flips.x = False
    assert any(i["rule"] == "Q-PLT-06" for i in report(p)["issues"])


def test_palette_findings_retain_each_block_position():
    p = project(
        [[1, 5, 1, 5]],
        palette=["#00000000"] + ["#ffffffff"] * 8,
        platform={
            "system": {
                "palette": {"rows": 2, "row_size": 4, "unit": "block", "block": {"w": 2, "h": 1}}
            }
        },
    )
    issue = next(i for i in report(p)["issues"] if i["rule"] == "Q-PLT-04")
    assert [v["bbox"]["x"] for v in issue["where"]["findings"]] == [0, 2]


def test_unique_tiles_preserve_distinct_indices_with_identical_rgba():
    p = project(
        [[1, 2]],
        palette=["#00000000", "#ffffffff", "#ffffffff"],
        platform={"system": {"tile": {"w": 1, "h": 1, "unique_max": 1}}},
    )
    result = report(p)
    assert result["metrics"]["platform"]["unique_tiles"] == 2
    assert any(i["rule"] == "Q-PLT-06" for i in result["issues"])


def test_palette_units_follow_rectangular_tile_renderer():
    p = project([[1, 2]], platform={"system": {"palette": {"rows": 1, "row_size": 4}}})
    p.tilesets = [
        Tileset(
            id="TS1",
            name="Test",
            tile_w=2,
            tile_h=1,
            tiles=[{"pixels": ["0000"]}, {"pixels": ["0102"]}],
        )
    ]
    p.layers = [
        TilemapLayer(
            id="L1",
            name="Map",
            tileset="TS1",
            cels=[TileCel(frame=0, x=0, y=0, w=1, h=1, tiles=["1d"])],
        )
    ]
    data = list(resources(p, include_tilesets=False))[0][0]
    assert data.tolist() == [[1, 2]]  # Non-square d follows the renderer's unchanged orientation.


@pytest.mark.parametrize(
    "direction,repeat,expected",
    [
        ("forward", 2, [0, 1, 2, 0, 1, 2]),
        ("reverse", 1, [2, 1, 0]),
        ("pingpong", 1, [0, 1, 2]),
        ("pingpong", 2, [0, 1, 2, 1, 0]),
        ("pingpong", 3, [0, 1, 2, 1, 0, 1, 2]),
        ("pingpong", 0, [0, 1, 2, 1]),
        ("pingpong_reverse", 2, [2, 1, 0, 1, 2]),
    ],
)
def test_review_playback(direction, repeat, expected):
    p = new_project(width=1, height=1, frames=3)
    p.tags = [Tag(id="T1", name="idle", **{"from": 0, "to": 2}, direction=direction, repeat=repeat)]
    assert playback_frames(p, [0, 1, 2]) == [("T1", expected)]


def test_review_pixels_gray_and_budget():
    p = project(
        [[1, 2]],
        platform={
            "system": {"screen": {"w": 4, "h": 3}},
            "defaults": {
                "preview": {"backgrounds": ["#ffffff", "#000000"]},
                "export": {"review_scale": 3},
            },
        },
    )
    image, scale, panels = review_sheet(p, [0])
    assert scale == 3
    assert [v["kind"] for v in panels] == ["actual", "actual", "zoom", "silhouette", "luminance"]
    panel = panels[0]
    assert (panel["w"], panel["h"]) == (6, 5)
    # Centered actual pixels: black then white, surrounded by the configured white background.
    assert image[panel["y"] + 2, panel["x"] + 2].tolist() == [0, 0, 0, 255]
    assert image[panel["y"] + 2, panel["x"] + 3].tolist() == [255, 255, 255, 255]
    gray = luminance(np.array([[[0, 0, 0, 255], [255, 255, 255, 255]]], dtype=np.uint8))
    assert gray.tolist() == [[[0, 0, 0, 255], [255, 255, 255, 255]]]
    p.platform.system.screen.w = 9000
    with pytest.raises(CyberSpriteError) as error:
        review_sheet(p, [0])
    assert error.value.code == "E_LIMIT_EXCEEDED"


def test_review_design_zoom_same_row_and_exact_scale():
    p = project(
        [[1, 2]], platform={"defaults": {"preview": {"backgrounds": ["#ffffff", "#000000"]}}}
    )
    design = np.full((1, 2, 4), (80, 80, 80, 255), dtype=np.uint8)
    image, scale, panels = review_sheet(p, [0], design=design)
    zoom = next(v for v in panels if v["kind"] == "zoom")
    reference = next(v for v in panels if v["kind"] == "design")
    assert zoom["y"] == reference["y"] and zoom["scale"] == reference["scale"] == scale
    assert image[reference["y"], reference["x"]].tolist() == [80, 80, 80, 255]


def test_review_screen_frame_never_silently_expands():
    p = project([[1, 2]], platform={"system": {"screen": {"w": 1, "h": 1}}})
    with pytest.raises(CyberSpriteError, match="select a smaller rect"):
        review_sheet(p, [0])
    _, _, panels = review_sheet(p, [0], rect={"x": 0, "y": 0, "w": 1, "h": 1})
    assert (panels[0]["w"], panels[0]["h"]) == (3, 3)


def test_preview_animation_review_defaults_to_all(tmp_path):
    root = tmp_path / "p"
    ops.execute("new_project", root, {"width": 2, "height": 2, "frames": 3}, preview="none")
    result = ops.execute("render_preview", root, {"layout": "review", "inline": False})["result"]
    assert next(v for v in result["panels"] if v["kind"] == "playback")["frames"] == [0, 1, 2]


def test_review_op_cli_and_no_project_changes(tmp_path):
    root = tmp_path / "p"
    ops.execute("new_project", root, {"platform": "dmg/sprite-16"}, preview="none")
    before = (root / "project.json").read_bytes()
    result = ops.execute("render_preview", root, {"layout": "review", "inline": False})["result"]
    image = decode_png((root / result["paths"][0]).read_bytes()).rgba()
    assert image.shape[:2] == (result["height"], result["width"])
    assert result["panels"][0]["kind"] == "actual"
    assert (root / "project.json").read_bytes() == before
    response = CliRunner().invoke(cli, ["--project", str(root), "preview", "--layout", "review"])
    assert response.exit_code == 0, response.output


def test_platform_plugins_shared_loader():
    calls = []

    def factory():
        calls.append("factory")
        return {"test": {"title": "Test"}}

    factory.plugin_api = 1
    entry = SimpleNamespace(
        name="provider", value="provider:factory", dist=None, load=lambda: factory
    )
    manager = PluginManager(
        UserConfig.model_validate({"plugins": {"enabled": ["provider"]}}),
        groups=("cybersprite.platforms",),
        entry_points=lambda **_: [entry],
    )
    assert manager.listing()[0]["loaded"] is False and calls == []
    assert plugin_definitions(manager)["test"] == (
        {"id": "test", "title": "Test"},
        "plugin:provider",
    )
    assert calls == ["factory"] and manager.listing()[0]["loaded"] is True
    manager.plugin_settings.disabled.append("provider")
    assert plugin_definitions(manager) == {}
    manager.plugin_settings.disabled.clear()
    manager.discard("cybersprite.platforms", "provider")
    factory.plugin_api = 2
    with pytest.raises(CyberSpriteError):
        plugin_definitions(manager)
    assert calls == ["factory"]


def test_legacy_canonical_unchanged():
    from pathlib import Path

    data = Path("tests/golden/canonical/expected/canonical.project.json").read_bytes()
    assert canonical.dumps_project(canonical.loads_project(data)) == data
