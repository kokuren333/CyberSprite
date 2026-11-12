"""M11 platform contracts, hand vectors and snapshot determinism."""

import json
from pathlib import Path

import numpy as np
import pytest
from click.testing import CliRunner

from cybersprite import ops
from cybersprite.cli import cli
from cybersprite.core import canonical
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.models import ImageCel
from cybersprite.core.platform import (
    Tick,
    expand_channel,
    guide,
    tick_durations,
)
from cybersprite.core.projects import new_project
from cybersprite.core.quality import report
from cybersprite.platforms import list_platforms, merge, resolve


@pytest.fixture(autouse=True)
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setattr("cybersprite.platforms.plugin_definitions", lambda: {})


def create(root, **args):
    return ops.execute("new_project", root, args, preview="none")


def test_list_platforms_reports_inherited_system_role_and_canvas():
    listed = {p["id"]: p for p in list_platforms()}
    assert listed["nds/sprite-80"] == {
        "id": "nds/sprite-80",
        "title": "NDS-class sprite-80",
        "origin": "builtin",
        "system": "nds",
        "role": "sprite",
        "canvas": {"w": 80, "h": 80, "fixed": True},
    }
    assert listed["dmg/sprite-16"]["canvas"] == {"w": 16, "h": 16, "fixed": True}
    assert listed["nds"]["canvas"] is None and listed["nds"]["system"] == "nds"
    assert listed["sprite-80"]["system"] == "free"
    assert listed["sprite-80"]["canvas"]["fixed"] is False


def test_builtin_snapshots():
    ids = {p["id"] for p in list_platforms()}
    assert {"free", "dmg", "nds", "sprite-80", "motion", "dmg/background", "nds/sprite-96"} <= ids
    for id in sorted(ids):
        p = resolve(
            id, overrides={"/system/color/master_colors": [[0, 0, 0]]} if id == "nes" else None
        )
        assert p.id == id
        assert p.craft is None or p.craft.basis == "authored"
        assert len(guide(p).encode()) <= 2048
    p = resolve("nds/sprite-80")
    assert (p.asset.canvas.w, p.asset.canvas.h) == (80, 80)
    assert p.asset.colors.opaque_max == 15
    assert p.system.color.bits.r == 5
    assert p.system.tile.w == 8
    assert len(p.system.object.sizes) == 12


