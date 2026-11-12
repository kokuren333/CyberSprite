"""Schema artifact assembly outside the dependency-restricted core package."""

from cybersprite.core.canonical import json_bytes
from cybersprite.core.schemas import generate_schemas as core_schemas
from cybersprite.formats.sheet_models import sheet_schema
from cybersprite.ops import registry


def generate_schemas() -> dict[str, bytes]:
    schemas = core_schemas()
    schemas["sheet"] = json_bytes(sheet_schema())
    for op in registry().all():
        schemas[f"op.{op.name}"] = json_bytes(op.describe()["inputSchema"])
    return schemas
