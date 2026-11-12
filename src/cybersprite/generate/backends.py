"""Configured shell-free commands and optional, lazily imported Diffusers."""

import importlib
import secrets
import shutil
import subprocess
from pathlib import Path

import numpy as np
from pydantic import Field, ValidationError

from cybersprite.config import config_path
from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.models import Model
from cybersprite.formats.png import encode_png

from .contracts import Availability, GeneratedImage
from .licenses import model_info, require_license


class CommandParams(Model):
    """Command templates have no caller-defined arguments."""


class DiffusersParams(Model):
    num_inference_steps: int = Field(30, ge=1, le=1000, description="Denoising step count.")
    guidance_scale: int = Field(7, ge=0, le=100, description="Integer guidance scale.")


class ConfiguredBackend:
    def selected_model(self, alias=None):
        models = self.settings.models
        alias = alias if alias is not None else next(iter(sorted(models)), None)
        if not models:
            raise CyberSpriteError(
                "E_BACKEND_UNAVAILABLE",
                "No model configured in user config.toml.",
                "Register a model with id, local_path and license before generating.",
            )
        if alias not in models:
            raise invalid("Select a configured model alias.", candidates=sorted(models))
        return model_info(models[alias], alias)

    def list_models(self):
        result = []
        for alias in sorted(self.settings.models):
            setting = self.settings.models[alias]
            try:
                info = model_info(setting, alias)
            except CyberSpriteError:
                from .contracts import ModelInfo

                info = ModelInfo(
                    id=setting.id or alias,
                    license=setting.license,
                    alias=alias,
                    local_path=setting.local_path or "",
                    source_url=setting.source_url,
                )
            result.append(info)
        return result

    def model_availability(self):
        if not self.settings.models:
            return Availability(available=False, reason="No model configured in user config.toml.")
        reasons = []
        for alias in sorted(self.settings.models):
            try:
                require_license(self.selected_model(alias))
                return Availability(available=True)
            except CyberSpriteError as error:
                reasons.append(f"{alias}: {error.message}")
        return Availability(available=False, reason="; ".join(reasons))

    def checked(self, request):
        from cybersprite.config import reject_tool_configuration

        reject_tool_configuration(request.params)
        try:
            params = self.params_schema.model_validate(request.params)
        except ValidationError as error:
            raise invalid(
                "Invalid backend parameters.",
                issues=error.errors(include_context=False, include_input=False),
            ) from error
        model = self.selected_model(request.model)
        require_license(model, accept=request.accept_model_license)
        return model, params.model_dump()


class CommandBackend(ConfiguredBackend):
    params_schema = CommandParams

    def __init__(self, name, settings):
        from types import SimpleNamespace

        self.name = "command:" + name
        self.command = settings
        self.settings = SimpleNamespace(models={name: settings.model} if settings.model else {})
        program = Path(settings.program).expanduser()
        if not program.is_absolute() and len(program.parts) > 1:
            program = config_path().parent / program
        self.program = str(program)

    def template_hash(self):
        from hashlib import sha256

        from cybersprite.core.canonical import metadata_bytes

        return sha256(
            metadata_bytes({"program": self.program, "args": self.command.args})
        ).hexdigest()

    def availability(self):
        if not shutil.which(self.program):
            return Availability(
                available=False, reason=f"Command executable not found: {self.program}"
            )
        return self.model_availability()

    def generate(self, request, out_dir, progress):
        model, params = self.checked(request)
        seed = request.seed if request.seed is not None else secrets.randbits(63)
        values = dict(
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            width=request.width,
            height=request.height,
            seed=seed,
            count=request.count,
            out=str(out_dir / "output.png"),
        )
        command = [self.program, *(arg.format_map(values) for arg in self.command.args)]
        progress(0, "Starting configured command.")
        try:
            # Files bound subprocess output memory; external output never becomes instructions.
            with (
                (out_dir / "stdout.log").open("wb") as stdout,
                (out_dir / "stderr.log").open("wb") as stderr,
            ):
                result = subprocess.run(
                    command,
                    shell=False,
                    cwd=out_dir,
                    stdout=stdout,
                    stderr=stderr,
                    timeout=self.command.timeout_seconds,
                    check=False,
                )
        except subprocess.TimeoutExpired as error:
            raise CyberSpriteError(
                "E_TIMEOUT",
                "Generation command exceeded its timeout.",
                "Increase timeout_seconds in user config.toml or reduce work.",
            ) from error
        except OSError as error:
            raise CyberSpriteError(
                "E_BACKEND_UNAVAILABLE",
                f"Cannot start command: {error}",
                "Check program and permissions in user config.toml.",
            ) from error
        if result.returncode:
            with (out_dir / "stderr.log").open("rb") as stream:
                reason = stream.read(4096).decode("utf-8", errors="replace")
            raise CyberSpriteError(
                "E_GENERATION_FAILED",
                "Generation command failed.",
                "Repair the configured command and retry.",
                {"returncode": result.returncode, "stderr": reason},
            )
        paths = sorted(
            (
                p
                for p in out_dir.rglob("*")
                if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
            ),
            key=lambda p: p.relative_to(out_dir).as_posix(),
        )
        if len(paths) != request.count:
            raise CyberSpriteError(
                "E_GENERATION_FAILED",
                "Command output count does not match count.",
                "Write exactly count raster files under the supplied out directory.",
                {"expected": request.count, "found": len(paths)},
            )
        progress(1, "Command completed.")
        return [
            GeneratedImage(
                path=p,
                seed=seed,
                model=model,
                params={
                    **params,
                    "count": request.count,
                    "timeout_seconds": self.command.timeout_seconds,
                    "command_template_sha256": self.template_hash(),
                },
            )
            for p in paths
        ]


