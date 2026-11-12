"""Registered ComfyUI HTTP workflows. No server code or third-party graphs are bundled."""

import hashlib
import json
import secrets
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from pydantic import Field, ValidationError

from cybersprite.config import config_path
from cybersprite.core.canonical import metadata_bytes
from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.models import Model

from .contracts import Availability, GeneratedImage, ModelInfo
from .licenses import require_license


def local_workflow(file):
    path = Path(file).expanduser()
    return (path if path.is_absolute() else config_path().parent / path).resolve()


def read_workflow(file):
    path = local_workflow(file)
    try:
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("workflow exceeds 8 MiB")
        data = path.read_bytes()
        workflow = json.loads(data)
        if not isinstance(workflow, dict) or not workflow:
            raise ValueError("expected a non-empty API-format node object")
        for node in workflow.values():
            if (
                not isinstance(node, dict)
                or not isinstance(node.get("class_type"), str)
                or not isinstance(node.get("inputs"), dict)
            ):
                raise ValueError(
                    "each API node needs class_type and inputs; editor-format JSON is unsupported"
                )
        return workflow, hashlib.sha256(data).hexdigest()
    except (OSError, ValueError, RecursionError) as error:
        raise invalid(
            "Cannot read API workflow; export API-format JSON and repair its configured file.",
            file=str(path),
            reason=str(error),
        ) from error


def inspect_workflow(file):
    workflow, digest = read_workflow(file)
    candidates = {
        key: []
        for key in (
            "prompt",
            "negative_prompt",
            "seed",
            "width",
            "height",
            "steps",
            "cfg",
            "checkpoint",
            "lora",
        )
    }
    mapping = {
        "KSampler": {"seed": "seed", "steps": "steps", "cfg": "cfg"},
        "EmptyLatentImage": {"width": "width", "height": "height"},
        "CheckpointLoaderSimple": {"checkpoint": "ckpt_name"},
        "LoraLoader": {"lora": "lora_name"},
    }
    for node_id in sorted(workflow):
        node = workflow[node_id]
        for param, key in mapping.get(node["class_type"], {}).items():
            if key in node["inputs"]:
                candidates[param].append([node_id, "inputs", key])
        if node["class_type"] == "CLIPTextEncode" and "text" in node["inputs"]:
            for param in ("prompt", "negative_prompt"):
                candidates[param].append([node_id, "inputs", "text"])
    bind = {}
    for param in ("prompt", "negative_prompt"):
        connection = "positive" if param == "prompt" else "negative"
        linked = []
        for node_id in sorted(workflow):
            node = workflow[node_id]
            target = node["inputs"].get(connection)
            if (
                node["class_type"] == "KSampler"
                and isinstance(target, list)
                and len(target) == 2
                and str(target[0]) in workflow
            ):
                target_node = workflow[str(target[0])]
                if (
                    target_node["class_type"] == "CLIPTextEncode"
                    and "text" in target_node["inputs"]
                ):
                    path = [str(target[0]), "inputs", "text"]
                    if path not in linked:
                        linked.append(path)
        if len(linked) == 1:
            bind[param] = linked[0]
    for param in candidates:
        if param not in {"prompt", "negative_prompt"} and len(candidates[param]) == 1:
            bind[param] = candidates[param][0]
    # An ambiguous prompt must never silently overwrite the negative text.
    return {
        "sha256": digest,
        "bind": bind,
        "candidates": candidates,
        "message": "Suggestions only. Review every binding, model license and custom node "
        "before registering this workflow in config.toml.",
    }


