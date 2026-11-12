"""Lazy Click surface. --version does not import NumPy, pydantic, or the renderer."""

from __future__ import annotations

import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import click

from cybersprite import __version__

from .generated import (
    RegistryGroup,
    SchemaValue,
    definition_or_none,
    dither_option,
    normalize_pipeline_aliases,
    optional_function,
    schema_options,
    unsupported,
)
from .output import failure, protect_project_output, write


def _emit(state: dict, op: str, result: dict, *, project=None, revision=None, warnings=None):
    envelope = {
        "ok": True,
        "op": op,
        "project": project,
        "revision": revision,
        "result": result,
        "warnings": warnings or [],
    }
    write(state, envelope)


def _project(state):
    from cybersprite.core.canonical import load_project, project_path
    from cybersprite.core.transactions import synchronize

    path = project_path(state["project"] or Path.cwd())
    project = synchronize(path.parent, load_project(path), actor=state.get("actor", "cli"))
    state["revision"] = project.revision
    state["project_path"] = path.parent.as_posix()
    return project


def _output(state, op, result, warnings=None):
    _emit(
        state,
        op,
        result,
        project=state.get("project_path"),
        revision=state.get("revision"),
        warnings=warnings,
    )


class ResultGroup(click.Group):
    def main(self, args=None, prog_name=None, complete_var=None, standalone_mode=True, **extra):
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="strict", newline="\n")
        state = extra.setdefault("obj", {})
        # Project selection may follow a nested command (SPEC §9.4.2 example).
        arguments = list(args) if args is not None else sys.argv[1:]
        global_args: list[str] = []
        local_args: list[str] = []
        index = 0
        while index < len(arguments):
            value = arguments[index]
            if value == "--":
                local_args.extend(arguments[index:])
                break
            if value in {"-p", "--project", "--actor"} and index + 1 < len(arguments):
                global_args.extend(arguments[index : index + 2])
                index += 2
                continue
            if value == "--quiet" or value.startswith(("--project=", "--actor=")):
                global_args.append(value)
            else:
                local_args.append(value)
            index += 1
        try:
            result = super().main(
                args=global_args + local_args,
                prog_name=prog_name,
                complete_var=complete_var,
                standalone_mode=False,
                **extra,
            )
            code = result if isinstance(result, int) else 0
        except (click.exceptions.Exit, SystemExit) as error:
            code = (
                error.exit_code
                if isinstance(error, click.exceptions.Exit)
                else int(error.code or 0)
            )
        except Exception as error:
            code = failure(state, error)
        if standalone_mode:
            raise SystemExit(code)
        return code

    def get_command(self, ctx, cmd_name):
        if cmd_name in {"pixels", "preview", "diff"}:
            from .generated import read_command

            read_ops = {"pixels": "get_pixels", "preview": "render_preview", "diff": "diff_preview"}
            return read_command(cmd_name, read_ops[cmd_name])
        mappings = {
            "new": "new_project",
            "info": "get_info",
            "validate": "validate",
            "undo": "undo",
            "redo": "redo",
            "history": "get_history",
        }
        if cmd_name in mappings:
            op = mappings[cmd_name]
            definition = definition_or_none(op)
            command = self.commands[cmd_name]
            if cmd_name in {"undo", "redo", "history"}:

                def invoke(**args):
                    return _run(
                        click.get_current_context().obj,
                        op,
                        {key: value for key, value in args.items() if value is not None},
                    )

                return click.Command(
                    cmd_name,
                    params=schema_options(definition),
                    callback=invoke,
                    help=definition.description,
                )
            params = schema_options(
                definition,
                skip=("width", "height") if cmd_name == "new" else (),
                aliases={"duration_ms": ["--duration", "--duration-ms"]},
            )
            if cmd_name == "new":
                params = command.params[:2] + params  # PATH and composite --size.
            if cmd_name == "validate":
                params.append(click.Option(["--strict"], is_flag=True))
            if cmd_name == "info":
                for option in params:
                    if option.name == "include":
                        option.multiple = True
                        option.default = ()
            return click.Command(
                cmd_name, params=params, callback=command.callback, help=definition.description
            )
        return super().get_command(ctx, cmd_name)

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        finally:
            if ctx.obj is not None:
                ctx.obj.setdefault("command", ctx.invoked_subcommand)

    def format_commands(self, ctx, formatter):
        # Click's default calls get_command for every command. Avoid schema imports here.
        with formatter.section("Commands"):
            formatter.write_dl(
                [
                    (name, command.get_short_help_str())
                    for name, command in sorted(self.commands.items())
                ]
            )


