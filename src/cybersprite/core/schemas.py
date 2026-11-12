"""Pydantic schema generation and byte-stable schema artifacts."""

from .canonical import json_bytes
from .models import Project, Sources


def generate_schemas() -> dict[str, bytes]:
    return {
        name: json_bytes(model.model_json_schema(by_alias=True))
        for name, model in (("project", Project), ("sources", Sources))
    }