class ComfyParams(Model):
    steps: int | None = Field(None, ge=1, le=1000)
    cfg: int | None = Field(None, ge=0, le=100)
    checkpoint: str | None = Field(None, min_length=1)
    lora: str | None = Field(None, min_length=1)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ComfyUIBackend:
    name = "comfyui"
    params_schema = ComfyParams

    def __init__(self, settings):
        self.settings = settings

    def _request(self, route, *, body=None, deadline=None, binary=False):
        timeout = self.settings.request_timeout_seconds
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise self._timeout()
            timeout = min(timeout, remaining)
        request = Request(
            self.settings.url + route,
            data=metadata_bytes(body) if body is not None else None,
            headers={
                "Content-Type": "application/json",
                "Accept": "image/*" if binary else "application/json",
            },
        )
        try:
            with build_opener(ProxyHandler({}), NoRedirect()).open(
                request, timeout=timeout
            ) as response:
                limit = (64 if binary else 8) * 1024 * 1024
                if int(response.headers.get("Content-Length", "0")) > limit:
                    raise ValueError(f"response exceeds {limit} bytes")
                data = bytearray()
                while True:
                    if deadline is not None and time.monotonic() >= deadline:
                        raise self._timeout()
                    chunk = response.read1(min(65536, limit + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                    if len(data) > limit:
                        raise ValueError(f"response exceeds {limit} bytes")
            if deadline is not None and time.monotonic() >= deadline:
                raise self._timeout()
            if binary:
                return bytes(data)
            value = json.loads(data)
            if not isinstance(value, dict):
                raise ValueError("expected a JSON object")
            return value
        except TimeoutError as error:
            raise self._timeout() from error
        except HTTPError as error:
            raise CyberSpriteError(
                "E_GENERATION_FAILED",
                f"ComfyUI HTTP {error.code} for {route}.",
                "Check the server log, workflow bindings and installed nodes; "
                "redirects are not followed.",
                {"status": error.code, "route": route},
            ) from error
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise self._timeout() from error
            raise CyberSpriteError(
                "E_BACKEND_UNAVAILABLE",
                f"Cannot reach ComfyUI at {self.settings.url}: {error.reason}",
                "Start your ComfyUI server or repair generators.comfyui.url in config.toml.",
            ) from error
        except (OSError, ValueError, RecursionError) as error:
            raise CyberSpriteError(
                "E_GENERATION_FAILED",
                f"Invalid ComfyUI response for {route}: {error}",
                "Check the server and registered workflow; retry after repairing the response.",
            ) from error

    def _timeout(self):
        return CyberSpriteError(
            "E_TIMEOUT",
            "ComfyUI generation or HTTP request timed out.",
            "Inspect the ComfyUI queue before retrying; the submitted job may still be running. "
            "Increase configured timeouts if needed.",
        )

    def selected_model(self, alias=None):
        if alias not in self.settings.workflows:
            raise invalid(
                "Select a registered ComfyUI workflow using model; "
                "arbitrary workflow JSON is forbidden.",
                candidates=sorted(self.settings.workflows),
            )
        setting = self.settings.workflows[alias]
        _, digest = read_workflow(setting.file)
        return ModelInfo(
            id="comfyui:" + alias,
            alias=alias,
            display_name=alias,
            license=setting.license,
            commercial_use=setting.commercial_use,
            local_path=str(local_workflow(setting.file)),
            sha256=digest,
            kind="workflow",
        )

    def list_models(self):
        result = []
        for alias in sorted(self.settings.workflows):
            try:
                result.append(self.selected_model(alias))
            except CyberSpriteError as error:
                setting = self.settings.workflows[alias]
                result.append(
                    ModelInfo(
                        id="comfyui:" + alias,
                        alias=alias,
                        license=setting.license,
                        commercial_use=setting.commercial_use,
                        kind="workflow",
                        note=error.message,
                    )
                )
        return result

    def availability(self):
        if not self.settings.workflows:
            return Availability(
                available=False, reason="No ComfyUI workflows registered in config.toml."
            )
        try:
            self._request("/system_stats")
            return Availability(available=True)
        except CyberSpriteError as error:
            return Availability(available=False, reason=error.message + " " + error.hint)

    def checked(self, request):
        try:
            params = self.params_schema.model_validate(request.params).model_dump(exclude_none=True)
        except ValidationError as error:
            raise invalid(
                "Only bound ComfyUI steps, cfg, checkpoint and lora parameters are allowed.",
                issues=error.errors(include_context=False, include_input=False),
            ) from error
        model = self.selected_model(request.model)
        setting = self.settings.workflows[request.model]
        required = {"prompt", "seed", "width", "height"} | set(params)
        if request.negative_prompt:
            required.add("negative_prompt")
        missing = sorted(required - set(setting.bind))
        if missing:
            raise invalid(
                "Register bindings for every requested ComfyUI parameter before generating.",
                missing_bindings=missing,
            )
        workflow, digest = read_workflow(setting.file)
        if digest != model.sha256:
            raise invalid("Workflow changed during selection; keep the file unchanged and retry.")
        for param in sorted(setting.bind):
            node, _, key = setting.bind[param]
            if (
                node not in workflow
                or key not in workflow[node]["inputs"]
                or isinstance(workflow[node]["inputs"][key], (list, dict))
            ):
                raise invalid(
                    "Binding must target an existing scalar workflow input, not a node connection.",
                    parameter=param,
                    binding=setting.bind[param],
                )
        require_license(model, accept=request.accept_model_license)
        return model, params

    def generate(self, request, out_dir, progress):
        model, params = self.checked(request)
        setting = self.settings.workflows[request.model]
        workflow, digest = read_workflow(setting.file)
        if digest != model.sha256:
            raise invalid("Workflow changed after license acceptance; review and retry.")
        seed = request.seed if request.seed is not None else secrets.randbits(63)
        values = {
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "width": request.width,
            "height": request.height,
            "seed": seed,
            **params,
        }
        actual = {}
        for param in sorted(setting.bind):
            node, _, key = setting.bind[param]
            if param in values:
                workflow[node]["inputs"][key] = values[param]
            actual[param] = workflow[node]["inputs"][key]
        filled = metadata_bytes(workflow)
        deadline = time.monotonic() + self.settings.timeout_seconds
        submitted = self._request("/prompt", body={"prompt": workflow}, deadline=deadline)
        prompt_id = submitted.get("prompt_id")
        if (
            submitted.get("error")
            or submitted.get("node_errors")
            or not isinstance(prompt_id, str)
            or not prompt_id
        ):
            raise CyberSpriteError(
                "E_GENERATION_FAILED",
                "ComfyUI rejected the registered workflow.",
                "Check the server log, missing nodes and registered input bindings.",
                {"response": submitted},
            )
        route = "/history/" + quote(prompt_id, safe="")
        while True:
            history = self._request(route, deadline=deadline)
            item = history.get(prompt_id)
            if item is not None:
                if not isinstance(item, dict):
                    raise invalid("ComfyUI history item must be an object.")
                status = item.get("status", {})
                if isinstance(status, dict) and status.get("status_str") == "error":
                    raise CyberSpriteError(
                        "E_GENERATION_FAILED",
                        "ComfyUI workflow execution failed.",
                        "Read the ComfyUI execution error and repair the registered workflow.",
                        {"status": status},
                    )
                if "outputs" in item and (not status or status.get("completed")):
                    break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise self._timeout()
            time.sleep(min(self.settings.poll_interval_ms / 1000, remaining))
        outputs = item["outputs"]
        if not isinstance(outputs, dict):
            raise invalid("ComfyUI history outputs must be an object.")
        descriptors = []
        for node in sorted(outputs):
            output = outputs[node]
            if not isinstance(output, dict) or not isinstance(output.get("images", []), list):
                raise invalid("ComfyUI image output must contain an images array.")
            descriptors.extend(output.get("images", []))
        if len(descriptors) != request.count:
            raise CyberSpriteError(
                "E_GENERATION_FAILED",
                f"ComfyUI returned {len(descriptors)} images; expected {request.count}.",
                "Configure the registered workflow batch size and image outputs to match count.",
            )
        result = []
        for index, image in enumerate(descriptors):
            if (
                not isinstance(image, dict)
                or not isinstance(image.get("filename"), str)
                or not image["filename"]
                or any(
                    not isinstance(image.get(key, default), str)
                    for key, default in (("subfolder", ""), ("type", "output"))
                )
            ):
                raise invalid(
                    "ComfyUI image descriptor needs filename, subfolder and type strings."
                )
            query = urlencode(
                {
                    "filename": image["filename"],
                    "subfolder": image.get("subfolder", ""),
                    "type": image.get("type", "output"),
                }
            )
            data = self._request("/view?" + query, deadline=deadline, binary=True)
            # The server filename is never used as a local path.
            path = out_dir / f"output_{index:04d}.png"
            path.write_bytes(data)
            result.append(
                GeneratedImage(
                    path=path,
                    seed=seed,
                    model=model,
                    params={
                        **actual,
                        "workflow_sha256": hashlib.sha256(filled).hexdigest(),
                        "workflow_file_sha256": model.sha256,
                        "server_url": self.settings.url,
                        "workflow_license": setting.license,
                    },
                    workflow=workflow,
                )
            )
        progress(1, "ComfyUI generation completed.")
        return result
