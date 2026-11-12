"""Every SPEC §9.3 command has a JSON and exit-code contract, including lazy hooks."""

import json
import os
import re
import subprocess
import sys
import types
from pathlib import Path

import pytest
from click.testing import CliRunner
from pydantic import create_model

from cybersprite.cli import cli
from cybersprite.core.errors import EXIT_CODES, CyberSpriteError
from cybersprite.core.models import Model
from cybersprite.core.registry import Op
from cybersprite.ops import registry

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def runner(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path / "settings"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "settings"))
    return CliRunner()


def invoke(runner, *args, code=0, input=None):
    result = runner.invoke(cli, list(map(str, args)), input=input)
    assert result.exit_code == code, (result.output, result.exception)
    assert result.stderr == ""
    output = json.loads(result.stdout)
    assert set(output) >= {"ok", "op", "project", "revision"}
    if output["ok"]:
        assert "result" in output and isinstance(output["warnings"], list)
        definition = next((op for op in registry().all() if op.name == output["op"]), None)
        if definition is not None:
            definition.result.model_validate(output["result"])
    else:
        assert set(output["error"]) >= {"code", "message", "hint", "details"}
        assert output["error"]["message"] and output["error"]["hint"]
    return output


@pytest.fixture
def project(runner):
    invoke(runner, "new", "sample", "--size", "16x16", "--palette", "gray-4")
    invoke(
        runner,
        "-p",
        "sample",
        "op",
        "rect",
        "layer=L1",
        "frame=0",
        "x=1",
        "y=1",
        "w=8",
        "h=8",
        "color=1",
    )
    return Path("sample")


COMMAND_CASES = [
    (["new", "second", "--size", "4x4"], ["new", "sample", "--size", "4x4"], 3),
    (["info", "--include", "layers,tags,slices,palette"], ["info", "--include", "bad"], 2),
    (
        ["pixels", "--layer", "L1", "--as", "sym", "--rect", "0,0,8,8"],
        ["pixels", "--layer", "missing"],
        3,
    ),
    (["palette", "show"], ["palette", "show", "--bogus"], 2),
    (["palette", "presets"], ["palette", "presets", "--bogus"], 2),
    (["validate", "--frames", "0", "--rules", "Q-PAL-01"], ["validate", "--frames", "99"], 3),
    (
        ["render", "--frame", "0", "--out", "render.png", "--indexed"],
        ["render", "--frame", "99", "--out", "bad.png"],
        3,
    ),
    (
        ["preview", "--frame", "0", "--onion", "0,0", "--out", "preview.png"],
        ["preview", "--frame", "99"],
        3,
    ),
    (
        ["diff", "--from", "0", "--to", "1", "--frame", "0", "--out", "diff.png"],
        ["diff", "--from", "999"],
        3,
    ),
    (["op", "set_pixel", "layer=L1", "frame=0", "x=2", "y=2", "color=1"], ["op", "unknown"], 2),
    (["apply", "-"], ["apply", "missing.json"], 4),
    (["undo"], ["undo", "--steps", "0"], 2),
    (["history"], ["history", "--limit", "0"], 2),
    (["import", "palette", "gray-8", "--append"], ["import", "palette", "missing-preset"], 6),
    (["ops", "list"], ["ops", "list", "--unknown"], 2),
    (["ops", "describe", "line"], ["ops", "describe", "missing"], 2),
    (["schema", "op", "line"], ["schema", "op", "unknown"], 2),
    (["plugins", "list"], ["plugins", "list", "--unknown"], 2),
    (["doctor"], ["doctor", "--unknown"], 2),
]


@pytest.mark.parametrize(
    ("success", "failure", "code"),
    COMMAND_CASES,
    ids=[" ".join(row[0][:2]) for row in COMMAND_CASES],
)
def test_existing_command_contracts(runner, project, success, failure, code):
    transaction = (
        '{"ops":[{"op":"set_pixel","args":{"layer":"L1","frame":0,"x":3,"y":3,"color":1}}]}'
    )
    assert invoke(runner, "-p", project, *success, input=transaction)["ok"]
    assert not invoke(runner, "-p", project, *failure, code=code)["ok"]


def test_redo_contract(runner, project):
    assert invoke(runner, "-p", project, "redo", code=3)["error"]["code"] == "E_NOTHING_TO_REDO"
    invoke(runner, "-p", project, "undo")
    assert invoke(runner, "-p", project, "redo")["revision"]["after"] == 3


