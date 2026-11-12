"""BYOW metadata, base terms and source outlets use local, self-authored dummy data."""

import hashlib
import json
from datetime import datetime

import pytest
from click.testing import CliRunner

from cybersprite import ops
from cybersprite.cli import cli
from cybersprite.config import load_config
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.source_terms import model_terms
from cybersprite.generate.backends import DiffusersBackend
from cybersprite.generate.models import list_models, register_model, term_badges


@pytest.fixture
def byow(tmp_path, monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_CONFIG_DIR", str(tmp_path / "config"))
    path = tmp_path / "dummy.data"
    path.write_bytes(b"Self-authored test vector. No model weights.\n")
    return path


def register(path, name="base", **kwargs):
    return register_model(path, name=name, kind="checkpoint", license="CC0-1.0", **kwargs)


def test_registration_cli_roundtrip_preserves_config(byow):
    config = byow.parent / "config/config.toml"
    config.parent.mkdir()
    config.write_text('# preserve this comment\n[gui]\nlanguage="en"\n', encoding="utf-8")
    result = CliRunner().invoke(
        cli,
        [
            "gen",
            "register-model",
            str(byow),
            "--name",
            '日本語 "base"',
            "--kind",
            "checkpoint",
            "--base-model",
            "unknown",
            "--license",
            "CreativeML-OpenRAIL-M",
            "--license-url",
            "https://example.invalid/license",
            "--commercial-use",
            "yes",
            "--source-url",
            "https://example.invalid/model",
            "--note",
            "test registration",
        ],
    )
    assert result.exit_code == 0, result.output
    record = load_config().generators.diffusers.models['日本語 "base"']
    assert record.sha256 == hashlib.sha256(byow.read_bytes()).hexdigest()
    assert record.display_name == '日本語 "base"' and record.base_model == "unknown"
    assert record.license_url.endswith("/license") and record.source_url.endswith("/model")
    assert (
        record.note == "test registration" and datetime.fromisoformat(record.registered_at).tzinfo
    )
    assert config.read_text("utf-8").startswith("# preserve this comment")
    listed = CliRunner().invoke(cli, ["gen", "models"])
    assert listed.exit_code == 0, listed.output
    assert (
        json.loads(listed.output)["result"]["models"][0]["badges"][0]["badge"]
        == "commercial OK with use restrictions (not OSI)"
    )
    text = CliRunner().invoke(cli, ["--format", "text", "gen", "models"])
    assert "commercial OK with use restrictions (not OSI)" in text.output
    duplicate = CliRunner().invoke(
        cli,
        [
            "gen",
            "register-model",
            str(byow),
            "--name",
            '日本語 "base"',
            "--kind",
            "checkpoint",
            "--license",
            "MIT",
        ],
    )
    assert duplicate.exit_code == 3 and "E_EXISTS" in duplicate.output


@pytest.mark.parametrize("kind", ["lora", "vae", "controlnet"])
def test_adapter_registration_and_base_warning(byow, kind):
    register(byow, commercial_use="no")
    register_model(
        byow, name="adapter", kind=kind, base_model="base", license="MIT", commercial_use="yes"
    )
    backend = DiffusersBackend(load_config().generators.diffusers)
    model = backend.selected_model("adapter")
    assert model.bases[0].commercial_use == "no"
    assert model.bases[0].sha256 == model.sha256
    assert {t["commercial_use"] for t in term_badges(model.model_dump())} == {"yes", "no"}
    assert any(b["badge"] == "non-commercial only" for b in list_models()["models"][0]["badges"])


def test_list_generators_models_carry_the_same_badges(byow):
    register(byow, commercial_use="no")
    from cybersprite.generate.registry import BackendRegistry

    described = BackendRegistry().describe()["backends"]
    diffusers = next(b for b in described if b["name"] == "diffusers")
    badges = diffusers["models"][0]["badges"]
    assert badges == list_models()["models"][0]["badges"]
    assert badges[0]["badge"] == "non-commercial only"


@pytest.mark.parametrize(
    "name,kind,base",
    [
        ("unknown", "checkpoint", "unknown"),
        ("a", "diffusers-dir", "unknown"),
        ("a", "checkpoint", "missing"),
    ],
)
def test_invalid_registration_never_writes(byow, name, kind, base):
    with pytest.raises(CyberSpriteError):
        register_model(byow, name=name, kind=kind, base_model=base, license="MIT")
    assert not (byow.parent / "config/config.toml").exists()


def test_directory_registration_hash_vector(byow):
    folder = byow.parent / "pipeline"
    folder.mkdir()
    (folder / "b").write_bytes(b"B")
    (folder / "a").write_bytes(b"A")
    expected = hashlib.sha256(
        b"CSMODEL1\na\0" + hashlib.sha256(b"A").digest() + b"b\0" + hashlib.sha256(b"B").digest()
    ).hexdigest()
    item = register_model(folder, name="dir", kind="diffusers-dir", license="MIT")
    assert item["sha256"] == expected


def test_missing_and_cyclic_bases_are_actionable(byow):
    register(byow)
    path = byow.parent / "config/config.toml"
    original = path.read_text("utf-8")
    for base in ("missing", "base"):
        path.write_text(
            original.replace('base_model = "unknown"', f'base_model = "{base}"'), encoding="utf-8"
        )
        with pytest.raises(CyberSpriteError, match="Invalid user configuration"):
            load_config()


@pytest.mark.parametrize(
    "license,commercial,badge",
    [
        ("OpenRAIL++", "yes", "commercial OK with use restrictions (not OSI)"),
        ("CreativeML-OpenRAIL-M", "unknown", "commercial OK with use restrictions (not OSI)"),
        ("CC-BY-NC-4.0", "yes", "non-commercial only"),
        ("custom", "yes", "needs review"),
        ("unknown", "unknown", "needs review"),
        ("MIT", "yes", "commercial OK"),
    ],
)
def test_badges_keep_explicit_commercial_status(license, commercial, badge):
    row = term_badges({"id": "test", "license": license, "commercial_use": commercial})[0]
    assert row["badge"] == badge and row["commercial_use"] == commercial


def test_unknown_adapter_base_is_reviewed(byow):
    register_model(byow, name="lora", kind="lora", license="MIT", commercial_use="yes")
    terms = model_terms(
        DiffusersBackend(load_config().generators.diffusers).selected_model("lora").model_dump()
    )
    assert terms[-1]["commercial_use"] == "unknown"


def test_registered_base_acceptance_and_inline_adapter_parent_reference(byow):
    from cybersprite.generate.licenses import identities, require_license

    register(byow, commercial_use="no")
    register_model(
        byow, name="lora", kind="lora", base_model="base", license="MIT", commercial_use="yes"
    )
    settings = load_config().generators.diffusers
    backend = DiffusersBackend(settings)
    model = backend.selected_model("lora")
    assert {r["id"] for r in identities(model)} == {"lora", "base"}
    with pytest.raises(CyberSpriteError) as error:
        require_license(model)
    assert error.value.code == "E_LICENSE_NOT_ACCEPTED"
    require_license(model, accept=True)
    require_license(model)
    byow.write_bytes(b"Changed base and adapter content requires fresh acceptance.")
    with pytest.raises(CyberSpriteError) as error:
        require_license(backend.selected_model("lora"))
    assert error.value.code == "E_LICENSE_NOT_ACCEPTED"
    # An inline adapter may explicitly reference its owning base without recursion.
    from cybersprite.config import ModelLocation

    settings.models["base"].adapters = [
        ModelLocation(
            local_path=str(byow),
            license="MIT",
            kind="lora",
            base_model="base",
            commercial_use="yes",
        )
    ]
    model = backend.selected_model("base")
    assert model.adapters[0].bases[0].id == "base"
    assert model.adapters[0].bases[0].adapters == []


def test_human_commands_are_not_ops_or_mcp_tools(byow):
    from cybersprite.mcp.server import MCPService

    names = {"register_model", "models", "comfy_inspect"}
    assert not names.intersection(op.name for op in ops.registry().all())
    assert not names.intersection(MCPService(root=byow.parent, enable_generation=True).exposed)


@pytest.mark.parametrize("location", ["model", "adapter", "base", "unknown-base", "all-yes"])
def test_placed_source_terms_snapshot_is_independent_of_config(byow, location):
    import numpy as np

    from cybersprite.formats.png import encode_png

    path = byow.with_suffix(".png")
    path.write_bytes(encode_png(np.full((2, 2, 4), 255, dtype=np.uint8)))
    project = byow.parent / "terms.csprite"
    model = {"id": "base", "license": "MIT", "commercial_use": "yes", "bases": [], "adapters": []}
    if location == "model":
        model["commercial_use"] = "unknown"
    if location == "adapter":
        model["adapters"] = [{"id": "adapter", "license": "custom", "commercial_use": "no"}]
    if location == "base":
        model["bases"] = [{"id": "upstream", "license": "custom", "commercial_use": "unknown"}]
    if location == "unknown-base":
        model.update(kind="lora", base_model="unknown")
    result = ops.execute(
        "import_image",
        project,
        {
            "files": str(path),
            "preset": "exact",
            "provenance": {
                "license": "MIT",
                "model": {"id": "base", "license": "MIT", "sha256": "", "adapters": []},
                "params": {"model_registry": model},
            },
        },
    )
    assert result["result"]["placed"]
    validation = ops.execute("validate", project, {})["result"]
    warnings = [i for i in validation["issues"] if i["rule"] == "Q-SRC-04"]
    assert bool(warnings) == (location != "all-yes")
    assert all(i["level"] == "warning" for i in warnings)
