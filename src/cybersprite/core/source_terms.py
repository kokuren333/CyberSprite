"""Read immutable generation terms from source provenance, independent of user config."""


def model_terms(model):
    """Flatten a model snapshot, including unknown adapter bases for review."""
    if not isinstance(model, dict):
        return []
    result = [model]
    for key in ("adapters", "bases"):
        for child in model.get(key, []):
            result.extend(model_terms(child))
    if (
        model.get("kind") in {"lora", "vae", "controlnet"}
        and not model.get("bases")
        and model.get("base_model", "unknown") == "unknown"
    ):
        result.append(
            {
                "id": f"{model.get('id', 'adapter')}:unknown-base",
                "license": "unknown",
                "commercial_use": "unknown",
            }
        )
    return result


def source_terms(source):
    snapshot = source.params.get("model_registry")
    if snapshot is None and source.model is not None:
        snapshot = source.model.model_dump()
    return model_terms(snapshot)