ROUTES = [
    ("export image", "export_image", "M5", None),
    ("export sheet", "export_sheet", "M5", None),
    ("export anim", "export_animation", "M5", None),
    ("export aseprite", "export_aseprite", "M5", None),
    ("export tileset", "export_tileset", "M5", None),
    ("export palette", "export_palette", "M5", None),
    ("import image", "import_image", "M6", "files"),
    ("import aseprite", "import_aseprite", "M5", "file"),
    ("source list", "list_sources", "M6", None),
    ("source show", "get_source", "M6", "id"),
]


def register_fake(monkeypatch, name, fields=None):
    args = create_model(name + "Args", __base__=Model, **(fields or {}))
    result = create_model(name + "Result", __base__=Model, received=(dict, ...))
    op = Op(name, args, lambda ctx, parsed: {"received": parsed.model_dump()}, result, "query", "R")
    monkeypatch.setitem(registry()._ops, name, op)
    return op


@pytest.mark.parametrize(("command", "op", "milestone", "positional"), ROUTES)
def test_registered_command_contracts_and_schema_extension(
    runner, project, monkeypatch, command, op, milestone, positional
):
    definition = registry().get(op)
    from cybersprite.cli.generated import schema_options

    options = schema_options(definition, skip=(positional,) if positional else ())
    assert {option.name for option in options} == set(definition.args.model_fields) - (
        {positional} if positional else set()
    )
    help_result = runner.invoke(cli, [*command.split(), "--help"])
    assert help_result.exit_code == 0
    assert " ".join(definition.description.split()) in " ".join(help_result.output.split())
    fields = {
        "split_tags": (bool, False),
        "item_name": (str, "default"),
        "frames": (list[int] | str, "all"),
    }
    if positional:
        fields[positional] = (list[str] if positional == "files" else str, ...)
    register_fake(monkeypatch, op, fields)
    args = command.split() + (
        ["one", "two"] if positional == "files" else ["one"] if positional else []
    )
    if op == "import_aseprite":
        args += ["--out", str(project)]
    output = invoke(
        runner, "-p", project, *args, "--split-tags", "--item-name", "日本語", "--frames", "0,1"
    )
    received = output["result"]["received"]
    assert received["split_tags"] and received["item_name"] == "日本語"
    assert received["frames"] == [0, 1]
    assert not invoke(runner, "-p", project, *args, "--bogus", code=2)["ok"]


@pytest.mark.parametrize(
    ("command", "module", "function", "milestone"),
    [
        (["mcp", "serve"], "cybersprite.mcp.server", "serve", "M4"),
        (["gui"], "cybersprite.server", "serve", "M8"),
        (["gen", "accept-license", "model"], "cybersprite.generate", "accept_license", "M9"),
        (["convert", "in.png", "out.png"], "cybersprite.pipeline.cli_api", "convert", "M6"),
        (
            ["pipeline", "detect-grid", "in.png"],
            "cybersprite.pipeline.cli_api",
            "detect_grid",
            "M6",
        ),
    ],
)
def test_lazy_module_command_contracts(runner, monkeypatch, command, module, function, milestone):
    monkeypatch.setitem(sys.modules, module, types.ModuleType(module))
    output = invoke(runner, *command, code=6)
    assert output["error"]["code"] == "E_UNSUPPORTED"
    assert milestone in output["error"]["hint"]
    if module == "cybersprite.mcp.server":
        assert "cybersprite[mcp]" in output["error"]["hint"]
    captured = {}

    def callback(*args, **kwargs):
        captured.update(kwargs)
        return {"hook_called": True}

    setattr(sys.modules[module], function, callback)
    assert invoke(runner, *command)["result"]["hook_called"]
    assert not invoke(runner, *command, "--unknown", code=2)["ok"]


def test_mcp_hook_passes_exact_options_and_missing_extra(runner, monkeypatch):
    module = types.ModuleType("cybersprite.mcp.server")
    captured = {}

    def serve(**options):
        captured.update(options)
        return {"stopped": True}

    module.serve = serve
    monkeypatch.setitem(sys.modules, module.__name__, module)
    invoke(
        runner,
        "mcp",
        "serve",
        "--root",
        ".",
        "--allow-dir",
        "one",
        "--allow-dir",
        "two",
        "--transport",
        "http",
        "--port",
        "1234",
        "--profile",
        "minimal",
        "--enable-generation",
        "--allow-plugin-op",
        "one",
        "--allow-plugin-op",
        "two",
        "--read-only",
    )
    assert captured == {
        "root": Path("."),
        "allow_dir": [Path("one"), Path("two")],
        "transport": "http",
        "port": 1234,
        "profile": "minimal",
        "enable_generation": True,
        "allow_plugin_op": ["one", "two"],
        "read_only": True,
    }

    def missing_extra(**kwargs):
        raise ModuleNotFoundError("No module named mcp")

    module.serve = missing_extra
    output = invoke(runner, "mcp", "serve", code=6)
    assert "cybersprite[mcp]" in output["error"]["hint"]


