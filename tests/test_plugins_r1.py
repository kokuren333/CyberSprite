"""R1-C contracts use original tiny plugins and fake distribution metadata only."""

from email.message import Message
from types import SimpleNamespace

import numpy as np
import pytest
from click.testing import CliRunner

from cybersprite import ops
from cybersprite.cli import cli
from cybersprite.config import UserConfig
from cybersprite.core import quality
from cybersprite.core.canonical import load_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.models import Model
from cybersprite.core.projects import create_project, new_project
from cybersprite.core.registry import EmptyResult, Op, Registry
from cybersprite.formats.common import export_policy
from cybersprite.formats.export_args import PluginExportArgs
from cybersprite.formats.plugin_export import export_plugin
from cybersprite.formats.png import decode_png, encode_png
from cybersprite.pipeline.runner import run_pipeline
from cybersprite.plugins import PluginManager, discover
from cybersprite.plugins.contracts import IndexedImage, PipelineStep, Validator
from cybersprite.plugins.validators import configure_validation


class Entry:
    def __init__(self, group, name, value, loaded, *, api=None, license="MIT"):
        self.group, self.name, self.value, self.loaded = group, name, value, loaded
        info = Message()
        info["Name"] = "test-distribution"
        info["License-Expression"] = license
        if api is not None:
            info["CyberSprite-Plugin-API"] = str(api)
        self.dist = SimpleNamespace(metadata=info, version="2.3.4")

    def load(self):
        self.loaded.append(self.name)
        return self.value


