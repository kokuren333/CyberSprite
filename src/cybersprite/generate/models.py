"""Human-only BYOW registration and plain-text license badges. No weight downloads."""

import json
from datetime import UTC, datetime
from pathlib import Path

from cybersprite.config import GenerationModel, UserConfig, config_path, load_config
from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.history import atomic_write
from cybersprite.core.source_terms import model_terms

from .licenses import fingerprint


def _snapshot(setting, alias, models, *, include_adapters=True):
    data = setting.model_dump()
    data["id"] = setting.id or alias
    data["bases"] = (
        [_snapshot(models[setting.base_model], setting.base_model, models, include_adapters=False)]
        if setting.base_model in models
        else []
    )
    data["adapters"] = (
        [
            _snapshot(adapter, f"{alias}:adapter:{i}", models)
            for i, adapter in enumerate(getattr(setting, "adapters", []))
        ]
        if include_adapters
        else []
    )
    return data


def term_badges(snapshot):
    result = []
    for info in model_terms(snapshot):
        license_name = info.get("license", "unknown")
        normalized = license_name.lower()
        commercial = info.get("commercial_use", "unknown")
        if commercial == "no" or "-nc" in normalized or "non-commercial" in normalized:
            badge = "non-commercial only"
        elif "openrail" in normalized:
            badge = "commercial OK with use restrictions (not OSI)"
        elif (
            normalized
            in {
                "apache-2.0",
                "mit",
                "bsd-2-clause",
                "bsd-3-clause",
                "isc",
                "zlib",
                "cc0-1.0",
                "unlicense",
            }
            and commercial == "yes"
        ):
            badge = "commercial OK"
        else:
            badge = "needs review"
        result.append(
            {
                "id": info.get("id", "unknown"),
                "license": license_name,
                "commercial_use": commercial,
                "badge": badge,
                "message": f"{info.get('id', 'unknown')}: {badge}; commercial_use={commercial}. "
                "Review adapter and base terms together.",
            }
        )
    return result


def register_model(
    path,
    *,
    name,
    kind,
    base_model="unknown",
    license,
    license_url="",
    commercial_use="unknown",
    source_url="",
    note="",
):
    settings = load_config()
    if not name.strip() or name == "unknown":
        raise invalid("Choose a non-empty model name other than the reserved name 'unknown'.")
    if name in settings.generators.diffusers.models:
        raise CyberSpriteError(
            "E_EXISTS",
            f"Model {name!r} is already registered.",
            "Choose a new name or edit its registration in config.toml.",
        )
    if base_model != "unknown" and base_model not in settings.generators.diffusers.models:
        raise invalid(
            "Register the base model first, or specify --base-model unknown.", base_model=base_model
        )
    local = Path(path).expanduser().resolve()
    if kind == "diffusers-dir" and not local.is_dir():
        raise invalid("A diffusers-dir model needs a local directory.", path=str(local))
    if kind != "diffusers-dir" and not local.is_file():
        raise invalid("This model kind needs a local file.", path=str(local))
    record = GenerationModel(
        display_name=name,
        kind=kind,
        base_model=base_model,
        local_path=str(local),
        license=license,
        license_url=license_url,
        commercial_use=commercial_use,
        source_url=source_url,
        note=note,
        sha256=fingerprint(local),
        registered_at=datetime.now(UTC).isoformat(),
    )
    destination = config_path()
    original = destination.read_text("utf-8") if destination.exists() else ""
    # Append a quoted TOML table; preserve every existing setting and comment.
    table = f"\n[generators.diffusers.models.{json.dumps(name, ensure_ascii=False)}]\n"
    table += "".join(
        f"{key} = {json.dumps(value, ensure_ascii=False)}\n"
        for key, value in record.model_dump(exclude={"id", "adapters"}).items()
    )
    import tomllib

    UserConfig.model_validate(tomllib.loads(original + table))
    atomic_write(destination, (original + table).encode("utf-8"))
    return {
        "name": name,
        **record.model_dump(),
        "badges": term_badges(_snapshot(record, name, settings.generators.diffusers.models)),
    }


def list_models():
    models = load_config().generators.diffusers.models
    result = []
    for alias in sorted(models):
        setting = models[alias]

        # Listing registered metadata does not read many GB of weights or require a GPU.
        result.append(
            {
                "name": alias,
                **setting.model_dump(),
                "badges": term_badges(_snapshot(setting, alias, models)),
            }
        )
    return {"models": result}