def test_error_table_covers_every_appendix_code():
    appendix = (
        (ROOT / "docs/SPEC.md").read_text("utf-8").split("## 付録 C.")[1].split("## 付録 D.")[0]
    )
    codes = set(re.findall(r"`(E_[A-Z_]+)`", appendix))
    assert set(EXIT_CODES) == codes
    expected = {
        1: "E_VALIDATION_FAILED",
        2: "E_INVALID_ARGS E_UNKNOWN_OP",
        3: "E_PROJECT_NOT_FOUND E_EXISTS E_LAYER_NOT_FOUND E_CEL_NOT_FOUND E_TAG_NOT_FOUND "
        "E_SLICE_NOT_FOUND E_TILESET_NOT_FOUND E_SOURCE_NOT_FOUND E_FRAME_OUT_OF_RANGE "
        "E_AMBIGUOUS_REF E_WRONG_LAYER_TYPE E_LAYER_LOCKED E_PALETTE_FROZEN "
        "E_INDEX_OUT_OF_RANGE E_COLOR_NOT_IN_PALETTE E_OUT_OF_CANVAS E_REVISION_CONFLICT "
        "E_NOTHING_TO_UNDO E_NOTHING_TO_REDO E_HISTORY_UNAVAILABLE E_PLUGIN "
        "E_BACKEND_UNAVAILABLE E_LICENSE_NOT_ACCEPTED E_GENERATION_FAILED",
        4: "E_IO E_LOCKED E_PATH_NOT_ALLOWED E_INVALID_PROJECT E_TIMEOUT",
        5: "E_INTERNAL E_INVARIANT",
        6: "E_LIMIT_EXCEEDED E_UNSUPPORTED E_NEEDS_QUANTIZE E_NOT_PALETTE_CLOSED E_SCHEMA_TOO_NEW",
    }
    assert EXIT_CODES == {
        code: value for value, names in expected.items() for code in names.split()
    }
    for code in codes:
        assert CyberSpriteError(code, "message", "hint").exit_code == EXIT_CODES[code]
    assert {code for code, value in EXIT_CODES.items() if value == 1} == {"E_VALIDATION_FAILED"}
    assert {code for code, value in EXIT_CODES.items() if value == 2} == {
        "E_INVALID_ARGS",
        "E_UNKNOWN_OP",
    }
    assert CyberSpriteError("E_FUTURE_BUG", "", "").exit_code == 5


@pytest.mark.parametrize(("code", "exit_code"), sorted(EXIT_CODES.items()))
def test_every_public_error_has_cli_envelope(runner, project, monkeypatch, code, exit_code):
    args = create_model("ErrorProbeArgs", __base__=Model)

    def fail(context, parsed):
        raise CyberSpriteError(code, "Test failure.", "Retry with corrected inputs.")

    op = Op("m3_error_probe", args, fail, Model, "query", "R")
    monkeypatch.setitem(registry()._ops, op.name, op)
    output = invoke(runner, "-p", project, "op", op.name, code=exit_code)
    assert output["error"]["code"] == code
    assert output["revision"] == {"before": 1, "after": 1}


@pytest.mark.parametrize("option", ["--version", "--help"])
def test_fast_start_does_not_import_heavy_modules(option):
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from cybersprite.cli import cli; "
            f"cli.main([{option!r}], standalone_mode=False); "
            "assert not {'numpy','pydantic','PIL','aseprite'} & sys.modules.keys()",
        ],
        capture_output=True,
        encoding="utf-8",
    )
    assert probe.returncode == 0, probe.stderr


