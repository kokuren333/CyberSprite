"""Single-source operation contracts, shared by all surfaces and plugins."""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, create_model

from .errors import CyberSpriteError, invalid
from .models import Model, Project


@dataclass
class OpContext:
    project: Project
    root: Path
    linked_frames: set[int] = field(default_factory=set)
    clipped_pixels: int = 0
    prepared: object = None
    side_writes: list = field(default_factory=list)
    source_manifest: object = None
    previous_source_manifest: object = None
    warnings: list = field(default_factory=list)


@dataclass(frozen=True)
class Op:
    name: str
    args: type[BaseModel]
    apply: Callable
    result: type[BaseModel]
    kind: Literal["mutate", "query", "export", "ingest"] = "mutate"
    idempotency: Literal["R", "I", "C", "N", "E", "G"] = "I"
    destructive: bool = False
    description: str = ""
    provider: str = "builtin"

    def parse(self, values: dict) -> BaseModel:
        try:
            return self.args.model_validate(values)
        except ValidationError as error:
            issues = error.errors(include_context=False, include_input=False)
            for issue in issues:
                location = issue["loc"]
                resource_limit = (
                    issue["type"] == "string_too_long"
                    and location[0] in ("name", "layer_name")
                    or issue["type"] == "too_long"
                    and location[0] in ("ops", "pixels", "points", "frames")
                    or issue["type"] == "less_than_equal"
                    and (location[0] in ("scale", "factor") or "size" in location)
                )
                if resource_limit:
                    raise CyberSpriteError(
                        "E_LIMIT_EXCEEDED",
                        f"Resource limit exceeded for {self.name}.",
                        "Reduce the indicated size, name length, or item count.",
                        {"issues": issues},
                    ) from error
            raise invalid(
                f"Invalid arguments for {self.name}.",
                issues=issues,
            ) from error

    @property
    def annotations(self) -> dict:
        return {
            "readOnlyHint": self.idempotency == "R",
            "idempotentHint": self.idempotency in "RICE",
            "destructiveHint": self.destructive,
            "openWorldHint": self.idempotency == "G",
        }

    def describe(self) -> dict:
        input_fields: dict[str, Any] = {
            "project": (str, Field(description="Project directory or project.json path."))
        }
        if self.kind in ("mutate", "ingest"):
            input_fields.update(
                {
                    "expect_revision": (
                        int | None,
                        Field(None, description="Reject if the current revision differs."),
                    ),
                    "idempotency_key": (
                        str | None,
                        Field(
                            None,
                            min_length=1,
                            max_length=64,
                            description="Replay a prior result for this transaction key.",
                        ),
                    ),
                    "dry_run": (
                        bool,
                        Field(False, description="Validate without committing project changes."),
                    ),
                    "preview": (
                        Literal["none", "path", "inline"],
                        Field(
                            "path",
                            description="Return no preview, PNG paths, or inline PNG images.",
                        ),
                    ),
                }
            )
        input_model = create_model(self.name + "Input", __base__=self.args, **input_fields)
        output_fields: dict[str, Any] = {
            "ok": (bool, ...),
            "op": (str, ...),
            "project": (str, ...),
            "revision": (int | dict[str, int], ...),
            "result": (self.result, ...),
            "warnings": (list[dict], Field(default_factory=lambda: [])),
        }
        if self.kind in ("mutate", "ingest") and self.name not in (
            "new_project",
            "import_aseprite",
            "generate_image",
        ):
            output_fields.update(
                {
                    "no_op": (bool, ...),
                    "replayed": (bool, ...),
                    "dry_run": (bool, ...),
                    "changed": (dict, ...),
                    "validation": (dict, ...),
                    "preview": (dict, ...),
                    "would_commit": (bool | None, None),
                }
            )
        output_model = create_model(self.name + "Output", __base__=Model, **output_fields)
        output_schema = output_model.model_json_schema(by_alias=True)
        if self.kind == "ingest":
            # A gate rejection keeps originals and a report but performs no mutation.
            output_schema["required"] = [
                key
                for key in output_schema["required"]
                if key in {"ok", "op", "project", "revision", "result"}
            ]
        return {
            "name": self.name,
            "title": self.name.replace("_", " ").title(),
            "description": self.description,
            "kind": self.kind,
            "idempotency": self.idempotency,
            "provider": self.provider,
            "annotations": self.annotations,
            "inputSchema": input_model.model_json_schema(by_alias=True),
            "outputSchema": output_schema,
            "resultSchema": self.result.model_json_schema(by_alias=True),
        }


class Registry:
    def __init__(self):
        self._ops: dict[str, Op] = {}

    def register(self, op: Op) -> None:
        if op.name in self._ops:
            raise invalid("Operation is already registered.", op=op.name)
        self._ops[op.name] = op

    def get(self, name: str) -> Op:
        if name not in self._ops:
            raise CyberSpriteError(
                "E_UNKNOWN_OP",
                f"Unknown operation {name!r}.",
                "Use ops list to find a registered operation.",
                {"candidates": get_close_matches(name, sorted(self._ops))},
            )
        return self._ops[name]

    def all(self) -> list[Op]:
        return [self._ops[name] for name in sorted(self._ops)]

    def load_plugins(self, *, enabled: bool = False) -> None:
        """Opt-in entry points; MCP must independently allowlist plugin names."""
        if enabled:
            from importlib.metadata import entry_points

            for entry in sorted(entry_points(group="cybersprite.ops"), key=lambda e: e.name):
                try:
                    for op in entry.load()():
                        self.register(replace(op, provider=entry.name))
                except Exception as error:
                    raise CyberSpriteError(
                        "E_PLUGIN",
                        f"Cannot load operation plugin {entry.name}: {error}",
                        "Repair or disable this plugin before loading it again.",
                        {"plugin": entry.name},
                    ) from error


class EmptyResult(Model):
    pass