@click.group(cls=ResultGroup, context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-p", "--project", type=click.Path(path_type=Path), help="Project directory or project.json."
)
@click.option("--format", "output_format", type=click.Choice(["json", "text"]), default="json")
@click.option("--actor", envvar="CYBERSPRITE_ACTOR", default="cli", help="History actor.")
@click.option("--quiet", is_flag=True, help="Suppress progress messages on stderr.")
@click.version_option(version=__version__, prog_name="cybersprite")
@click.pass_context
def cli(ctx, project, output_format, actor, quiet):
    """Deterministic indexed-color sprite tools. Frame numbers start at zero."""
    ctx.ensure_object(dict)
    ctx.obj.update(project=project, format=output_format, actor=actor, quiet=quiet)


@cli.command("new")
@click.argument("path", type=click.Path(path_type=Path))
@click.option("--size", required=True, help="Canvas WIDTHxHEIGHT in integer pixels.")
@click.pass_obj
def new_command(state, path, size, frames, duration_ms, name, palette, background, **extra):
    """Create a new project at revision zero; never overwrite an existing project."""
    import re

    from cybersprite.core.errors import invalid
    from cybersprite.ops import execute

    state.update(op="new_project", project=path)
    match = re.fullmatch(r"([0-9]+)[xX]([0-9]+)", size)
    if match is None:
        raise invalid("--size must be WIDTHxHEIGHT, for example 32x32.")
    colors = "cs-circuit-16" if palette == "default" else palette
    envelope = execute(
        "new_project",
        path,
        {
            "width": int(match[1]),
            "height": int(match[2]),
            **({"frames": frames} if frames is not None else {}),
            **({"duration_ms": duration_ms} if duration_ms is not None else {}),
            "name": name or path.stem,
            **({"palette": colors} if colors is not None else {}),
            "background": background,
            **{key: value for key, value in extra.items() if value is not None},
        },
        actor=state["actor"],
    )
    state.update(project_path=envelope["project"], revision=envelope["revision"])
    write(state, envelope)


@cli.command("info")
@click.pass_obj
def info_command(state, include):
    """Describe project structure and stable layer IDs."""
    merged = list(dict.fromkeys(item for group in include for item in group)) if include else []
    _run(state, "get_info", {"include": merged} if merged else {})


@cli.command("render")
@click.option("--frame", type=int, default=0, show_default=True)
@click.option("--out", required=True, type=click.Path(path_type=Path))
@click.option("--scale", type=int, default=1, show_default=True)
@click.option("--layers", default=None, help="Comma-separated layer IDs, names, or group paths.")
@click.option("--bg", default=None, help="Palette index or #rrggbb opaque background.")
@click.option("--indexed", is_flag=True, help="Require palette closure and write indexed PNG.")
@click.option("--flatten", type=click.Choice(["strict", "nearest"]), default="strict")
@click.option("--include-hidden", is_flag=True)
@click.option("--compression", type=click.Choice(["zlib", "stored"]), default="zlib")
@click.option("--apply-pixel-ratio", is_flag=True)
@click.pass_obj
def render_command(
    state,
    frame,
    out,
    scale,
    layers,
    bg,
    indexed,
    flatten,
    include_hidden,
    compression,
    apply_pixel_ratio,
):
    """Render one undecorated frame to a self-verified PNG."""
    import numpy as np

    from cybersprite.core.errors import CyberSpriteError
    from cybersprite.core.hashing import pixel_sha256
    from cybersprite.core.quality import report
    from cybersprite.core.render import RenderOptions, indexed_result, render_result
    from cybersprite.formats.png import decode_png, encode_png, environment_fingerprint

    project = _project(state)
    protect_project_output(state, out)
    options = RenderOptions(
        layers=layers.split(",") if layers is not None else None,
        scale=scale,
        background=int(bg) if bg and bg.isdecimal() else bg,
        flatten=flatten,
        include_hidden=include_hidden,
        apply_pixel_ratio=apply_pixel_ratio,
    )
    result = (
        indexed_result(project, frame, options)
        if indexed
        else render_result(project, frame, options)
    )
    data = encode_png(result.pixels, result.palette, compression=compression)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        decoded = decode_png(out.read_bytes())
    except OSError as error:
        raise CyberSpriteError(
            "E_IO",
            f"Cannot write or verify PNG: {error}",
            "Check the destination and write permissions.",
            {"path": out.as_posix()},
        ) from error
    verified = np.array_equal(result.pixels, decoded.pixels) and result.palette == decoded.palette
    if not verified:
        raise CyberSpriteError(
            "E_INTERNAL",
            "Written PNG did not match rendered pixels.",
            "Keep the output and report this self-verification failure.",
        )
    _output(
        state,
        "render",
        {
            "path": out.as_posix(),
            "width": result.pixels.shape[1],
            "height": result.pixels.shape[0],
            "indexed": indexed,
            "pixel_sha256": pixel_sha256(result.pixels),
            "environment_fingerprint": environment_fingerprint(),
            "validation_ok": report(project, root=state["project_path"])["ok"],
            "validation_scope": "full",
            "verified": verified,
        },
        result.warnings,
    )