def test_real_uv_stdout_utf8_and_errors(tmp_path):
    env = {**os.environ, "PYTHONIOENCODING": "ascii"}
    args = ["uv", "run", "cybersprite"]
    project = tmp_path / "日本語.csprite"
    good = subprocess.run(
        [*args, "new", str(project), "--size", "2x2", "--name", "日本語"],
        cwd=ROOT,
        env=env,
        capture_output=True,
    )
    assert good.returncode == 0 and good.stderr == b""
    assert json.loads(good.stdout.decode("utf-8"))["result"]["summary"]["name"] == "日本語"
    bad = subprocess.run(
        [*args, "-p", str(project), "op", "unknown"], cwd=ROOT, env=env, capture_output=True
    )
    assert bad.returncode == 2 and bad.stderr == b""
    assert json.loads(bad.stdout.decode("utf-8"))["error"]["code"] == "E_UNKNOWN_OP"


def test_external_input_adapter_contract(runner, monkeypatch):
    from cybersprite.core.projects import new_project
    from cybersprite.formats import input_adapter
    from cybersprite.formats.png import decode_png, encode_png

    original = new_project(width=2, height=2)
    from cybersprite.core.render import render

    Path("in.png").write_bytes(encode_png(render(original, 0)))
    captured = []
    real_loader = input_adapter.load_external

    def load_external(path, options):
        captured.append((path, options))
        return real_loader(path, options)

    monkeypatch.setattr(input_adapter, "load_external", load_external)
    output = invoke(runner, "export", "image", "--input", "in.png", "--out", "out.png")
    assert output["op"] == "export_image"
    assert output["result"]["verified"] and output["result"]["validation_ok"]
    assert captured == [(Path("in.png"), {"out": "out.png"})]
    assert decode_png(Path("out.png").read_bytes()).pixels.shape == (2, 2)
    assert (
        invoke(runner, "export", "image", "--input", "missing.png", "--out", "bad.png", code=4)[
            "error"
        ]["code"]
        == "E_IO"
    )
    assert not list(Path.cwd().rglob("project.json"))
    assert not (Path.cwd() / "source").exists()


def test_schema_variants_and_sheet_hook(runner, monkeypatch):
    for kind in ("project", "sources", "all"):
        assert invoke(runner, "schema", kind)["ok"]
    invoke(runner, "schema", "op", "line", "--out", "schemas")
    assert Path("schemas/op.schema.json").is_file()
    assert (
        invoke(runner, "schema", "project", "unexpected", code=2)["error"]["code"]
        == "E_INVALID_ARGS"
    )
    module = types.ModuleType("cybersprite.formats.sheet")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    assert invoke(runner, "schema", "sheet", code=6)["error"]["code"] == "E_UNSUPPORTED"
    module.sheet_schema = lambda: {"type": "object"}
    assert invoke(runner, "schema", "sheet")["result"]["sheet"] == {"type": "object"}


def test_output_copy_and_project_safety(runner, project):
    initial = (project / "project.json").read_bytes()
    output = invoke(runner, "-p", project, "preview", "--out", "copied.png")
    assert output["result"]["paths"] == ["copied.png"]
    from cybersprite.formats.png import decode_png

    assert decode_png(Path("copied.png").read_bytes()).pixels.size
    assert (
        invoke(runner, "-p", project, "preview", "--out", project / "project.json", code=2)[
            "error"
        ]["code"]
        == "E_INVALID_ARGS"
    )
    assert (
        invoke(runner, "-p", project, "diff", "--out", project / "project.json", code=2)["error"][
            "code"
        ]
        == "E_INVALID_ARGS"
    )
    assert (project / "project.json").read_bytes() == initial
    os.link(project / "project.json", "linked.png")
    for command in ("render", "preview", "diff"):
        output = invoke(runner, "-p", project, command, "--out", "linked.png", code=2)
        assert output["error"]["code"] == "E_INVALID_ARGS"
    assert (project / "project.json").read_bytes() == initial


def test_explicit_transaction_flags_override_file_options(runner, project):
    initial = (project / "project.json").read_bytes()
    transaction = {
        "dry_run": False,
        "preview": "path",
        "ops": [
            {"op": "set_pixel", "args": {"layer": "L1", "frame": 0, "x": 3, "y": 3, "color": 2}},
        ],
    }
    Path("apply.json").write_text(json.dumps(transaction), "utf-8")
    output = invoke(runner, "-p", project, "apply", "apply.json", "--dry-run", "--preview", "none")
    assert output["dry_run"] and output["preview"]["paths"] == []
    assert (project / "project.json").read_bytes() == initial


def test_apply_refuses_interactive_stdin(runner, monkeypatch):
    monkeypatch.setattr(
        "click.get_text_stream",
        lambda *args, **kwargs: types.SimpleNamespace(
            isatty=lambda: True,
        ),
    )
    output = invoke(runner, "apply", code=2)
    assert "interactive" in output["error"]["message"]


