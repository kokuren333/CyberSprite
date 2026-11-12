"""Exercise the public HTTP boundary with a self-authored fake ComfyUI server."""

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import numpy as np
import pytest
from click.testing import CliRunner

from cybersprite import ops
from cybersprite.cli import cli
from cybersprite.config import ComfySettings, load_config
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.sources import read_manifest
from cybersprite.formats.png import decode_png, encode_png
from cybersprite.generate.comfyui import ComfyUIBackend, inspect_workflow
from cybersprite.generate.service import accept_license


def graph():
    # Written specifically for this test; no third-party workflow or asset.
    return {
        "p": {"class_type": "CLIPTextEncode", "inputs": {"text": "old positive"}},
        "n": {"class_type": "CLIPTextEncode", "inputs": {"text": "old negative"}},
        "s": {
            "class_type": "KSampler",
            "inputs": {
                "positive": ["p", 0],
                "negative": ["n", 0],
                "seed": 1,
                "steps": 20,
                "cfg": 7,
            },
        },
        "z": {"class_type": "EmptyLatentImage", "inputs": {"width": 8, "height": 6}},
        "c": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "old.data"}},
        "l": {"class_type": "LoraLoader", "inputs": {"lora_name": "old-lora.data"}},
    }


@pytest.fixture
def comfy(tmp_path, monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_CONFIG_DIR", str(tmp_path))
    workflow = tmp_path / "workflow.json"
    workflow.write_text(json.dumps(graph()), encoding="utf-8")
    state = {"calls": [], "submitted": [], "mode": "ok", "polls": 0, "count": 1}
    raster = encode_png(np.full((6, 8, 4), 255, dtype=np.uint8), compression="stored")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, value, code=200, binary=False):
            data = value if binary else json.dumps(value).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            state["calls"].append(self.path)
            state["submitted"].append(
                json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            )
            if state["mode"] == "reject":
                self.respond({"error": "invalid nodes", "node_errors": {"s": "missing"}}, 400)
            else:
                self.respond({"prompt_id": "job-1", "number": 1})

        def do_GET(self):
            state["calls"].append(self.path)
            if self.path == "/system_stats":
                self.respond({"devices": []})
            elif self.path == "/history/job-1":
                state["polls"] += 1
                if state["mode"] == "pending" or state["polls"] == 1:
                    self.respond({})
                elif state["mode"] == "error":
                    self.respond({"job-1": {"status": {"status_str": "error", "completed": False}}})
                elif state["mode"] == "malformed":
                    self.respond(b"not JSON", binary=True)
                elif state["mode"] == "oversize-json":
                    self.send_response(200)
                    self.send_header("Content-Length", str(9 * 1024 * 1024))
                    self.end_headers()
                elif state["mode"] == "redirect":
                    self.send_response(302)
                    self.send_header("Location", "/should-not-follow")
                    self.end_headers()
                else:
                    self.respond(
                        {
                            "job-1": {
                                "status": {"status_str": "success", "completed": True},
                                "outputs": {
                                    "o": {
                                        "images": [
                                            {
                                                "filename": "../日本語 image.png",
                                                "subfolder": "folder with space",
                                                "type": "output",
                                            }
                                        ]
                                        * state["count"]
                                    }
                                },
                            }
                        }
                    )
            elif self.path.startswith("/view?"):
                query = parse_qs(urlsplit(self.path).query)
                assert query["filename"] == ["../日本語 image.png"]
                assert query["subfolder"] == ["folder with space"]
                if state["mode"] == "oversize-image":
                    self.send_response(200)
                    self.send_header("Content-Length", str(65 * 1024 * 1024))
                    self.end_headers()
                else:
                    self.respond(
                        b"not raster" if state["mode"] == "corrupt" else raster, binary=True
                    )
            else:
                self.respond({}, 404)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    bind = inspect_workflow(workflow)["bind"]
    config = (
        f"[generators.comfyui]\nurl={json.dumps(url)}\ntimeout_seconds=60\n"
        "request_timeout_seconds=30\npoll_interval_ms=1\n"
        '[generators.comfyui.workflows.test]\nfile="workflow.json"\n'
        'license="test workflow terms"\ncommercial_use="unknown"\n'
        "[generators.comfyui.workflows.test.bind]\n"
        + "".join(f"{key}={json.dumps(value)}\n" for key, value in sorted(bind.items()))
    )
    (tmp_path / "config.toml").write_text(config, encoding="utf-8")
    try:
        yield state, tmp_path / "project.csprite", workflow, raster
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def request(**kwargs):
    return {
        "backend": "comfyui",
        "model": "test",
        "prompt": "日本語 ; {text}",
        "negative_prompt": "blur",
        "width": 8,
        "height": 6,
        "seed": 42,
        **kwargs,
    }