@cli.command("validate")
@click.pass_obj
def validate_command(state, frames, rules, strict):
    """Validate all structural invariants, quality rules and metrics."""
    report = _run(
        state,
        "validate",
        {
            key: value
            for key, value in {"frames": frames, "rules": rules}.items()
            if value is not None
        },
    )["result"]
    if not report["ok"] or strict and report["counts"]["warning"]:
        raise click.exceptions.Exit(1)


@cli.command("schema")
@click.argument(
    "kind", type=click.Choice(["project", "sources", "sheet", "op", "all"]), default="all"
)
@click.argument("name", required=False)
@click.option("--out", type=click.Path(path_type=Path), default=None)
@click.pass_obj
def schema_command(state, kind, name, out):
    """Return generated JSON Schemas or write them to a directory."""
    from cybersprite.core.errors import invalid
    from cybersprite.ops import registry
    from cybersprite.schemas import generate_schemas

    if (kind == "op") != (name is not None):
        raise invalid("Use schema op <name>; other schema kinds do not take a name.")
    generated = (
        generate_schemas()
        if kind != "op"
        else {"op": json.dumps(registry().get(name).describe()["inputSchema"]).encode("utf-8")}
    )
    names = list(generated) if kind == "all" else [kind]
    if out is None:
        _emit(state, "schema", {name: json.loads(generated[name]) for name in names})
    else:
        out.mkdir(parents=True, exist_ok=True)
        for name in names:
            protect_project_output(state, out / f"{name}.schema.json")
            (out / f"{name}.schema.json").write_bytes(generated[name])
        _emit(
            state, "schema", {"paths": [(out / f"{name}.schema.json").as_posix() for name in names]}
        )


@cli.command("doctor")
@click.pass_obj
def doctor_command(state):
    """Report versions, environment fingerprint, optional dependencies, and write access."""
    from importlib.metadata import PackageNotFoundError, version

    from cybersprite.config import config_path, load_config
    from cybersprite.formats.png import environment_fingerprint

    settings = load_config()

    dependencies: dict[str, str | None] = {}
    for name in (
        "numpy",
        "pydantic",
        "click",
        "mcp",
        "Pillow",
        "aseprite",
        "starlette",
        "diffusers",
    ):
        try:
            dependencies[name] = version(name)
        except PackageNotFoundError:
            dependencies[name] = None
    _emit(
        state,
        "doctor",
        {
            "version": __version__,
            "python": sys.version.split()[0],
            "environment_fingerprint": environment_fingerprint(),
            "dependencies": dependencies,
            "cwd_writable": os.access(Path.cwd(), os.W_OK),
            "config": {
                "path": config_path().as_posix(),
                "exists": config_path().is_file(),
                "valid": True,
                "command_backends": sorted(settings.generators.command),
                "models": sorted(settings.generators.diffusers.models),
                "enabled_plugins": sorted(settings.plugins.enabled),
            },
        },
    )