def test_actor_project_placement_text_and_stdin(runner, project, monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_ACTOR", "from-env")
    invoke(runner, "op", "set_pixel", "-p", project, "layer=L1", "frame=0", "x=2", "y=2", "color=2")
    entries = invoke(runner, "history", "-p", project)["result"]["entries"]
    assert entries[0]["actor"] == "from-env"
    invoke(
        runner,
        "op",
        "set_pixel",
        "--actor",
        "override",
        "-p",
        project,
        "layer=L1",
        "frame=0",
        "x=2",
        "y=2",
        "color=3",
    )
    assert invoke(runner, "-p", project, "history")["result"]["entries"][0]["actor"] == "override"
    invoke(
        runner,
        "-p",
        project,
        "apply",
        input='{"ops":[{"op":"set_pixel","args":{"layer":"L1","frame":0,"x":4,"y":4,"color":1}}]}',
    )
    result = runner.invoke(cli, ["--format", "text", "-p", str(project), "info"])
    assert result.exit_code == 0 and result.stdout.startswith("get_info: ")
    assert len(result.stdout) < 300
    result = runner.invoke(cli, ["--format", "text", "-p", str(project), "op", "unknown"])
    assert result.exit_code == 2 and result.stdout.startswith("E_UNKNOWN_OP:")


def test_progress_stdout_is_redirected_and_quiet(runner, monkeypatch):
    module = types.ModuleType("cybersprite.pipeline.cli_api")

    def convert(**kwargs):
        print("converting 日本語")
        return {"converted": True}

    module.convert = convert
    monkeypatch.setitem(sys.modules, module.__name__, module)
    result = runner.invoke(cli, ["convert", "in.png", "out.png"])
    assert result.exit_code == 0 and json.loads(result.stdout)["result"]["converted"]
    assert result.stderr == "converting 日本語\n"
    invoke(runner, "--quiet", "convert", "in.png", "out.png")


def test_ingest_command_gets_transaction_options(runner, monkeypatch):
    definition = register_fake(monkeypatch, "import_image", {"files": (list[str], ...)})
    from dataclasses import replace

    monkeypatch.setitem(registry()._ops, "import_image", replace(definition, kind="ingest"))
    captured = {}

    def run(state, name, args, **options):
        from cybersprite.cli import _emit

        captured.update(name=name, args=args, options=options)
        _emit(state, name, {"received": args})

    monkeypatch.setattr("cybersprite.cli._run", run)
    invoke(runner, "import", "image", "one.png", "--dry-run", "--expect-revision", "2")
    assert captured == {
        "name": "import_image",
        "args": {"files": ["one.png"]},
        "options": {"dry_run": True, "expect_revision": 2},
    }


def test_import_and_convert_pipeline_shortcuts(runner, project, monkeypatch):
    sheet = create_model("SheetArgs", __base__=Model, cell_w=(int, ...), cell_h=(int, ...))
    register_fake(
        monkeypatch,
        "import_image",
        {
            "files": (list[str], ...),
            "sheet": (sheet | None, None),
            "pipeline": (dict | None, None),
        },
    )
    options = [
        "--sheet-cell",
        "8x4",
        "--pipeline",
        '{"dither":{"strength":7}}',
        "--dither",
        "bayer4",
    ]
    output = invoke(runner, "-p", project, "import", "image", "in.png", *options)
    assert output["result"]["received"]["sheet"] == {"cell_w": 8, "cell_h": 4}
    assert output["result"]["received"]["pipeline"] == {
        "dither": {"strength": 7, "type": "bayer4"},
    }
    module = types.ModuleType("cybersprite.pipeline.cli_api")
    captured = {}

    def convert(**options):
        captured.update(options)
        return {"converted": True}

    module.convert = convert
    monkeypatch.setitem(sys.modules, module.__name__, module)
    invoke(runner, "convert", "in.png", "out.png", *options)
    assert captured["sheet"] == {"cell_w": 8, "cell_h": 4}
    assert captured["pipeline"] == {"dither": {"strength": 7, "type": "bayer4"}}


@pytest.mark.parametrize("pipeline", ["[1]", '{"dither":"none"}'])
def test_pipeline_shortcuts_reject_wrong_container_types(runner, pipeline):
    output = invoke(
        runner, "convert", "in.png", "out.png", "--pipeline", pipeline, "--dither", "bayer4", code=2
    )
    assert output["error"]["code"] == "E_INVALID_ARGS"
