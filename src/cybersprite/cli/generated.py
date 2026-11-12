"""Lazy commands derived from registered Pydantic argument schemas."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import click


def unsupported(feature, milestone, install=None):
    from cybersprite.core.errors import CyberSpriteError

    hint = f"{feature} requires {milestone}; use a build that includes that milestone."
    if install:
        hint += f" Install {install}."
    raise CyberSpriteError("E_UNSUPPORTED", f"{feature} is not available in this build.", hint)


def optional_function(module, function, milestone, install=None):
    try:
        imported = importlib.import_module(module)
        callback = getattr(imported, function, None)
        if callback is None:
            unsupported(module, milestone, install)
        return callback
    except ImportError as error:
        try:
            unsupported(module, milestone, install)
        except Exception as problem:
            raise problem from error


def variants(schema, definitions):
    if "$ref" in schema:
        return variants(definitions[schema["$ref"].rsplit("/", 1)[1]], definitions)
    if "anyOf" in schema or "oneOf" in schema:
        return [
            value
            for part in schema.get("anyOf", schema.get("oneOf", []))
            for value in variants(part, definitions)
            if value.get("type") != "null"
        ]
    return [schema]


class SchemaValue(click.ParamType):
    name = "VALUE"

    def __init__(self, schema, definitions):
        self.definitions = definitions
        self.schemas = variants(schema, definitions)

    def convert(self, value, param, ctx):
        if not isinstance(value, str):
            return value
        types = {item.get("type") for item in self.schemas}
        if types == {"string"}:
            return value
        if "integer" in types:
            try:
                return int(value)
            except ValueError:
                pass
        if value.startswith(("[", "{")) or value == "null":
            try:
                return json.loads(value)
            except ValueError:
                self.fail("Use valid JSON for arrays and objects.", param, ctx)
        if "object" in types:
            for schema in self.schemas:
                keys = set(schema.get("properties", {}))
                if {"cell_w", "cell_h"} <= keys:
                    sizes = value.lower().split("x")
                    if len(sizes) == 2 and all(part.isdecimal() for part in sizes):
                        return {"cell_w": int(sizes[0]), "cell_h": int(sizes[1])}
                if {"prev", "next"} <= keys:
                    try:
                        parts = [int(item) for item in value.split(",")]
                        if len(parts) == 2:
                            return dict(zip(("prev", "next"), parts, strict=True))
                    except ValueError:
                        pass
                if keys == {"x", "y", "w", "h"}:
                    try:
                        parts = [int(item) for item in value.split(",")]
                        if len(parts) == 4:
                            return dict(zip(("x", "y", "w", "h"), parts, strict=True))
                    except ValueError:
                        pass
        if "array" in types and ("string" not in types or "," in value):
            schema = next(item for item in self.schemas if item.get("type") == "array")
            item_type = SchemaValue(schema.get("items", {}), self.definitions)
            return [item_type.convert(item, param, ctx) for item in value.split(",")]
        if "string" in types:
            return value
        self.fail(
            "Use an integer, comma-separated list, or JSON matching ops describe.", param, ctx
        )


def schema_options(definition, *, skip=(), aliases=None, defaults=None):
    schema = definition.args.model_json_schema(by_alias=True)
    aliases, defaults = aliases or {}, defaults or {}
    options = []
    for name, field in schema["properties"].items():
        if name in skip:
            continue
        flags = aliases.get(
            name,
            ["--sheet", "--sheet-cell"] if name == "sheet" else ["--" + name.replace("_", "-")],
        )
        types = variants(field, schema.get("$defs", {}))
        boolean = len(types) == 1 and types[0].get("type") == "boolean"
        if boolean:
            flags = [f"{flags[0]}/--no-{flags[0][2:]}"]
        options.append(
            click.Option(
                [*flags, name],
                type=bool if boolean else SchemaValue(field, schema.get("$defs", {})),
                default=defaults.get(name),
                required=name in schema.get("required", []) and name not in defaults,
                help=field.get("description", f"Op argument: {name}.")
                + (f" Default: {field['default']}." if "default" in field else ""),
            )
        )
    return options


def transaction_options():
    return [
        click.Option(["--dry-run"], is_flag=True, default=None),
        click.Option(["--expect-revision"], type=int, default=None),
        click.Option(["--idempotency-key"], default=None),
        click.Option(["--preview"], type=click.Choice(["none", "path", "inline"]), default=None),
    ]


def dither_option():
    return click.Option(["--dither"], type=click.Choice(["none", "bayer2", "bayer4", "bayer8"]))


def normalize_pipeline_aliases(values):
    dither = values.pop("dither", None)
    if dither is not None:
        from cybersprite.core.errors import invalid

        pipeline = values.get("pipeline")
        if pipeline is not None and not isinstance(pipeline, dict):
            raise invalid("--pipeline must be a JSON object.")
        pipeline = dict(pipeline or {})
        if not isinstance(pipeline.get("dither", {}), dict):
            raise invalid("pipeline.dither must be an object with type and optional strength.")
        pipeline["dither"] = {**pipeline.get("dither", {}), "type": dither}
        values["pipeline"] = pipeline
    return values


def definition_or_none(name):
    from cybersprite.core.errors import CyberSpriteError
    from cybersprite.ops import registry

    try:
        return registry().get(name)
    except CyberSpriteError as error:
        if error.code != "E_UNKNOWN_OP":
            raise
        return None


def external_export(state, definition, path, args):
    from cybersprite.cli import _emit
    from cybersprite.core.registry import OpContext
    from cybersprite.formats.common import export_policy

    loader = optional_function("cybersprite.formats.input_adapter", "load_external", "M5")
    parsed = definition.parse(args)
    project = loader(Path(path), args.copy())
    context = OpContext(project, Path(path).resolve().parent)
    with export_policy(Path.cwd()):
        result = definition.apply(context, parsed)
    definition.result.model_validate(result)
    _emit(state, definition.name, result, project=str(path), revision=project.revision)


class RegistryGroup(click.Group):
    """Keep command discovery lazy; re-read the registry for every selected command."""

    def __init__(self, *args, routes, **kwargs):
        super().__init__(*args, **kwargs)
        self.routes = routes

    def list_commands(self, ctx):
        return sorted(self.routes)

    def format_commands(self, ctx, formatter):
        with formatter.section("Commands"):
            formatter.write_dl(
                [
                    (name, f"{op} ({milestone})")
                    for name, (op, milestone, _) in sorted(self.routes.items())
                ]
            )

    def get_command(self, ctx, cmd_name):
        if cmd_name not in self.routes:
            return None
        op, milestone, positional = self.routes[cmd_name]
        definition = definition_or_none(op)
        if definition is None:

            def missing(**_kwargs):
                click.get_current_context().obj["op"] = op
                unsupported(op, milestone)

            return click.Command(
                cmd_name,
                callback=missing,
                context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
                help=f"{op} is supplied by {milestone}.",
            )
        skip = [positional] if positional else []
        if op == "import_aseprite":
            skip.append("project")
        params = schema_options(definition, skip=skip)
        if op == "import_image" and "pipeline" in definition.args.model_fields:
            params.append(dither_option())
        if positional:
            params.insert(
                0,
                click.Argument(
                    [positional],
                    nargs=-1 if positional == "files" else 1,
                    required=positional != "files",
                ),
            )
        if definition.kind in {"mutate", "ingest"}:
            params.extend(transaction_options())
        if op == "load_palette":
            params.append(click.Option(["--append"], is_flag=True))
        if op == "import_aseprite":
            params.append(click.Option(["--out"], required=True, type=click.Path(path_type=Path)))
        if op.startswith("export_"):
            params.append(click.Option(["--input"], type=click.Path(path_type=Path)))

        def execute(**values):
            from cybersprite.cli import _run

            state = click.get_current_context().obj
            state["op"] = op
            if op == "import_image":
                normalize_pipeline_aliases(values)
            if positional == "files":
                values["files"] = list(values["files"]) or None
            if op == "load_palette" and values.pop("append"):
                values["mode"] = "append"
            if op == "import_aseprite":
                state["project"] = values.pop("out")
            external = values.pop("input", None) if op.startswith("export_") else None
            tx = {
                key: values.pop(key)
                for key in ("dry_run", "expect_revision", "idempotency_key", "preview")
                if key in values and values[key] is not None
            }
            args = {key: value for key, value in values.items() if value is not None}
            if external is not None:
                return external_export(state, definition, external, args)
            return _run(state, op, args, **tx)

        return click.Command(cmd_name, callback=execute, params=params, help=definition.description)


def read_command(name, op):
    from cybersprite.cli import _run
    from cybersprite.cli.output import protect_project_output

    definition = definition_or_none(op)
    aliases = {
        "format": ["--as", "--pixel-format"],
        "frames": ["--frame", "--frames"],
        "from_revision": ["--from", "--from-revision"],
        "to_revision": ["--to", "--to-revision"],
    }
    defaults = {"frame": 0} if name == "pixels" else {"frames": 0} if name == "preview" else {}
    params = schema_options(definition, aliases=aliases, defaults=defaults)
    if name in {"preview", "diff"}:
        params.append(click.Option(["--out"], type=click.Path(path_type=Path)))

    def invoke(**values):
        from cybersprite.core.errors import invalid

        state = click.get_current_context().obj
        out = values.pop("out", None)
        if out is not None:
            protect_project_output(state, out, directory=not out.suffix)
        args = {key: value for key, value in values.items() if value is not None}
        if name in {"preview", "diff"}:
            args.setdefault("inline", False)
        if name == "diff" and isinstance(args.get("frames"), int):
            args["frames"] = [args["frames"]]

        def copy_output(envelope):
            if out is None:
                return
            root = Path(envelope["project"])
            paths = envelope["result"]["paths"]
            if len(paths) > 1 and out.suffix:
                raise invalid("Multiple preview frames require --out to name a directory.")
            destinations = [
                out / Path(path).name if len(paths) > 1 or not out.suffix else out for path in paths
            ]
            # Check every destination before writing any, so a refusal changes no file.
            for destination in destinations:
                protect_project_output(state, destination)
            for source, destination in zip(paths, destinations, strict=True):
                data = (root / source).read_bytes()
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                if destination.read_bytes() != data:
                    raise OSError(f"Cannot verify preview copy at {destination}.")
            envelope["result"]["paths"] = [str(dest) for dest in destinations]

        return _run(state, op, args, transform=copy_output)

    return click.Command(name, params=params, callback=invoke, help=definition.description)