def test_http_generation_provenance_replay_outlet_and_placement(comfy):
    state, project, workflow, raster = comfy
    accept_license("comfyui:test")
    result = ops.execute(
        "generate_image",
        project,
        request(
            use="design",
            rights_note="Review third-party rights",
            params={"steps": 12, "cfg": 5, "checkpoint": "local.data", "lora": "local-lora.data"},
        ),
        idempotency_key="once",
    )
    assert result["ok"] and result["result"]["use"] == "design"
    assert result["result"]["model_terms"][0]["badge"] == "needs review"
    assert result["warnings"][0]["code"] == "W_MODEL_TERMS"
    assert not (project / "project.json").exists()
    source = read_manifest(project).sources[0]
    assert source.rights_note == "Review third-party rights" and source.params["use"] == "design"
    assert source.params["server_url"].startswith("http://127.0.0.1:")
    assert source.model.sha256 == hashlib.sha256(workflow.read_bytes()).hexdigest()
    saved = project / source.params["workflow"]["path"]
    assert (
        hashlib.sha256(saved.read_bytes()).hexdigest()
        == source.params["workflow_sha256"]
        == source.params["workflow"]["sha256"]
    )
    filled = json.loads(saved.read_bytes())
    assert filled == state["submitted"][0]["prompt"]
    assert filled["p"]["inputs"]["text"] == request()["prompt"]
    assert filled["s"]["inputs"]["seed"] == 42 and filled["s"]["inputs"]["cfg"] == 5
    assert filled["c"]["inputs"]["ckpt_name"] == "local.data"
    assert (project / source.files[0].path).read_bytes() == raster
    assert decode_png((project / source.files[0].path).read_bytes()).pixels.shape == (6, 8, 4)
    assert (
        ops.execute(
            "generate_image",
            project,
            request(
                use="design",
                rights_note="Review third-party rights",
                params={
                    "steps": 12,
                    "cfg": 5,
                    "checkpoint": "local.data",
                    "lora": "local-lora.data",
                },
            ),
            idempotency_key="once",
        )
        == result
    )
    assert len(state["submitted"]) == 1
    placed = ops.execute("import_image", project, {"source": "SRC1", "preset": "exact"})
    issues = placed["validation"]["new_issues"]
    assert any(i["rule"] == "Q-SRC-04" for i in issues)
    saved.write_bytes(b"changed")
    with pytest.raises(CyberSpriteError, match="workflow is missing or changed"):
        ops.execute(
            "generate_image",
            project,
            request(
                use="design",
                rights_note="Review third-party rights",
                params={
                    "steps": 12,
                    "cfg": 5,
                    "checkpoint": "local.data",
                    "lora": "local-lora.data",
                },
            ),
            idempotency_key="once",
        )


