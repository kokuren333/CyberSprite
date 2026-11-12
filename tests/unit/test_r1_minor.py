"""R1-M regression vectors and seeded preservation properties."""

import json
import random
from copy import deepcopy

import numpy as np
import pytest
from click.testing import CliRunner
from PIL import Image

from cybersprite import ops
from cybersprite.cli import cli
from cybersprite.core.canonical import dumps_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.models import ImageCel, ImageLayer
from cybersprite.core.pixels import pixels_to_rows
from cybersprite.core.projects import new_project
from cybersprite.core.registry import OpContext
from cybersprite.core.render import render
from cybersprite.formats.common import export_policy
from cybersprite.formats.export import export_animation, export_image, export_sheet
from cybersprite.formats.export_args import AnimationArgs, ImageArgs, SheetArgs
from cybersprite.formats.sheet_models import sheet_schema
from tools import update_goldens
from tools.m5_cases import animated_project


@pytest.mark.parametrize("seed", range(24))
@pytest.mark.parametrize("name", ["flatten", "merge_layers"])
def test_seeded_composite_preservation(tmp_path, seed, name):
    rng = random.Random(1701 + seed)
    p = new_project(width=5, height=4, frames=2, palette=["#ff00ff00", "#102030ff", "#405060ff"])
    p.layers = []
    for i in range(3):
        background = i == 0 and bool(seed % 2)
        layer = ImageLayer(
            id=f"L{i + 1}",
            name=f"Layer {i}",
            background=background,
            visible=rng.choice([True, True, False]),
            opacity=255 if background else rng.choice([255, 255, 127]),
        )
        layer.cels = [
            ImageCel(
                frame=f,
                x=0,
                y=0,
                w=5,
                h=4,
                pixels=pixels_to_rows(
                    np.array(
                        [[rng.randrange(3) for _ in range(5)] for _ in range(4)], dtype=np.uint8
                    )
                ),
            )
            for f in range(2)
        ]
        p.layers.append(layer)
    p.id_counters.layer = 3
    include_hidden = name == "flatten" and seed % 3 == 0
    before = [render(p, f, {"include_hidden": include_hidden}) for f in range(2)]
    original = deepcopy(p)
    op = ops.registry().get(name)
    args = (
        {"visible_only": not include_hidden}
        if name == "flatten"
        else {"layers": ["L1", "L2", "L3"]}
    )
    try:
        op.apply(OpContext(p, tmp_path), op.parse(args))
    except CyberSpriteError as error:
        assert error.code == "E_NOT_PALETTE_CLOSED"
        assert p == original
    else:
        for f in range(2):
            np.testing.assert_array_equal(render(p, f), before[f])
        assert p.layers[0].background == original.layers[0].background


def test_background_flatten_regression(tmp_path):
    root = tmp_path / "p"
    ops.execute(
        "new_project",
        root,
        {
            "width": 3,
            "height": 3,
            "palette": ["#ff00ff00", "#102030ff", "#405060ff"],
            "background": 1,
        },
    )
    ops.execute(
        "erase",
        root,
        {"layer": "L2", "frame": 0, "region": {"type": "rect", "x": 0, "y": 0, "w": 2, "h": 2}},
        preview="none",
    )
    from cybersprite.core.canonical import load_project

    before = render(load_project(root))
    ops.execute("flatten", root, {}, preview="none")
    after = load_project(root)
    assert after.layers[0].background
    np.testing.assert_array_equal(render(after), before)


def test_warnings_validation_and_outside_details(tmp_path):
    root = tmp_path / "p"
    ops.execute("new_project", root, {"width": 2, "height": 2})
    result = ops.execute(
        "line",
        root,
        {"layer": "L1", "frame": 0, "x0": -1, "y0": 0, "x1": 1, "y1": 0, "color": 1},
        preview="none",
    )
    assert result["warnings"] == [{"code": "W_CLIPPED", "clipped_pixels": 1}]
    with pytest.raises(CyberSpriteError) as caught:
        ops.execute(
            "fill", root, {"layer": "L1", "frame": 0, "x": -1, "y": 0, "color": 1}, preview="none"
        )
    assert caught.value.details == {"x": -1, "y": 0, "width": 2, "height": 2}
    with pytest.raises(CyberSpriteError) as caught:
        ops.execute(
            "set_validation",
            root,
            {"settings": {"severity": {"Q-NOT-A-RULE": "off"}}},
            preview="none",
        )
    assert caught.value.code == "E_INVALID_ARGS"
    assert "Q-PIX-01" in caught.value.details["candidates"]
    ops.execute("set_validation", root, {"settings": {"palette_max": 1}}, preview="none")
    with export_policy(tmp_path):
        with pytest.raises(CyberSpriteError) as caught:
            ops.execute("export_image", root, {"out": "bad.png"})
        assert "validate" in caught.value.hint and "allow_invalid" in caught.value.hint
        result = ops.execute("export_image", root, {"out": "forced.png", "allow_invalid": True})
        assert result["warnings"] == result["result"]["warnings"]
        assert any(w["code"] == "W_EXPORT_INVALID" for w in result["warnings"])