def _run(state, name, args, *, transform=None, label=None, **options):
    from cybersprite.core.canonical import load_project, project_path
    from cybersprite.formats.common import export_policy
    from cybersprite.ops import execute

    path = state.get("project") or Path.cwd()
    state["op"] = name
    if name == "generate_image":
        from cybersprite.config import reject_tool_configuration

        reject_tool_configuration(args)
    state["project_path"] = project_path(path).parent.as_posix()
    if project_path(path).exists():
        state["revision"] = load_project(path).revision
    with export_policy(Path.cwd()):
        envelope = execute(
            name, path, {**args, **options}, actor=state.get("actor", "cli"), label=label
        )
    if transform:
        transform(envelope)
    write(state, envelope)
    return envelope


def _json_object(value):
    from cybersprite.core.errors import invalid

    try:
        parsed = json.loads(value)
    except ValueError as error:
        raise invalid("Arguments must contain a valid JSON object.", reason=str(error)) from error
    if not isinstance(parsed, dict):
        raise invalid("Arguments must be a JSON object.")
    return parsed


@cli.command("op")
@click.argument("name")
@click.argument("values", nargs=-1)
@click.option("--args", "inline_args", default=None)
@click.option("--args-file", type=click.Path(path_type=Path), default=None)
@click.option("--dry-run", is_flag=True, default=None)
@click.option("--expect-revision", type=int, default=None)
@click.option("--idempotency-key", default=None)
@click.option("--label", default=None, help="History label for this transaction.")
@click.option("--preview", type=click.Choice(["none", "path", "inline"]), default=None)
@click.pass_obj
def op_command(state, name, values, inline_args, args_file, **options):
    """Execute a registered Op. Merge args-file, args JSON, then key=value arguments."""
    from cybersprite.core.errors import invalid
    from cybersprite.ops import registry

    from .generated import SchemaValue

    schema = registry().get(name).args.model_json_schema(by_alias=True)

    args = _json_object(args_file.read_text("utf-8")) if args_file else {}
    if inline_args:
        args.update(_json_object(inline_args))
    for item in values:
        if "=" not in item:
            raise invalid("Op arguments must use key=value.", argument=item)
        key, value = item.split("=", 1)
        try:
            value = json.loads(value)
        except ValueError:
            if key in schema["properties"]:
                value = SchemaValue(schema["properties"][key], schema.get("$defs", {})).convert(
                    value, None, None
                )
        args[key] = value
    _run(state, name, args, **{key: value for key, value in options.items() if value is not None})


@cli.command("apply")
@click.argument("file", default="-")
@click.option("--dry-run", is_flag=True, default=None)
@click.option("--expect-revision", type=int, default=None)
@click.option("--idempotency-key", default=None)
@click.option("--preview", type=click.Choice(["none", "path", "inline"]), default=None)
@click.pass_obj
def apply_command(state, file, **options):
    """Apply a JSON transaction containing ops, label, and common transaction options."""
    _run(
        state,
        "apply_ops",
        _json_object(_read_stdin() if file == "-" else Path(file).read_text("utf-8")),
        **{key: value for key, value in options.items() if value is not None},
    )


# Argument models are loaded only for the selected command.
for _name in ("undo", "redo", "history"):
    cli.add_command(click.Command(_name, help=f"Read or update {_name} through the Op registry."))


@cli.group("ops")
def ops_group():
    """Inspect the same contracts used by CLI, MCP, and GUI."""


@ops_group.command("list")
@click.pass_obj
def ops_list(state):
    from cybersprite.ops import registry

    registry().load_plugins(enabled=True)
    _emit(
        state,
        "ops_list",
        {
            "ops": [
                {"name": op.name, "kind": op.kind, "idempotency": op.idempotency}
                for op in registry().all()
            ]
        },
    )


@ops_group.command("describe")
@click.argument("name")
@click.pass_obj
def ops_describe(state, name):
    from cybersprite.ops import registry

    _emit(state, "ops_describe", registry().get(name).describe())


# Parameters for these commands are materialized only when selected.
for _name in ("pixels", "preview", "diff"):
    cli.add_command(click.Command(_name, help=f"Read {_name} through the Op registry."))


@cli.group("palette")
def palette_group():
    """Inspect project palette or built-in presets."""


@palette_group.command("show")
@click.pass_obj
def palette_show(state):
    _run(state, "get_palette", {})


@palette_group.command("presets")
@click.pass_obj
def palette_presets(state):
    from cybersprite.formats.palette_files import presets

    _emit(state, "palette_presets", {"presets": presets()})