class DiffusersBackend(ConfiguredBackend):
    name = "diffusers"
    params_schema = DiffusersParams

    def __init__(self, settings):
        self.settings = settings

    def runtime(self):
        try:
            torch = importlib.import_module("torch")
            diffusers = importlib.import_module("diffusers")
        except (ImportError, OSError) as error:
            raise CyberSpriteError(
                "E_BACKEND_UNAVAILABLE",
                "Diffusers extra is not installed or usable.",
                "See docs/GENERATION.md for the pending optional dependency audit; "
                "use a configured command backend until the GPU stack is approved.",
            ) from error
        if not torch.cuda.is_available():
            raise CyberSpriteError(
                "E_BACKEND_UNAVAILABLE",
                "No supported CUDA GPU is available.",
                "Use command generation or import an agent-generated image.",
            )
        return torch, diffusers

    def availability(self):
        try:
            self.runtime()
        except CyberSpriteError as error:
            return Availability(available=False, reason=error.message)
        return self.model_availability()

    def generate(self, request, out_dir, progress):
        model, params = self.checked(request)
        torch, diffusers = self.runtime()
        seed = request.seed if request.seed is not None else secrets.randbits(63)
        try:
            progress(0, "Loading local model.")
            location = Path(model.local_path)
            factory = (
                diffusers.StableDiffusionPipeline.from_single_file
                if location.is_file()
                else diffusers.AutoPipelineForText2Image.from_pretrained
            )
            pipe = factory(str(location), local_files_only=True, torch_dtype=torch.float16)
            for i, adapter in enumerate(model.adapters):
                path = Path(adapter.local_path)
                options = dict(local_files_only=True, adapter_name=f"adapter_{i}")
                if path.is_file():
                    options["weight_name"] = path.name
                    path = path.parent
                pipe.load_lora_weights(str(path), **options)
            if model.adapters:
                pipe.set_adapters([f"adapter_{i}" for i in range(len(model.adapters))])
            pipe = pipe.to("cuda")
            if hasattr(pipe, "set_progress_bar_config"):
                pipe.set_progress_bar_config(disable=True)
            generator = torch.Generator(device="cuda").manual_seed(seed)
            result = pipe(
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                width=request.width,
                height=request.height,
                num_images_per_prompt=request.count,
                generator=generator,
                **params,
            )
            images = []
            for i, image in enumerate(result.images):
                pixels = np.asarray(image.convert("RGBA"), dtype=np.uint8)
                path = out_dir / f"output_{i:04d}.png"
                path.write_bytes(encode_png(pixels, compression="stored"))
                images.append(GeneratedImage(path=path, seed=seed, model=model, params=params))
            progress(1, "Generation completed.")
            return images
        except CyberSpriteError:
            raise
        except Exception as error:
            raise CyberSpriteError(
                "E_GENERATION_FAILED",
                f"Diffusers generation failed: {error}",
                "Check local model format, adapters and GPU memory.",
            ) from error
