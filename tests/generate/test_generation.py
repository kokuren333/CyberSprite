"""Generation contracts use fake pipelines and a real, small shell-free subprocess."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from click.testing import CliRunner

from cybersprite import ops
from cybersprite.cli import cli
from cybersprite.config import load_config
from cybersprite.core.canonical import load_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.sources import read_manifest
from cybersprite.generate import GenerationRequest
from cybersprite.generate.backends import DiffusersBackend
from cybersprite.generate.licenses import fingerprint, require_license
from cybersprite.generate.registry import BackendRegistry
from cybersprite.generate.service import accept_license

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def configured(tmp_path, monkeypatch):
    directory = tmp_path / "settings"
    directory.mkdir()
    monkeypatch.setenv("CYBERSPRITE_CONFIG_DIR", str(directory))
    monkeypatch.setenv("CYBERSPRITE_NOW", "2026-11-12T00:00:00+00:00")
    (directory / "model.txt").write_bytes(b"test model identity; contains no weights\n")
    (directory / "adapter.txt").write_bytes(b"test adapter identity; contains no weights\n")
    args = [
        str(ROOT / "tests/generate/fake_command.py"),
        "--prompt",
        "{prompt}",
        "--negative-prompt",
        "{negative_prompt}",
        "--width",
        "{width}",
        "--height",
        "{height}",
        "--seed",
        "{seed}",
        "--count",
        "{count}",
        "--out",
        "{out}",
    ]
    text = (
        "[generators.command.fake]\n"
        + f"program={json.dumps(sys.executable)}\n"
        + f'args={json.dumps(args)}\nlicense="test output terms"\ntimeout_seconds=180\n'
        + '[generators.command.fake.model]\nid="test/base"\n'
        + 'local_path="model.txt"\nlicense="CC0-1.0"\n'
        + '[[generators.command.fake.model.adapters]]\nid="test/adapter"\n'
        + 'local_path="adapter.txt"\nlicense="Unlicense"\n'
    )
    (directory / "config.toml").write_text(text, "utf-8")
    return directory, tmp_path / "generated.csprite"


def request(**kwargs):
    return dict(
        backend="command:fake",
        prompt='日本語 ; $(do-not-run) & "quotes" {out}',
        negative_prompt="blur",
        width=8,
        height=6,
        seed=19,
        **kwargs,
    )


def test_command_license_gate_batch_replay_and_import(configured):
    settings, project = configured
    with pytest.raises(CyberSpriteError) as error:
        ops.execute("generate_image", project, request())
    assert error.value.code == "E_LICENSE_NOT_ACCEPTED"
    assert not (project / "source").exists()
    result = ops.execute(
        "generate_image",
        project,
        request(count=2, accept_model_license=True),
        idempotency_key="once",
    )
    assert result["result"]["sources"] == ["SRC1", "SRC2"]
    assert not (project / "project.json").exists()
    accepted = json.loads((settings / "models.json").read_bytes())["models"]
    assert {r["id"] for r in accepted} == {"test/base", "test/adapter"}
    source = read_manifest(project).sources[0]
    assert source.provider == "command:fake" and source.model.id == "test/base"
    assert source.model.sha256 == hashlib.sha256((settings / "model.txt").read_bytes()).hexdigest()
    assert source.model.adapters[0].license == "Unlicense"
    assert source.params["adapters"][0]["sha256"] == fingerprint(settings / "adapter.txt")
    assert source.prompt == request()["prompt"] and source.seed == 19
    assert (
        source.files[0].sha256 == "cefe701a2801aae4dec10a6cb707701ec5898519db0260ad8f3d364b0633d259"
    )
    assert source.created_at == "2026-11-12T00:00:00+00:00"
    assert source.pipeline is None and source.placements == []
    replay = ops.execute("generate_image", project, request(count=2), idempotency_key="once")
    assert replay == result
    with pytest.raises(CyberSpriteError, match="different arguments"):
        ops.execute("generate_image", project, request(count=1), idempotency_key="once")
    imported = ops.execute(
        "import_image", project, {"source": "SRC1", "preset": "exact"}, preview="path"
    )
    assert imported["result"]["accepted"] and imported["result"]["placed"]
    assert imported["validation"]["ok"]
    loaded = load_project(project)
    assert (loaded.canvas.width, loaded.canvas.height) == (8, 6)
    assert len(read_manifest(project).sources) == 2
    assert read_manifest(project).sources[0].placements[0].revision == loaded.revision
    before = (project / "project.json").read_bytes()
    ops.execute("generate_image", project, request())
    assert (project / "project.json").read_bytes() == before


def test_exact_cli_command_workflow(configured):
    _, project = configured
    runner = CliRunner()
    listed = runner.invoke(cli, ["gen", "backends"])
    assert listed.exit_code == 0, listed.output
    command = next(
        b for b in json.loads(listed.output)["result"]["backends"] if b["name"] == "command:fake"
    )
    assert not command["available"] and "license" in command["reason"].lower()
    accepted = runner.invoke(cli, ["gen", "accept-license", "command:fake"])
    assert accepted.exit_code == 0, accepted.output
    generated = runner.invoke(
        cli,
        [
            "-p",
            str(project),
            "gen",
            "run",
            "--backend",
            "command:fake",
            "--prompt",
            "test",
            "--width",
            "8",
            "--height",
            "6",
            "--seed",
            "19",
            "--idempotency-key",
            "cli-once",
        ],
    )
    assert generated.exit_code == 0, generated.output
    assert json.loads(generated.output)["result"]["sources"] == ["SRC1"]
    imported = runner.invoke(
        cli, ["-p", str(project), "import", "image", "--source", "SRC1", "--preset", "exact"]
    )
    assert imported.exit_code == 0, imported.output
    assert json.loads(imported.output)["result"]["accepted"]


@pytest.mark.parametrize("file", ["model.txt", "adapter.txt"])
def test_changed_model_requires_new_acceptance(configured, file):
    settings, project = configured
    accept_license("command:fake")
    (settings / file).write_bytes(b"changed local identity")
    with pytest.raises(CyberSpriteError) as error:
        ops.execute("generate_image", project, request())
    assert error.value.code == "E_LICENSE_NOT_ACCEPTED"
    assert not (project / "source").exists()


def test_availability_no_runtime_no_gpu_no_model(configured, monkeypatch):
    backend = DiffusersBackend(load_config().generators.diffusers)

    def missing(_name):
        raise ImportError("not installed")

    monkeypatch.setattr("cybersprite.generate.backends.importlib.import_module", missing)
    assert "not installed" in backend.availability().reason
    monkeypatch.setattr(
        "cybersprite.generate.backends.importlib.import_module",
        lambda _name: SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False)),
    )
    assert "GPU" in backend.availability().reason
    monkeypatch.setattr(backend, "runtime", lambda: (None, None))
    assert "No model" in backend.availability().reason
    monkeypatch.undo()
    _, project = configured
    assert ops.execute("new_project", project, {"width": 4, "height": 4})["ok"]


def test_command_missing_files_and_program_have_reasons(configured):
    settings, _ = configured
    (settings / "model.txt").unlink()
    backend = BackendRegistry().get("command:fake")
    assert "No model files" in backend.availability().reason
    backend.program = "cybersprite-no-such-executable"
    assert "executable not found" in backend.availability().reason


def test_command_timeout_and_failure(configured, monkeypatch):
    _, project = configured
    accept_license("command:fake")

    def timeout(*args, **kwargs):
        assert kwargs["shell"] is False
        raise subprocess.TimeoutExpired(args[0], 1)

    monkeypatch.setattr("cybersprite.generate.backends.subprocess.run", timeout)
    with pytest.raises(CyberSpriteError) as error:
        ops.execute("generate_image", project, request())
    assert error.value.code == "E_TIMEOUT"
    assert read_manifest(project).sources == []
    assert list((project / "source").iterdir()) == []
    monkeypatch.setattr(
        "cybersprite.generate.backends.subprocess.run",
        lambda *a, **kw: SimpleNamespace(returncode=7),
    )
    with pytest.raises(CyberSpriteError) as error:
        ops.execute("generate_image", project, request())
    assert error.value.code == "E_GENERATION_FAILED"


def test_prompt_is_one_literal_argument(configured, monkeypatch):
    _, project = configured
    accept_license("command:fake")
    real_run = subprocess.run

    def inspect(args, **kwargs):
        assert args[args.index("--prompt") + 1] == request()["prompt"]
        assert kwargs["shell"] is False and isinstance(args, list)
        return real_run(args, **kwargs)

    monkeypatch.setattr("cybersprite.generate.backends.subprocess.run", inspect)
    ops.execute("generate_image", project, request())


def test_injection_and_unknown_model_refused(configured):
    _, project = configured
    for values in [
        request(params={"program": "bad"}),
        request(model="arbitrary/download"),
        request(params={"surprise": True}),
    ]:
        with pytest.raises(CyberSpriteError) as error:
            ops.execute("generate_image", project, values)
        assert error.value.code == "E_INVALID_ARGS"


@pytest.mark.parametrize("single_file", [False, True])
@pytest.mark.parametrize("fp16_variant", [False, True])
def test_diffusers_fake_pipeline(configured, monkeypatch, single_file, fp16_variant):
    from cybersprite.config import DiffusersSettings
    from cybersprite.generate.contracts import ModelInfo

    settings, _ = configured
    calls = []
    image = SimpleNamespace(convert=lambda mode: np.full((6, 8, 4), 255, dtype=np.uint8))

    class FakePipeline:
        def to(self, device):
            calls.append(("to", device))
            return self

        def load_lora_weights(self, path, **kwargs):
            calls.append(("lora", path, kwargs))

        def set_adapters(self, names):
            calls.append(("adapters", names))

        def __call__(self, **kwargs):
            calls.append(("call", kwargs))
            return SimpleNamespace(images=[image] * kwargs["num_images_per_prompt"])

    class Factory:
        @staticmethod
        def from_pretrained(path, **kwargs):
            calls.append(("load", path, kwargs))
            return FakePipeline()

        from_single_file = from_pretrained

    class Generator:
        def __init__(self, **kwargs):
            calls.append(("generator", kwargs))

        def manual_seed(self, seed):
            calls.append(("seed", seed))
            return self

    backend = DiffusersBackend(DiffusersSettings())
    location = settings / "model.txt" if single_file else settings
    if fp16_variant:
        (settings / "model.fp16.safetensors").write_bytes(b"fake variant, not weights")
    adapter = ModelInfo(
        id="test/adapter",
        license="Unlicense",
        local_path=str(settings / "adapter.txt"),
        sha256=fingerprint(settings / "adapter.txt"),
    )
    model = ModelInfo(
        id="fake",
        license="CC0-1.0",
        sha256=fingerprint(location),
        local_path=str(location),
        adapters=[adapter],
    )
    require_license(model, accept=True)
    monkeypatch.setattr(backend, "selected_model", lambda _alias: model)
    monkeypatch.setattr(
        backend,
        "runtime",
        lambda: (
            SimpleNamespace(Generator=Generator, float16="float16"),
            SimpleNamespace(AutoPipelineForText2Image=Factory, StableDiffusionPipeline=Factory),
        ),
    )
    out = settings / "out"
    out.mkdir()
    generated = backend.generate(
        GenerationRequest(**{**request(count=2), "backend": "diffusers"}), out, lambda *args: None
    )
    assert len(generated) == 2 and generated[0].seed == 19
    assert next(c for c in calls if c[0] == "load")[2]["local_files_only"] is True
    load_options = next(c for c in calls if c[0] == "load")[2]
    assert load_options.get("variant") == ("fp16" if fp16_variant and not single_file else None)
    if fp16_variant and not single_file:
        assert load_options["use_safetensors"] is True
    kwargs = next(c for c in calls if c[0] == "call")[1]
    assert kwargs["prompt"] == request()["prompt"] and kwargs["guidance_scale"] == 7
    assert kwargs["num_inference_steps"] == 30
    assert "deterministic" not in kwargs
    assert next(c for c in calls if c[0] == "lora")[2] == {
        "local_files_only": True,
        "adapter_name": "adapter_0",
        "weight_name": "adapter.txt",
    }
    assert ("adapters", ["adapter_0"]) in calls


@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("workspace", [None, ":16:8"])
def test_deterministic_generation_restores_flags_and_environment(monkeypatch, fail, workspace):
    import os

    from cybersprite.generate.backends import deterministic_generation

    if workspace is None:
        monkeypatch.delenv("CUBLAS_WORKSPACE_CONFIG", raising=False)
    else:
        monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", workspace)
    cudnn = SimpleNamespace(benchmark=True, deterministic=False, allow_tf32=True)
    matmul = SimpleNamespace(allow_tf32=True)
    state = [False, True]

    def algorithms(enabled, warn_only=False):
        state[:] = [enabled, warn_only]

    torch = SimpleNamespace(
        are_deterministic_algorithms_enabled=lambda: state[0],
        is_deterministic_algorithms_warn_only_enabled=lambda: state[1],
        use_deterministic_algorithms=algorithms,
        backends=SimpleNamespace(cudnn=cudnn, cuda=SimpleNamespace(matmul=matmul)),
    )
    try:
        with deterministic_generation(torch, True):
            assert state == [True, False]
            assert os.environ["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"
            assert not cudnn.benchmark and cudnn.deterministic
            assert not cudnn.allow_tf32 and not matmul.allow_tf32
            if fail:
                raise RuntimeError("unsupported deterministic operation")
    except RuntimeError:
        assert fail
    assert state == [False, True]
    assert cudnn.benchmark and not cudnn.deterministic
    assert cudnn.allow_tf32 and matmul.allow_tf32
    assert os.environ.get("CUBLAS_WORKSPACE_CONFIG") == workspace


def test_lazy_plugins_and_explicit_enable(configured, monkeypatch):
    from cybersprite.generate.contracts import Availability

    loaded = []

    class Plugin:
        plugin_api = 1
        name = "fake-plugin"

        def availability(self):
            return Availability(available=True)

    entry = SimpleNamespace(name="fake-plugin", load=lambda: loaded.append(True) or Plugin)
    monkeypatch.setattr("cybersprite.generate.registry.entry_points", lambda **kw: [entry])
    registry = BackendRegistry()
    assert registry.describe()["backends"] and loaded == []
    with pytest.raises(CyberSpriteError, match="not enabled"):
        registry.get("fake-plugin")
    registry.settings.plugins.enabled.append("fake-plugin")
    assert registry.get("fake-plugin").availability().available
    assert loaded == [True]


def test_tracked_and_packaged_files_never_contain_weights():
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    weights = {".safetensors", ".ckpt", ".pt", ".pth", ".onnx", ".gguf", ".ggml", ".h5"}
    for name in result.stdout.decode("utf-8").split("\0"):
        if not name:
            continue
        path = ROOT / name
        assert path.suffix.lower() not in weights, name
        assert not (path.suffix.lower() == ".bin" and "model" in path.name.lower()), name
        if path.is_file():
            assert path.stat().st_size < 32 * 1024 * 1024, name
    for path in (ROOT / "src/cybersprite").rglob("*"):
        if path.is_file():
            assert path.suffix.lower() not in weights, path
            assert path.stat().st_size < 32 * 1024 * 1024, path


def test_mcp_generation_is_opt_in_and_read_only_gated(configured):
    pytest.importorskip("mcp.server")
    from jsonschema import Draft202012Validator
    from mcp.shared.exceptions import MCPError

    from cybersprite.mcp.server import MCPService

    _, project = configured
    accept_license("command:fake")
    root = project.parent
    assert "generate_image" not in MCPService(root=root).exposed
    assert "list_generators" not in MCPService(root=root).exposed
    with pytest.raises(MCPError):
        MCPService(root=root).call("generate_image", {"project": project.name, **request()})
    for profile in ["standard", "minimal"]:
        service = MCPService(root=root, enable_generation=True, profile=profile)
        assert {"generate_image", "list_generators"} <= set(service.exposed)
        assert service.contracts["generate_image"]["annotations"]["openWorldHint"]
    readonly = MCPService(root=root, enable_generation=True, read_only=True)
    assert "generate_image" not in readonly.exposed and "list_generators" in readonly.exposed
    response = service.call(
        "generate_image", {"project": project.name, **request(), "idempotency_key": "mcp-once"}
    )
    value = response.structured_content
    assert value["ok"], value
    Draft202012Validator(service.contracts["generate_image"]["outputSchema"]).validate(value)
    assert value["result"]["sources"] == ["SRC1"]
    assert not (project / "project.json").exists()
    rejected = service.call(
        "apply_ops", {"project": project.name, "ops": [{"op": "generate_image", "args": request()}]}
    )
    assert not rejected.structured_content["ok"]


@pytest.mark.parametrize("bad_output", ["outside", "dimensions", "count", "corrupt", "identity"])
def test_invalid_backend_output_never_commits_manifest(configured, monkeypatch, bad_output):
    import cybersprite.generate.service as service
    from cybersprite.formats.png import encode_png
    from cybersprite.generate.contracts import GeneratedImage

    settings, project = configured
    accept_license("command:fake")
    registry = BackendRegistry()
    backend = registry.get("command:fake")
    model = backend.selected_model()

    def generate(request, out_dir, _progress):
        if bad_output == "count":
            return []
        path = (settings if bad_output == "outside" else out_dir) / "image.png"
        shape = (1, 1, 4) if bad_output == "dimensions" else (6, 8, 4)
        path.write_bytes(
            b"not a png" if bad_output == "corrupt" else encode_png(np.zeros(shape, dtype=np.uint8))
        )
        used_model = (
            model.model_copy(update={"sha256": "bad"}) if bad_output == "identity" else model
        )
        return [GeneratedImage(path=path, seed=19, model=used_model, params={})]

    monkeypatch.setattr(backend, "generate", generate)
    monkeypatch.setattr(
        service, "BackendRegistry", lambda: SimpleNamespace(get=lambda _name: backend)
    )
    with pytest.raises(CyberSpriteError) as error:
        ops.execute("generate_image", project, request())
    assert error.value.code in {"E_GENERATION_FAILED", "E_PATH_NOT_ALLOWED"}
    assert read_manifest(project).sources == []


def test_directory_digest_has_fixed_portable_order(configured):
    settings, _ = configured
    directory = settings / "digest"
    directory.mkdir()
    (directory / "a.txt").write_bytes(b"a")
    (directory / "B.txt").write_bytes(b"b")
    assert (
        fingerprint(directory) == "51c1fb5ce679af56a4b5fbb37e48b6e218ce0c40492f222ed23aafbbea6dac6a"
    )


def test_seed_omission_records_chosen_seed(configured, monkeypatch):
    _, project = configured
    accept_license("command:fake")
    monkeypatch.setattr("cybersprite.generate.backends.secrets.randbits", lambda _bits: 1234)
    ops.execute("generate_image", project, {**request(), "seed": None})
    assert read_manifest(project).sources[0].seed == 1234