def _read_stdin():
    from cybersprite.core.errors import invalid

    stream = click.get_text_stream("stdin", encoding="utf-8")
    if stream.isatty():
        raise invalid("apply needs a JSON file or piped UTF-8 JSON; interactive input is disabled.")
    return stream.read()


cli.add_command(
    RegistryGroup(
        "export",
        help="Export using registered format operations.",
        routes={
            "image": ("export_image", "M5", None),
            "sheet": ("export_sheet", "M5", None),
            "anim": ("export_animation", "M5", None),
            "aseprite": ("export_aseprite", "M5", None),
            "tileset": ("export_tileset", "M5", None),
            "palette": ("export_palette", "M5", None),
            "plugin": ("export_plugin", "R1-C", None),
        },
    )
)
cli.add_command(
    RegistryGroup(
        "import",
        help="Import through registered ingestion operations.",
        routes={
            "image": ("import_image", "M6", "files"),
            "aseprite": ("import_aseprite", "M5", "file"),
            "palette": ("load_palette", "M2", "source"),
        },
    )
)
cli.add_command(
    RegistryGroup(
        "source",
        help="Read source provenance.",
        routes={
            "list": ("list_sources", "M6", None),
            "show": ("get_source", "M6", "id"),
        },
    )
)


@cli.group("plugins")
def plugins_group():
    """Inspect plugins allowed by the user configuration."""


@plugins_group.command("list")
@click.pass_obj
def plugins_list(state):
    from cybersprite.plugins import PluginManager

    _emit(
        state,
        "plugins_list",
        {"plugins": PluginManager().listing()},
    )


def _launch(state, module, function, milestone, install=None, **options):
    callback = optional_function(module, function, milestone, install)
    # Server protocols own stdout while running. Startup logs belong on stderr.
    try:
        if module == "cybersprite.mcp.server":
            result = callback(**options)
        else:
            result = _call_with_diagnostics(state, callback, **options)
    except ImportError as error:
        try:
            unsupported(module, milestone, install)
        except Exception as problem:
            raise problem from error
    _emit(state, function, result if isinstance(result, dict) else {"stopped": True})


def _call_with_diagnostics(state, callback, *args, **options):
    with open(os.devnull, "w", encoding="utf-8") as silent:
        with (
            redirect_stdout(silent if state.get("quiet") else sys.stderr),
            redirect_stderr(silent if state.get("quiet") else sys.stderr),
        ):
            return callback(*args, **options)


@cli.group("mcp")
def mcp_group():
    """Run the optional MCP service."""


@mcp_group.command("serve")
@click.option("--root", type=click.Path(path_type=Path), default=Path("."))
@click.option("--allow-dir", multiple=True, type=click.Path(path_type=Path))
@click.option("--transport", type=click.Choice(["stdio", "http"]), default="stdio")
@click.option("--port", type=click.IntRange(1, 65535), default=8765)
@click.option("--profile", type=click.Choice(["standard", "minimal"]), default="standard")
@click.option("--enable-generation", is_flag=True)
@click.option("--allow-plugin-op", multiple=True)
@click.option("--read-only", is_flag=True)
@click.pass_obj
def mcp_serve(state, **options):
    for key in ("allow_dir", "allow_plugin_op"):
        options[key] = list(options[key])
    _launch(state, "cybersprite.mcp.server", "serve", "M4", "cybersprite[mcp]", **options)


@cli.command("gui")
@click.option("--enable-generation", is_flag=True)
@click.argument("path", type=click.Path(path_type=Path), required=False)
@click.option("--port", type=click.IntRange(0, 65535), default=None)
@click.option("--no-browser", is_flag=True, default=None)
@click.option("--root", type=click.Path(path_type=Path, file_okay=False), default=None)
@click.option("--allow-dir", multiple=True, type=click.Path(path_type=Path, file_okay=False))
@click.pass_obj
def gui_command(state, path, port, no_browser, root, allow_dir, enable_generation):
    from cybersprite.config import load_config

    settings = load_config()
    _launch(
        state,
        "cybersprite.server",
        "serve",
        "M8",
        "cybersprite[gui]",
        project=path or state.get("project"),
        port=settings.gui.port if port is None else port,
        no_browser=not settings.gui.open_browser if no_browser is None else no_browser,
        root=root,
        allow_dir=allow_dir,
        enable_generation=enable_generation,
    )


