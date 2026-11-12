"""Content-bound license acceptance for user-managed local model files."""

import hashlib
import json
from pathlib import Path

from cybersprite.config import config_path
from cybersprite.core.canonical import metadata_bytes
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.history import atomic_write

from .contracts import ModelInfo


def fingerprint(path):
    if not path:
        raise CyberSpriteError(
            "E_BACKEND_UNAVAILABLE",
            "No local model path was configured.",
            "Set local_path to the downloaded model or adapter files in user config.toml.",
        )
    path = Path(path).expanduser().resolve()
    if path.is_file():
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    if path.is_dir():
        digest = hashlib.sha256(b"CSMODEL1\n")
        files = sorted(
            (p for p in path.rglob("*") if p.is_file()),
            key=lambda p: p.relative_to(path).as_posix(),
        )
        if files:
            for file in files:
                digest.update(file.relative_to(path).as_posix().encode("utf-8") + b"\0")
                with file.open("rb") as stream:
                    digest.update(hashlib.file_digest(stream, "sha256").digest())
            return digest.hexdigest()
    raise CyberSpriteError(
        "E_BACKEND_UNAVAILABLE",
        f"No model files at {path}.",
        "Download the model yourself and set its local_path in user config.toml.",
    )


def model_info(setting, alias, base_model=None, registered=None, visited=(), include_adapters=True):
    if alias in visited:
        from cybersprite.core.errors import invalid

        raise invalid(
            "Cyclic model or adapter reference; repair base_model in config.toml.", model=alias
        )
    path = Path(setting.local_path).expanduser() if setting.local_path else None
    if path is not None and not path.is_absolute():
        path = config_path().parent / path
    digest = fingerprint(path) if path is not None else ""
    return ModelInfo(
        id=setting.id or alias,
        license=setting.license,
        alias=alias,
        source_url=setting.source_url,
        local_path=str(path.resolve()) if path is not None else "",
        sha256=digest,
        base_model=setting.base_model
        if setting.base_model != "unknown"
        else base_model or "unknown",
        display_name=setting.display_name or alias,
        kind=setting.kind,
        license_url=setting.license_url,
        commercial_use=setting.commercial_use,
        note=setting.note,
        registered_at=setting.registered_at,
        bases=[
            model_info(
                registered[setting.base_model],
                setting.base_model,
                registered=registered,
                visited=(*visited, alias),
                include_adapters=False,
            )
        ]
        if registered and setting.base_model in registered
        else [],
        adapters=[
            model_info(a, f"{alias}:adapter:{i}", alias, registered)
            for i, a in enumerate(getattr(setting, "adapters", []))
        ]
        if include_adapters
        else [],
    )


def records():
    path = config_path().with_name("models.json")
    try:
        value = json.loads(path.read_bytes()) if path.exists() else {"models": []}
        if not isinstance(value, dict) or not isinstance(value.get("models"), list):
            raise ValueError("expected a models array")
        for row in value["models"]:
            if (
                not isinstance(row, dict)
                or set(row) != {"id", "license", "sha256"}
                or not all(isinstance(v, str) for v in row.values())
            ):
                raise ValueError("each acceptance must contain id, license and sha256 strings")
        return value
    except (OSError, ValueError) as error:
        raise CyberSpriteError(
            "E_IO",
            f"Cannot read model acceptances: {error}",
            "Repair models.json in the user configuration directory.",
        ) from error


def identities(model):
    values = []
    for info in all_models(model):
        row = {"id": info.id, "license": info.license, "sha256": info.sha256}
        if row not in values:
            values.append(row)
    return values


def all_models(model):
    yield model
    for child in [*model.adapters, *model.bases]:
        yield from all_models(child)


def require_license(model, *, accept=False):
    required = identities(model)
    if any(not r["sha256"] or not r["license"].strip() for r in required):
        raise CyberSpriteError(
            "E_BACKEND_UNAVAILABLE",
            "Model or adapter files are missing.",
            "Configure local_path and license for the base and every adapter.",
        )
    data = records()
    missing = [r for r in required if r not in data["models"]]
    if missing and not accept:
        raise CyberSpriteError(
            "E_LICENSE_NOT_ACCEPTED",
            "Model license acceptance is required: "
            + "; ".join(f"{r['id']}: {r['license']}" for r in missing),
            "Review the model and adapter terms, then use gen accept-license or "
            "--accept-model-license.",
            {"models": missing},
        )
    if missing:
        data["models"].extend(missing)
        data["models"].sort(key=lambda r: (r["id"], r["license"], r["sha256"]))
        atomic_write(config_path().with_name("models.json"), metadata_bytes(data))