@pytest.mark.independent_decoder
@pytest.mark.parametrize(
    "kind,mode",
    [
        ("png", "indexed"),
        ("png", "rgba"),
        ("gif", "indexed"),
        ("apng", "indexed"),
        ("apng", "rgba"),
        ("sheet", "indexed"),
        ("sheet", "rgba"),
    ],
)
def test_all_builtin_rasters_with_independent_decoder(tmp_path, kind, mode):
    p = animated_project()
    expected = [render(p, f) for f in range(3)]
    with export_policy(tmp_path):
        if kind == "png":
            result = export_image(
                p,
                ImageArgs(out="frame-{frame}.png", frames="all", color_mode=mode),
                root=tmp_path / "project",
            )
        elif kind == "sheet":
            result = export_sheet(
                p,
                SheetArgs(
                    out="sheet.png", data_out="sheet.json", layout="horizontal", color_mode=mode
                ),
                root=tmp_path / "project",
            )
        else:
            result = export_animation(
                p,
                AnimationArgs(
                    out=f"animation.{kind}", format=kind, frames="all", loop=1, color_mode=mode
                ),
                root=tmp_path / "project",
            )
    assert result["verified"]
    if kind == "sheet":
        from jsonschema import Draft202012Validator

        data = json.loads((tmp_path / "sheet.json").read_bytes())
        Draft202012Validator(sheet_schema()).validate(data)
        with Image.open(tmp_path / "sheet.png") as image:
            pixels = np.array(image.convert("RGBA"))
        for item in data["items"]:
            r = item["rect"]
            np.testing.assert_array_equal(
                pixels[r["y"] : r["y"] + r["h"], r["x"] : r["x"] + r["w"]], expected[item["frame"]]
            )
    elif kind == "png":
        for frame, file in enumerate(result["files"]):
            with Image.open(tmp_path / file["path"]) as image:
                np.testing.assert_array_equal(np.array(image.convert("RGBA")), expected[frame])
    else:
        with Image.open(tmp_path / f"animation.{kind}") as image:
            assert image.n_frames == len(expected)
            for frame, pixels in enumerate(expected):
                image.seek(frame)
                np.testing.assert_array_equal(np.array(image.convert("RGBA")), pixels)


def test_cli_repeated_include_and_sheet_schema(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["new", "p", "--size", "2x2"]).exit_code == 0
    response = runner.invoke(
        cli, ["-p", "p", "info", "--include", "layers", "--include", "frames,layers"]
    )
    assert response.exit_code == 0, response.output
    assert set(json.loads(response.output)["result"]) == {"layers", "frames"}
    response = runner.invoke(cli, ["schema", "sheet"])
    assert response.exit_code == 0
    assert json.loads(response.output)["result"]["sheet"] == sheet_schema()


def test_first_import_reuses_initial_layer(tmp_path):
    from pathlib import Path

    from cybersprite.core.canonical import load_project

    source = Path(__file__).resolve().parents[1] / "pipeline/corpus/originals/hero_16x16.png"
    root = tmp_path / "new.csprite"
    result = ops.execute(
        "import_image",
        root,
        {"files": str(source), "preset": "exact", "provenance": {"license": "unknown"}},
        preview="none",
    )
    assert result["result"]["accepted"]
    p = load_project(root)
    assert len(p.layers) == 1 and p.layers[0].cels
    assert p.layers[0].id == result["result"]["placed"]["layer"] == "L1"


@pytest.mark.parametrize("arguments", [[], ["--all"], ["--confirm-all"], ["--case", "not-a-case"]])
def test_golden_updater_requires_explicit_valid_selection(monkeypatch, arguments):
    monkeypatch.setattr("sys.argv", ["update_goldens.py", *arguments])
    monkeypatch.setattr(update_goldens, "update", lambda case: pytest.fail("Must not write"))
    with pytest.raises(SystemExit) as caught:
        update_goldens.main()
    assert caught.value.code == 2


def test_golden_updater_prints_textual_diff(tmp_path, capsys):
    case = tmp_path / "one"
    (case / "expected").mkdir(parents=True)
    p = new_project(width=1, height=1)
    (case / "project.json").write_bytes(dumps_project(p))
    (case / "case.json").write_text('{"canonical":true}', encoding="utf-8")
    (case / "expected/canonical.project.json").write_bytes(b"{}\n")
    assert update_goldens.update(case) == 1
    output = capsys.readouterr().out
    assert "--- one/canonical.project.json (before)" in output
    assert "+" in output and "bytes" in output


def test_documented_warning_codes_and_golden_case_count():
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    spec = (root / "docs/SPEC.md").read_text(encoding="utf-8")
    codes = set()
    for path in (root / "src/cybersprite").rglob("*.py"):
        codes.update(re.findall(r'["\'](W_[A-Z_]+)["\']', path.read_text(encoding="utf-8")))
    assert not {code for code in codes if f"`{code}`" not in spec}
    cases = len(list((root / "tests/golden").glob("*/case.json")))
    assert f"{cases} " in (root / "tests/golden/README.md").read_text(encoding="utf-8")