def test_resolver_precedence_inheritance_and_null(tmp_path, monkeypatch):
    directory = tmp_path / "config/platforms"
    directory.mkdir(parents=True)
    (directory / "free.json").write_text(
        json.dumps({"id": "free", "title": "User free", "extends": "sprite-16"}), encoding="utf-8"
    )
    # Self references through ancestors are cycles even across origins.
    with pytest.raises(CyberSpriteError, match="cycle"):
        resolve("free")
    (directory / "free.json").write_text(
        json.dumps({"id": "free", "title": "User free"}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "cybersprite.platforms.plugin_definitions",
        lambda: {"free": ({"id": "free", "title": "Plugin free"}, "plugin:test")},
    )
    assert resolve("free").title == "User free"
    file = tmp_path / "file.json"
    file.write_text(json.dumps({"id": "free", "title": "File free"}), encoding="utf-8")
    assert resolve("free", platform_file=file).title == "File free"
    assert (
        resolve({"extends": "free", "title": "Object free"}, platform_file=file).title
        == "Object free"
    )
    assert merge({"a": {"b": [1, 2], "c": 3}}, {"a": {"b": [4], "c": None}}) == {
        "a": {"b": [4], "c": None}
    }
    assert (
        resolve({"extends": "nds", "system": {"color": {"bits": None}}}).system.color.bits is None
    )


def test_plugin_precedence(monkeypatch):
    monkeypatch.setattr(
        "cybersprite.platforms.plugin_definitions",
        lambda: {"free": ({"id": "free", "title": "Plugin free"}, "plugin:test")},
    )
    assert resolve("free").origin == "plugin:test"


@pytest.mark.parametrize(
    "overrides",
    [
        {"/missing": 1},
        {"bad": 1},
        {"/system/~2": 1},
        {"/system/tile/w": 0},
        {"/system/tile/w": 257},
        {"/system/object/sizes/-1/0": 16},
        {"/system/object/sizes/00/0": 16},
        {"/system/color/bits/r": 5.0},
    ],
)
def test_invalid_overrides(overrides):
    with pytest.raises(CyberSpriteError) as e:
        resolve("nds/sprite-80", overrides=overrides)
    assert e.value.code == "E_INVALID_ARGS"


def test_override_pointer_and_partial():
    p = resolve("nds/sprite-80", overrides={"/asset/canvas/w": 96, "/system/object/sizes/0/0": 16})
    assert p.asset.canvas.w == 96
    assert p.overrides == ["/asset/canvas/w", "/system/object/sizes/0/0"]
    assert resolve("free", width=48, height=48).asset.canvas.w == 48


def test_definition_palette_paths_cannot_bypass_transport_path_checks():
    for definition in (
        {"defaults": {"palette": "../outside.hex"}},
        {"system": {"color": {"model": "master", "master_palette": "../outside.hex"}}},
    ):
        with pytest.raises(CyberSpriteError) as error:
            resolve(definition)
        assert error.value.code == "E_INVALID_ARGS"


@pytest.mark.parametrize("platform", ["nds/sprite-80", "dmg/sprite-16"])
def test_snapshot_independent_of_definitions(tmp_path, monkeypatch, platform):
    root = tmp_path / "p"
    result = create(root, platform=platform)
    assert result["defaults_from_platform"] == [
        "asset.canvas.w",
        "asset.canvas.h",
        "defaults.palette",
        "defaults.grid",
    ]
    before = (root / "project.json").read_bytes()
    p = canonical.load_project(root)
    validation = report(p)
    monkeypatch.setattr(
        "cybersprite.platforms.definitions",
        lambda *a: (_ for _ in ()).throw(AssertionError("definition reread")),
    )
    monkeypatch.setattr(
        "cybersprite.formats.palette_files.read_palette",
        lambda *a: (_ for _ in ()).throw(AssertionError("master palette reread")),
    )
    assert report(canonical.loads_project(before)) == validation
    assert canonical.dumps_project(canonical.loads_project(before)) == before
    assert list(json.loads(before)).index("platform") == list(json.loads(before)).index("name") + 1


def test_legacy_bytes_and_synthetic_migration(monkeypatch):
    data = Path("tests/golden/canonical/expected/canonical.project.json").read_bytes()
    p = canonical.loads_project(data)
    assert p.platform is None
    assert canonical.dumps_project(p) == data
    raw = json.loads(data)
    raw["schema_version"] = 0
    seen = []

    def migrate(value):
        seen.append(value["schema_version"])
        return {**value, "schema_version": 1}

    monkeypatch.setitem(canonical.MIGRATIONS, 0, migrate)
    assert canonical.dumps_project(canonical.loads_project(json.dumps(raw))) == data
    assert seen == [0]


def test_user_default_and_explicit_arguments(tmp_path):
    folder = tmp_path / "config"
    folder.mkdir()
    (folder / "config.toml").write_text('[defaults]\nplatform="nds/sprite-80"\n', encoding="utf-8")
    create(tmp_path / "p", width=48, height=24, palette=["#00000000", "#000000ff"])
    p = canonical.load_project(tmp_path / "p")
    assert p.canvas.width == 48 and len(p.palette.colors) == 2
    assert p.platform.id == "nds/sprite-80"


def test_set_platform_dry_remove_and_copy(tmp_path):
    root = tmp_path / "p"
    create(root, width=16, height=16)
    before = (root / "project.json").read_bytes()
    result = ops.execute(
        "set_platform", root, {"platform": "dmg/sprite-16"}, dry_run=True, preview="none"
    )
    assert (root / "project.json").read_bytes() == before
    assert "colors_per_frame_max" in result["result"]["copied_validation_keys"]
    ops.execute("set_platform", root, {"platform": "dmg/sprite-16"}, preview="none")
    p = canonical.load_project(root)
    assert p.validation.colors_per_frame_max == 3
    assert p.palette.colors == canonical.loads_project(before).palette.colors
    ops.execute("set_platform", root, {"platform": None}, preview="none")
    assert b'"platform"' not in (root / "project.json").read_bytes()


def test_color_count_excludes_transparent(tmp_path):
    p = new_project(width=2, height=1)
    p.palette.transparent_index = 2
    p.layers[0].cels = [ImageCel(frame=0, x=0, y=0, w=2, h=1, pixels=["0201"])]
    m = report(p)["metrics"]
    assert m["colors_used"] == 1
    assert m["colors_per_frame"] == [1]
    assert "platform" not in m


@pytest.mark.parametrize("value,expected", [(0, 0), (1, 8), (16, 132), (31, 255)])
def test_replicate_vectors(value, expected):
    assert expand_channel(value, 5, "replicate") == expected
    assert expand_channel(value, 5, "shift") == value * 8


@pytest.mark.parametrize(
    "id,color,expected",
    [("dmg/sprite-16", "#808080ff", "#aaaaaaff"), ("nds/sprite-80", "#808080ff", "#7b8484ff")],
)
def test_conform_vectors(tmp_path, id, color, expected):
    root = tmp_path / "p"
    create(root, platform=id, palette=["#00000000", color])
    before = (root / "project.json").read_bytes()
    dry = ops.execute("conform_palette", root, {}, dry_run=True, preview="none")
    assert dry["result"]["replacements"] == [{"index": 1, "before": color, "after": expected}]
    assert (root / "project.json").read_bytes() == before
    ops.execute("conform_palette", root, {}, preview="none")
    assert canonical.load_project(root).palette.colors[1] == expected
    assert ops.execute("conform_palette", root, {}, preview="none")["no_op"]


def test_qplt_hand_vectors():
    p = new_project(width=9, height=9, frames=3, palette=["#00000000", "#80808080"])
    p.platform = resolve(
        "nds/sprite-80",
        overrides={
            "/asset/animation/tick": {"num": 1, "den": 24},
            "/asset/animation/tags": ["idle"],
            "/asset/animation/frames_max": 2,
        },
    )
    p.frames[0].duration_ms = 50
    p.layers[0].opacity = 128
    p.layers[0].cels = [ImageCel(frame=0, x=0, y=0, w=1, h=1, opacity=100, pixels=["01"])]
    result = report(p)
    found = {i["rule"]: i for i in result["issues"] if i["rule"].startswith("Q-PLT")}
    assert set(found) == {"Q-PLT-01", "Q-PLT-02", "Q-PLT-03", "Q-PLT-05", "Q-PLT-07", "Q-PLT-08"}
    assert found["Q-PLT-02"]["where"]["index"] == 1
    assert result["metrics"]["platform"]["unrepresentable_colors"] == 1
    assert set(report(p, rules=["Q-PAL-01"])["metrics"]["platform"]) == {
        "id",
        "opaque_max",
        "unrepresentable_colors",
        "unique_tiles",
        "unique_tiles_with_flips",
        "tick_deviations",
        "craft",
    }
    p.validation.severity.update({k: "off" for k in found})
    assert not any(i["rule"].startswith("Q-PLT") for i in report(p)["issues"])


def test_transparent_entry_rgb_is_still_checked(tmp_path):
    root = tmp_path / "p"
    create(root, platform="nds/sprite-80", palette=["#80808000", "#000000ff"])
    p = canonical.load_project(root)
    assert report(p)["metrics"]["colors_used"] == 0
    assert report(p)["metrics"]["platform"]["unrepresentable_colors"] == 1
    result = ops.execute("conform_palette", root, {}, preview="none")
    assert result["result"]["replacements"] == [
        {"index": 0, "before": "#80808000", "after": "#7b848400"}
    ]


def test_multiple_platform_color_findings_keep_every_index(tmp_path):
    root = tmp_path / "p"
    create(
        root, platform="nds/sprite-80", palette=["#00000000", "#808080ff", "#123456ff", "#aabbccff"]
    )
    result = report(canonical.load_project(root))
    issue = next(i for i in result["issues"] if i["rule"] == "Q-PLT-02")
    assert {item["index"] for item in issue["where"]["findings"]} == {1, 2, 3}
    assert all(item["nearest"].endswith("ff") for item in issue["where"]["findings"])


def test_background_screen_and_map():
    p = new_project(width=8, height=8)
    p.platform = resolve("dmg/background", overrides={"/asset/canvas/fixed": False})
    assert any(i["rule"] == "Q-PLT-01" for i in report(p)["issues"])
    p.canvas.width = 264
    p.canvas.height = 144
    assert any("map" in i["message"] for i in report(p)["issues"] if i["rule"] == "Q-PLT-01")


def test_tick_vectors_and_op(tmp_path):
    assert tick_durations([1] * 6, Tick(num=1, den=24)) == [41, 42, 42, 41, 42, 42]
    assert tick_durations([2, 1, 3], Tick(num=1, den=24)) == [83, 42, 125]
    root = tmp_path / "p"
    create(root, platform="motion", width=2, height=2, frames=6)
    result = ops.execute("set_frame_ticks", root, {"ticks": 1}, preview="none")
    assert result["result"]["durations_ms"] == [41, 42, 42, 41, 42, 42]
    assert report(canonical.load_project(root))["metrics"]["platform"]["tick_deviations"] == 0
    ops.execute("add_tag", root, {"name": "first", "from": 0, "to": 1}, preview="none")
    ops.execute("add_tag", root, {"name": "second", "from": 2, "to": 5}, preview="none")
    result = ops.execute("set_frame_ticks", root, {"ticks": 1}, preview="none")
    assert result["result"]["durations_ms"] == [41, 42, 41, 42, 42, 41]
    assert report(canonical.load_project(root))["metrics"]["platform"]["tick_deviations"] == 0


@pytest.mark.parametrize("action", ["set_cel", "move_cel"])
@pytest.mark.parametrize("scope", ["frame", "shared"])
def test_linked_scope(tmp_path, action, scope):
    root = tmp_path / "p"
    create(root, width=8, height=8)
    ops.execute(
        "set_pixel", root, {"layer": "L1", "frame": 0, "x": 0, "y": 0, "color": 1}, preview="none"
    )
    ops.execute("add_frame", root, {"cels": "link", "copy_from": 0}, preview="none")
    args = {
        "layer": "L1",
        "frame": 1,
        **(
            {"x": 2, "linked": "unlink" if scope == "frame" else "all"}
            if action == "set_cel"
            else {"dx": 2, "scope": scope}
        ),
    }
    ops.execute(action, root, args, preview="none")
    from cybersprite.core.references import cel_at, cel_owner

    layer = canonical.load_project(root).layers[0]
    assert cel_owner(layer, cel_at(layer, 0)).x == (0 if scope == "frame" else 2)
    assert cel_owner(layer, cel_at(layer, 1)).x == 2


def test_linked_default_error(tmp_path):
    root = tmp_path / "p"
    create(root, width=8, height=8)
    ops.execute(
        "set_pixel", root, {"layer": "L1", "frame": 0, "x": 0, "y": 0, "color": 1}, preview="none"
    )
    ops.execute("add_frame", root, {"cels": "link", "copy_from": 0}, preview="none")
    with pytest.raises(CyberSpriteError) as error:
        ops.execute("set_cel", root, {"layer": "L1", "frame": 0, "x": 2}, preview="none")
    assert error.value.code == "E_LINKED_CEL"
    assert error.value.details["linked_frames"] == [0, 1]


def test_cli_and_registry(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["new", str(tmp_path / "p"), "--platform", "nds/sprite-80"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["result"]["summary"]["width"] == 80
    result = runner.invoke(cli, ["platforms", "show", "dmg/sprite-16", "--guide"])
    assert result.exit_code == 0, result.output
    assert "silhouette-first" in json.loads(result.output)["result"]["guide"]
    result = ops.execute("get_info", tmp_path / "p", {"include": ["platform", "summary"]})
    assert result["result"]["summary"]["platform"]["id"] == "nds/sprite-80"
    for name in [
        "set_platform",
        "list_platforms",
        "conform_palette",
        "set_frame_ticks",
        "move_cel",
    ]:
        assert ops.registry().get(name).describe()["name"] == name


def test_platform_defaults_tiles_preview_export(tmp_path):
    root = tmp_path / "p"
    create(root, platform="nds/sprite-80")
    result = ops.execute("add_tileset", root, {"name": "Tiles"}, preview="none")
    assert result["defaults_from_platform"] == ["system.tile.h", "system.tile.w"]
    assert canonical.load_project(root).tilesets[0].tile_w == 8
    result = ops.execute("render_preview", root, {"inline": False})
    assert result["result"]["scale"] == 6
    assert result["defaults_from_platform"] == ["defaults.preview.scale"]
    result = ops.execute("render_preview", root, {"scale": 2, "inline": False})
    assert result["result"]["scale"] == 2
    assert "defaults_from_platform" not in result
    ops.execute(
        "set_pixel", root, {"layer": "L1", "frame": 0, "x": 0, "y": 0, "color": 1}, preview="none"
    )
    from cybersprite.formats.common import export_policy

    with export_policy(tmp_path):
        result = ops.execute("export_image", root, {"out": str(tmp_path / "out.png")})
    assert result["result"]["verified"]
    assert result["defaults_from_platform"] == ["defaults.export.scale"]


def test_quantize_rounds_before_locking_only():
    from cybersprite.pipeline.quantize import quantize

    image = np.array([[[128, 128, 128, 255]]], dtype=np.uint8)
    p = resolve("nds/sprite-80")
    indices, palette, _ = quantize([image], mode="exact", platform_color=p.system.color)
    assert palette == [(0, 0, 0, 0), (123, 132, 132, 255)]
    assert indices[0].tolist() == [[1]]
    # Existing locked entries are never rewritten as a side effect of import.
    _, palette, _ = quantize(
        [image],
        mode="project",
        project_palette=[(0, 0, 0, 0), (128, 128, 128, 255)],
        platform_color=p.system.color,
    )
    assert palette[1] == (128, 128, 128, 255)


def test_import_uses_platform_defaults_once(tmp_path):
    from cybersprite.formats.png import encode_png

    root = tmp_path / "p"
    platform = {
        "asset": {"canvas": {"w": 2, "h": 2}},
        "system": {"color": {"bits": {"r": 5, "g": 5, "b": 5}}},
        "defaults": {"pipeline": {"preset": "exact", "overrides": {"palette.max_colors": 1}}},
    }
    create(root, platform=platform, palette=["#00000000"])
    image = tmp_path / "source.png"
    image.write_bytes(encode_png(np.full((2, 2, 4), 128, dtype=np.uint8)))
    arguments = {
        "files": str(image),
        "provenance": {"license": "unknown"},
        "on_gate_fail": "accept",
    }
    result = ops.execute(
        "import_image", root, arguments, preview="none", idempotency_key="platform-import"
    )
    assert result["defaults_from_platform"] == [
        "defaults.pipeline.overrides",
        "defaults.pipeline.preset",
    ]
    assert canonical.load_project(root).palette.colors[1] == "#7b8484ff"
    ops.execute(
        "set_platform",
        root,
        {"platform": {"defaults": {"pipeline": {"overrides": {"bad_section": 1}}}}},
        preview="none",
    )
    before = (root / "project.json").read_bytes()
    replay = ops.execute(
        "import_image", root, arguments, preview="none", idempotency_key="platform-import"
    )
    assert replay["replayed"]
    assert replay["defaults_from_platform"] == result["defaults_from_platform"]
    assert (root / "project.json").read_bytes() == before


def test_platform_aseprite_roundtrip(tmp_path):
    from cybersprite.formats.aseprite_io import decode_aseprite, encode_aseprite

    root = tmp_path / "p"
    create(root, platform="nds/sprite-80")
    p = canonical.load_project(root)
    restored, _ = decode_aseprite(encode_aseprite(p))
    assert restored.platform == p.platform


def test_platform_mcp_contract(tmp_path):
    import asyncio

    pytest.importorskip("mcp.server")
    from jsonschema import Draft202012Validator
    from mcp import Client

    from cybersprite.mcp.server import create_server

    async def run():
        async with Client(create_server(root=tmp_path)) as client:
            tools = {t.name: t for t in (await client.list_tools()).tools}

            async def call(name, **args):
                response = await client.call_tool(name, {"project": "nds.csprite", **args})
                result = response.structured_content
                Draft202012Validator(tools[name].output_schema).validate(result)
                assert result["ok"], result
                return result

            await call("list_platforms", id="nds/sprite-80", guide=True)
            await call("new_project", platform="nds/sprite-80")
            await call("set_pixel", layer="L1", frame=0, x=1, y=1, color=1, preview="none")
            result = await call("validate")
            assert result["result"]["metrics"]["platform"]["id"] == "nds/sprite-80"
            await call("conform_palette", preview="none")
            result = await call("export_image", out="out.png")
            assert result["result"]["validation_ok"] and result["result"]["verified"]

    asyncio.run(run())