@pytest.fixture
def plugins(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setenv("CYBERSPRITE_CONFIG_DIR", str(config_dir))
    entries, loaded = [], []
    monkeypatch.setattr(
        "importlib.metadata.entry_points", lambda *, group: [e for e in entries if e.group == group]
    )
    monkeypatch.setattr(ops, "_registry", None)
    monkeypatch.setattr(quality, "plugin_rule_provider", lambda: ())

    def install(group, name, value, *, enabled=True, api=None):
        entries.append(Entry("cybersprite." + group, name, value, loaded, api=api))
        names = [e.name for e in entries] if enabled else []
        (config_dir / "config.toml").write_text(
            "[plugins]\nenabled = [" + ", ".join('"' + n + '"' for n in names) + "]\n",
            encoding="utf-8",
            newline="\n",
        )

    return install, entries, loaded


def factory(value, api=1):
    def make():
        return value

    make.plugin_api = api
    return make


def test_metadata_sorted_listing_never_imports(plugins):
    install, _, loaded = plugins
    install("ops", "z", object())
    install("palettes", "z", object())
    install("platforms", "a", object(), api=999)
    install("importers", "deferred", object())
    descriptors = discover()
    assert [(d.group, d.name, d.distribution) for d in descriptors] == sorted(
        (d.group, d.name, d.distribution) for d in descriptors
    )
    rows = PluginManager().listing()
    assert rows[0]["state"] == "incompatible"
    row = next(r for r in rows if r["name"] == "z")
    assert row["version"] == "2.3.4" and row["license"] == "MIT"
    assert row["groups"] == ["cybersprite.ops", "cybersprite.palettes"]
    result = CliRunner().invoke(cli, ["plugins", "list"])
    assert result.exit_code == 0, result.output
    assert '"version": "2.3.4"' in result.output and loaded == []


def test_api_rejected_before_factory_and_explicit_disable(plugins):
    install, _, loaded = plugins
    calls = []

    def bad():
        calls.append(True)

    bad.plugin_api = 999
    install("ops", "bad", bad)
    manager = PluginManager()
    with pytest.raises(CyberSpriteError, match="plugin_api must be 1"):
        manager.load("cybersprite.ops", "bad")
    assert loaded == ["bad"] and calls == []
    assert manager.listing()[0]["state"] == "incompatible"
    settings = UserConfig.model_validate({"plugins": {"enabled": ["bad"], "disabled": ["bad"]}})
    with pytest.raises(CyberSpriteError, match="not enabled"):
        PluginManager(settings).load("cybersprite.ops", "bad")
    assert loaded == ["bad"]


def test_metadata_api_rejection_and_license_classifier_fallback(plugins):
    install, entries, loaded = plugins
    install("exporters", "future", object(), api=999)
    info = entries[0].dist.metadata
    del info["License-Expression"]
    info["Classifier"] = "License :: OSI Approved :: MIT License"
    manager = PluginManager()
    assert "MIT License" in manager.listing()[0]["license"]
    with pytest.raises(CyberSpriteError, match="unsupported metadata"):
        manager.load("cybersprite.exporters", "future")
    assert loaded == []


def test_selected_ops_atomic_registration_cli_and_mcp(plugins, tmp_path):
    install, _, loaded = plugins
    op = Op("allowed_read", Model, lambda ctx, a: {}, EmptyResult, "query", "R")
    install("ops", "allowed", factory([op]))
    install("ops", "unrelated", factory([], api=999))
    from cybersprite.mcp.server import MCPService

    service = MCPService(root=tmp_path, allow_plugin_op=["allowed_read"])
    assert "allowed_read" in service.exposed and loaded == ["allowed"]
    assert ops.registry().get("allowed_read").provider == "allowed"
    create_project(tmp_path / "p", new_project(width=2, height=2))
    result = CliRunner().invoke(cli, ["-p", str(tmp_path / "p"), "op", "allowed_read"])
    assert result.exit_code == 0, result.output
    install(
        "ops",
        "broken",
        factory(
            [
                Op("broken_one", Model, lambda c, a: {}, EmptyResult),
                Op("broken_one", Model, lambda c, a: {}, EmptyResult),
            ]
        ),
    )
    registry = Registry()
    with pytest.raises(CyberSpriteError, match="duplicate operation"):
        registry.load_plugins(enabled=True, names=["broken_one"])
    assert registry.all() == []


def test_cli_loads_enabled_op_on_first_use(plugins, tmp_path):
    install, _, loaded = plugins
    install(
        "ops",
        "tiny",
        factory(
            [
                Op("tiny_read", Model, lambda c, a: {}, EmptyResult, "query", "R"),
            ]
        ),
    )
    create_project(tmp_path / "p", new_project(width=2, height=2))
    assert loaded == []
    result = CliRunner().invoke(cli, ["-p", str(tmp_path / "p"), "op", "tiny_read"])
    assert result.exit_code == 0, result.output
    assert loaded == ["tiny"]


def image():
    return np.full((4, 4, 4), (40, 80, 120, 255), dtype=np.uint8)


def test_pipeline_downsample_convert_import_provenance(plugins, tmp_path):
    install, _, loaded = plugins
    calls = []

    def run(im, params):
        calls.append(params)
        assert params["grid"]["rows"] == 2
        return im[::2, ::2].copy(), {"count": 4}

    install("pipeline_steps", "downsample.tiny", PipelineStep("downsample", "tiny", run))
    overrides = {
        "grid": {"mode": "fixed", "cell_w": 2, "cell_h": 2},
        "downsample": {"method": "tiny", "params": {"amount": 3}},
        "palette": {"mode": "exact"},
        "cleanup": {"min_cluster": 1},
    }
    frames, palette, report = run_pipeline(
        [image()], tmp_path / "stages", preset="exact", overrides=overrides
    )
    assert frames[0].shape == (2, 2) and calls[0]["amount"] == 3
    assert frames[0].tolist() == [[1, 1], [1, 1]]
    assert palette == [(0, 0, 0, 0), (40, 80, 120, 255)]
    record = report["plugins"][0]
    assert record["name"] == "downsample.tiny" and record["version"] == "2.3.4"
    assert record["params"]["params"] == {"amount": 3}
    assert report["determinism"] == "same-platform"
    assert any(w["code"] == "W_PLUGIN_DETERMINISM" for w in report["warnings"])
    path = tmp_path / "input.png"
    path.write_bytes(encode_png(image(), compression="stored"))
    from cybersprite.pipeline.cli_api import convert

    with export_policy(tmp_path):
        result = convert(path, tmp_path / "converted.png", preset="exact", pipeline=overrides)
    assert result["verified"]
    assert decode_png((tmp_path / "converted.png").read_bytes()).pixels.shape[:2] == (2, 2)
    outcome = ops.execute(
        "import_image",
        tmp_path / "imported",
        {
            "files": [str(path)],
            "preset": "exact",
            "pipeline": overrides,
            "provenance": {"provider": "engineering-test", "license": "CC0-1.0"},
        },
        preview="none",
    )
    assert outcome["result"]["accepted"]
    from cybersprite.core.sources import read_manifest

    source = read_manifest(tmp_path / "imported").sources[0]
    assert source.pipeline.report["plugins"][0] == record
    assert loaded.count("downsample.tiny") == 3


@pytest.mark.parametrize("step", ["grid", "reconstruct", "quantize", "cleanup"])
def test_other_pipeline_steps(plugins, tmp_path, step):
    install, _, _ = plugins

    def run(im, params):
        if step == "quantize":
            return IndexedImage(
                np.ones(im.shape[:2], dtype=np.uint8), [(0, 0, 0, 0), (40, 80, 120, 255)]
            ), {"colors": 2}
        return im, {"count": 1}

    install("pipeline_steps", f"{step}.tiny", PipelineStep(step, "tiny", run, True))
    overrides = {"grid": {"mode": "none"}, "cleanup": {"min_cluster": 1}}
    section = "palette" if step == "quantize" else step
    overrides.setdefault(section, {}).update({"method": "tiny"})
    frames, _, report = run_pipeline(
        [image()], tmp_path / step, preset="exact", overrides=overrides
    )
    assert frames[0].shape == (4, 4) and report["plugins"][0]["step"] == step
    assert report["determinism"] == "level-a"


def test_target_auto_uses_enabled_pixeloe_only(plugins, tmp_path):
    install, _, loaded = plugins

    def run(im, params):
        return im[::2, ::2].copy(), {"device": "cpu-test"}

    install("pipeline_steps", "downsample.pixeloe", PipelineStep("downsample", "pixeloe", run))
    install("pipeline_steps", "unrelated", factory(None, api=999))
    frames, _, report = run_pipeline(
        [image()],
        tmp_path / "auto",
        preset="exact",
        overrides={
            "grid": {"mode": "target", "target_w": 2, "target_h": 2},
            "downsample": {"method": "auto"},
        },
    )
    assert frames[0].shape == (2, 2)
    assert report["plugins"][0]["method"] == "pixeloe"
    assert loaded == ["downsample.pixeloe"]


def test_plugin_preserves_diagnostic_conversion_when_auto_grid_fails(plugins, tmp_path):
    install, _, _ = plugins
    install(
        "pipeline_steps",
        "downsample.tiny",
        PipelineStep(
            "downsample",
            "tiny",
            lambda im, params: (im.copy(), {}),
            True,
        ),
    )
    frames, _, report = run_pipeline(
        [image()],
        tmp_path / "diagnostic",
        overrides={
            "grid": {"mode": "auto"},
            "downsample": {"method": "tiny"},
        },
    )
    assert frames[0].shape == (4, 4)
    assert report["accepted"] is False and report["grid"]["detected"] is False
    assert (tmp_path / "diagnostic" / "result.png").is_file()


@pytest.mark.parametrize("kind", ["api", "exception", "dtype", "unknown"])
def test_pipeline_rejects_bad_plugin_or_method(plugins, tmp_path, kind):
    install, _, _ = plugins

    def run(im, params):
        if kind == "exception":
            raise RuntimeError("specific failure")
        return im.astype(np.int32) if kind == "dtype" else im, {}

    value = (
        factory(PipelineStep("downsample", "tiny", run), api=999)
        if kind == "api"
        else PipelineStep("downsample", "tiny", run)
    )
    install("pipeline_steps", "downsample.tiny", value)
    with pytest.raises(CyberSpriteError) as caught:
        run_pipeline(
            [image()],
            tmp_path / kind,
            preset="exact",
            overrides={
                "downsample": {"method": "absent" if kind == "unknown" else "tiny"},
            },
        )
    assert caught.value.code == ("E_INVALID_ARGS" if kind == "unknown" else "E_PLUGIN")
    if kind == "unknown":
        assert "tiny" in caught.value.details["available_methods"]
    assert not (tmp_path / kind / "result.png").exists()


def test_validator_overrides_and_transaction_delta(plugins, tmp_path):
    install, _, _ = plugins

    def check(p, frames):
        p.name = "plugin must not mutate caller"
        value = p.frames[0].duration_ms
        return (
            [{"message": "Long frame.", "where": {"frames": [0]}}] if value > 100 else [],
            {"duration": value},
        )

    install("validators", "test", Validator("Q-test-01", "warning", check))
    registry = ops.registry()
    configure_validation(PluginManager())
    path = tmp_path / "p"
    create_project(path, new_project(width=2, height=2))
    result = ops.execute(
        "set_frame_duration", path, {"frames": [0], "duration_ms": 200}, preview="none"
    )
    assert any(i["rule"] == "Q-test-01" for i in result["validation"]["new_issues"])
    assert result["validation"]["metrics_delta"]["plugins.Q-test-01.duration"] == {
        "before": 100,
        "after": 200,
    }
    p = load_project(path)
    assert p.name != "plugin must not mutate caller" and registry
    p.validation.severity["Q-test-01"] = "error"
    assert not quality.report(p)["ok"]
    p.validation.severity["Q-test-01"] = "off"
    assert all(i["rule"] != "Q-test-01" for i in quality.report(p)["issues"])


def test_validator_failure_does_not_commit(plugins, tmp_path):
    install, _, _ = plugins

    def check(p, frames):
        if p.frames[0].duration_ms > 100:
            raise RuntimeError("specific rule failure")
        return [], {}

    install("validators", "test", Validator("Q-test-01", "warning", check))
    ops.registry()
    path = tmp_path / "p"
    create_project(path, new_project(width=2, height=2))
    before = (path / "project.json").read_bytes()
    with pytest.raises(CyberSpriteError, match="specific rule failure"):
        ops.execute("set_frame_duration", path, {"frames": [0], "duration_ms": 200}, preview="none")
    assert (path / "project.json").read_bytes() == before


def test_plugin_validator_cannot_shadow_builtin_rule(plugins):
    install, _, _ = plugins
    checked = []
    install(
        "validators",
        "PAL",
        Validator(
            "Q-PAL-01",
            "warning",
            lambda p, fs: (checked.append(True) or [], {}),
        ),
    )
    manager = PluginManager()
    configure_validation(manager)
    with pytest.raises(CyberSpriteError, match="unique ID"):
        quality.report(new_project(width=2, height=2))
    assert checked == [] and manager.loaded == {}


def test_palette_listing_and_new_project(plugins, tmp_path):
    install, _, _ = plugins
    install(
        "palettes",
        "test",
        factory(
            [
                {
                    "name": "test-two",
                    "colors": ["#00000000", "#285078ff"],
                    "names": {"1": "Test"},
                }
            ]
        ),
    )
    from cybersprite.formats.palette_files import presets, read_palette_with_names

    row = next(p for p in presets() if p["name"] == "test-two")
    assert row["license"] == "MIT" and row["version"] == "2.3.4"
    assert read_palette_with_names("test-two")[1] == {"1": "Test"}
    ops.execute("new_project", tmp_path / "p", {"width": 2, "height": 2, "palette": "test-two"})
    assert load_project(tmp_path / "p").palette.colors == ["#00000000", "#285078ff"]


@pytest.mark.parametrize("decode", ["valid", "absent", "bad"])
def test_exporter_path_policy_and_self_check(plugins, tmp_path, decode):
    install, _, _ = plugins

    class Exporter:
        plugin_api = 1
        name, extension, options_model = "tiny", ".tiny", Model

        def write(self, p, renderer, out, options):
            out.write_bytes(encode_png(renderer(p, 0), compression="stored"))
            return {
                "files": [],
                "fingerprint": "test-plugin",
                "warnings": [],
                "validation_ok": True,
                "verified": False,
            }

    plugin = Exporter()
    if decode != "absent":
        plugin.decode = lambda data: [decode_png(data).rgba()] if decode == "valid" else [image()]
    install("exporters", "tiny", plugin)
    p = new_project(width=2, height=2)
    with export_policy(tmp_path):
        with pytest.raises(CyberSpriteError) as caught:
            export_plugin(p, PluginExportArgs(out="../outside.tiny", format="tiny"))
        assert caught.value.code == "E_PATH_NOT_ALLOWED"
        args = PluginExportArgs(out="output.tiny", format="tiny")
        if decode == "bad":
            (tmp_path / "output.tiny").write_bytes(b"previous output")
            with pytest.raises(CyberSpriteError, match="differs"):
                export_plugin(p, args)
            assert (tmp_path / "output.tiny").read_bytes() == b"previous output"
        else:
            result = export_plugin(p, args)
            assert result["verified"] == (decode == "valid")
            assert (tmp_path / "output.tiny").is_file()
            if decode == "absent":
                assert "decode" in result["verification_reason"]
            else:
                create_project(tmp_path / "p", p)
                result = ops.execute("export_plugin", tmp_path / "p", {"out": "from-op.tiny"})
                assert result["result"]["verified"]
                assert np.array_equal(
                    decode_png((tmp_path / "from-op.tiny").read_bytes()).rgba(),
                    np.zeros((2, 2, 4), dtype=np.uint8),
                )