def test_cli_inspection_and_generation(comfy):
    state, project, workflow, _ = comfy
    result = CliRunner().invoke(cli, ["gen", "comfy-inspect", str(workflow)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["result"]["bind"]["prompt"] == ["p", "inputs", "text"]
    generated = CliRunner().invoke(
        cli,
        [
            "-p",
            str(project),
            "gen",
            "run",
            "--backend",
            "comfyui",
            "--model",
            "test",
            "--prompt",
            "test",
            "--width",
            "8",
            "--height",
            "6",
            "--seed",
            "42",
            "--use",
            "canvas",
            "--rights-note",
            "test note",
            "--accept-model-license",
        ],
    )
    assert generated.exit_code == 0, generated.output
    assert json.loads(generated.output)["result"]["use"] == "canvas"
    assert read_manifest(project).sources[0].rights_note == "test note"
    assert state["submitted"]


@pytest.mark.parametrize(
    "params",
    [
        {"workflow": {}},
        {"url": "http://evil.invalid"},
        {"file": "anything"},
        {"steps": 1.5},
        {"cfg": "7"},
        {"node_id": "x"},
    ],
)
def test_arbitrary_workflow_and_unbound_parameters_are_refused(comfy, params):
    state, project, _, _ = comfy
    with pytest.raises(CyberSpriteError) as error:
        ops.execute("generate_image", project, request(params=params, accept_model_license=True))
    assert error.value.code == "E_INVALID_ARGS" and not state["submitted"]


def test_unregistered_workflow_and_unbound_value_refused(comfy):
    state, project, _, _ = comfy
    with pytest.raises(CyberSpriteError, match="registered ComfyUI workflow"):
        ops.execute("generate_image", project, request(model="not-registered"))
    settings = load_config()
    del settings.generators.comfyui.workflows["test"].bind["steps"]
    from cybersprite.generate.contracts import GenerationRequest

    with pytest.raises(CyberSpriteError, match="Register bindings"):
        ComfyUIBackend(settings.generators.comfyui).checked(
            GenerationRequest(**request(params={"steps": 5}))
        )
    assert not state["submitted"]


def test_license_acceptance_is_bound_to_workflow_hash(comfy):
    state, project, workflow, _ = comfy
    with pytest.raises(CyberSpriteError) as error:
        ops.execute("generate_image", project, request())
    assert error.value.code == "E_LICENSE_NOT_ACCEPTED"
    accept_license("comfyui:test")
    workflow.write_bytes(workflow.read_bytes() + b"\n")
    with pytest.raises(CyberSpriteError) as error:
        ops.execute("generate_image", project, request())
    assert error.value.code == "E_LICENSE_NOT_ACCEPTED" and not state["submitted"]


@pytest.mark.parametrize(
    "mode,code",
    [
        ("reject", "E_GENERATION_FAILED"),
        ("error", "E_GENERATION_FAILED"),
        ("pending", "E_TIMEOUT"),
        ("malformed", "E_GENERATION_FAILED"),
        ("redirect", "E_GENERATION_FAILED"),
        ("corrupt", "E_GENERATION_FAILED"),
        ("oversize-json", "E_GENERATION_FAILED"),
        ("oversize-image", "E_GENERATION_FAILED"),
    ],
)
def test_http_failures_do_not_save_sources(comfy, mode, code):
    state, project, _, _ = comfy
    state["mode"] = mode
    if mode == "pending":
        from cybersprite.config import config_path

        config = config_path()
        config.write_text(
            config.read_text("utf-8").replace("timeout_seconds=60", "timeout_seconds=1"),
            encoding="utf-8",
        )
    with pytest.raises(CyberSpriteError) as error:
        ops.execute("generate_image", project, request(accept_model_license=True))
    assert error.value.code == code
    assert read_manifest(project).sources == []
    assert "/should-not-follow" not in state["calls"]


def test_wrong_count_and_dimension_rejected(comfy):
    state, project, _, _ = comfy
    state["count"] = 2
    with pytest.raises(CyberSpriteError, match="expected 1"):
        ops.execute("generate_image", project, request(accept_model_license=True))
    state["count"] = 1
    with pytest.raises(CyberSpriteError, match="dimensions"):
        ops.execute("generate_image", project, request(width=9, accept_model_license=True))
    assert read_manifest(project).sources == []


def test_availability_when_server_not_running(comfy):
    _, _, _, _ = comfy
    backend = ComfyUIBackend(load_config().generators.comfyui)
    assert backend.availability().available
    # A bound socket which never listens reliably refuses connections without assuming a free port.
    import socket

    with socket.socket() as blocked:
        blocked.bind(("127.0.0.1", 0))
        backend.settings.url = f"http://127.0.0.1:{blocked.getsockname()[1]}"
        availability = backend.availability()
    assert not availability.available and "Start your ComfyUI server" in availability.reason


def test_ambiguous_inspection_never_guesses_positive_negative(tmp_path):
    workflow = graph()
    del workflow["s"]
    path = tmp_path / "api.json"
    path.write_text(json.dumps(workflow), encoding="utf-8")
    result = inspect_workflow(path)
    assert "prompt" not in result["bind"] and len(result["candidates"]["prompt"]) == 2


@pytest.mark.parametrize(
    "bind",
    [
        {"prompt": ["p", "class_type", "x"]},
        {"prompt": ["p", "inputs", "text"], "seed": ["p", "inputs", "text"]},
        {"unknown": ["p", "inputs", "text"]},
    ],
)
def test_unsafe_bindings_rejected_in_configuration(bind):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ComfySettings.model_validate(
            {
                "workflows": {
                    "test": {
                        "file": "api.json",
                        "license": "test",
                        "commercial_use": "unknown",
                        "bind": bind,
                    }
                }
            }
        )


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/server",
        "http://user:secret@localhost:8188",
        "http://localhost:bad",
        "http://localhost:99999",
        "http://localhost:0",
        "http://localhost:8188?inject=true",
        "http://localhost:8188#fragment",
    ],
)
def test_invalid_server_urls_are_configuration_errors(url):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ComfySettings(url=url)