class GenerationGroup(RegistryGroup):
    def get_command(self, ctx, cmd_name):
        if cmd_name not in self.routes:
            return None
        op, milestone, _ = self.routes[cmd_name]
        # Import lazily so M9 can register its operations when the command is selected.
        import importlib

        try:
            importlib.import_module("cybersprite.generate")
        except ImportError:
            pass
        if definition_or_none(op) is not None:
            return super().get_command(ctx, cmd_name)
        params = []
        if cmd_name == "run":
            for name in ("backend", "prompt", "negative_prompt", "model", "params"):
                params.append(
                    click.Option(
                        ["--" + name.replace("_", "-")],
                        type=SchemaValue({"type": "object"}, {}) if name == "params" else str,
                    )
                )
            for name in ("width", "height", "seed", "count"):
                params.append(click.Option(["--" + name], type=int))
            params.append(click.Option(["--accept-model-license"], is_flag=True))
        elif cmd_name == "accept-license":
            params.append(click.Argument(["name"]))

        def invoke(**values):
            from cybersprite.config import reject_tool_configuration

            state = click.get_current_context().obj
            state["op"] = op
            reject_tool_configuration(values)
            function = optional_function("cybersprite.generate", op, milestone)
            if cmd_name == "backends":
                result = _call_with_diagnostics(state, function)
            else:
                result = _call_with_diagnostics(
                    state,
                    function,
                    project=state.get("project") or Path.cwd(),
                    actor=state["actor"],
                    **values,
                )
            _emit(state, op, result)

        return click.Command(cmd_name, params=params, callback=invoke, help=f"{op} ({milestone}).")


cli.add_command(
    GenerationGroup(
        "gen",
        help="Use optional generation backends.",
        routes={
            "backends": ("list_generators", "M9", None),
            "run": ("generate_image", "M9", None),
            "accept-license": ("accept_license", "M9", "name"),
        },
    )
)


def _pipeline_options():
    # Shared with convert before import_image is registered; M6 owns their semantics.
    definition = definition_or_none("import_image")
    if definition:
        params = schema_options(definition, skip=("files", "target", "provenance", "source"))
        if "pipeline" in definition.args.model_fields:
            params.append(dither_option())
        return params
    return [
        click.Option(["--preset"], type=click.Choice(["ai", "exact", "upscaled", "photo"])),
        click.Option(["--pipeline"], type=SchemaValue({"type": "object"}, {})),
        click.Option(
            ["--sheet", "--sheet-cell"],
            type=SchemaValue({"type": "object", "properties": {"cell_w": {}, "cell_h": {}}}, {}),
        ),
        dither_option(),
        click.Option(["--stages"], type=click.Path(path_type=Path)),
    ]


class ConvertCommand(click.Command):
    def parse_args(self, ctx, args):
        self.params = [click.Argument(["input"]), click.Argument(["output"]), *_pipeline_options()]
        if not any(param.name == "stages" for param in self.params):
            self.params.append(click.Option(["--stages"], type=click.Path(path_type=Path)))
        return super().parse_args(ctx, args)


def convert_command(**values):
    state = click.get_current_context().obj
    normalize_pipeline_aliases(values)
    callback = optional_function("cybersprite.pipeline.cli_api", "convert", "M6")
    values["input_path"] = values.pop("input")
    values["output_path"] = values.pop("output")
    result = _call_with_diagnostics(
        state, callback, **{key: value for key, value in values.items() if value is not None}
    )
    _emit(state, "convert", result)


cli.add_command(
    ConvertCommand(
        "convert",
        callback=convert_command,
        help="Convert a raster to indexed PNG and a pipeline report.",
    )
)


@cli.group("pipeline")
def pipeline_group():
    """Diagnose the optional conversion pipeline."""


@pipeline_group.command("detect-grid")
@click.argument("file", type=click.Path(path_type=Path))
@click.pass_obj
def detect_grid(state, file):
    callback = optional_function("cybersprite.pipeline.cli_api", "detect_grid", "M6")
    _emit(state, "detect_grid", _call_with_diagnostics(state, callback, file))


def main():
    cli.main(prog_name="cybersprite")
