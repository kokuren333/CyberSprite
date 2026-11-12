"""Lazy Click surface. --version does not import NumPy, pydantic, or the renderer."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import click

from cybersprite import __version__


def _emit(state: dict, op: str, result: dict, *, project=None, revision=None, warnings=None):
    envelope = {
        "ok": True,
        "op": op,
        "project": project,
        "revision": revision,
        "result": result,
        "warnings": warnings or [],
    }
    if state.get("format") == "text":
        click.echo(f"{op}: " + json.dumps(result, ensure_ascii=False))
    else:
        click.echo(json.dumps(envelope, ensure_ascii=False, allow_nan=False))


def _project(state):
    from cybersprite.core.canonical import load_project, project_path

    path = project_path(state["project"] or Path.cwd())
    project = load_project(path)
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
    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        finally:
            if ctx.obj is not None:
                ctx.obj["command"] = ctx.invoked_subcommand


@click.group(cls=ResultGroup, context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-p", "--project", type=click.Path(path_type=Path), help="Project directory or project.json."
)
@click.option("--format", "output_format", type=click.Choice(["json", "text"]), default="json")
@click.option(
    "--actor", envvar="CYBERSPRITE_ACTOR", default="cli", help="History actor (used from M2)."
)
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
@click.option("--frames", type=int, default=1, show_default=True)
@click.option(
    "--duration", type=int, default=100, show_default=True, help="Frame duration in milliseconds."
)
@click.option("--name", default=None)
@click.option("--palette", default="default", help="default, or a JSON array of #rrggbbaa colors.")
@click.option(
    "--background", default=None, help="Reserved for M2; currently returns E_UNSUPPORTED."
)
@click.pass_obj
def new_command(state, path, size, frames, duration, name, palette, background):
    """Create a new project at revision zero; never overwrite an existing project."""
    import re

    from cybersprite.core.errors import CyberSpriteError, invalid
    from cybersprite.core.projects import create_project, new_project

    if background is not None:
        raise CyberSpriteError(
            "E_UNSUPPORTED",
            "new --background is deferred until M2.",
            "Create a transparent project now; add a background with M2 Ops.",
        )
    match = re.fullmatch(r"([0-9]+)[xX]([0-9]+)", size)
    if match is None:
        raise invalid("--size must be WIDTHxHEIGHT, for example 32x32.")
    try:
        colors = None if palette == "default" else json.loads(palette)
    except ValueError as error:
        raise invalid("--palette must be default or a JSON array of #rrggbbaa colors.") from error
    project = new_project(
        width=int(match[1]),
        height=int(match[2]),
        frames=frames,
        duration=duration,
        name=name if name is not None else path.stem,
        palette=colors,
    )
    target = create_project(path, project)
    state.update(project_path=target.parent.as_posix(), revision=0)
    _output(
        state,
        "new_project",
        {
            "path": target.as_posix(),
            "name": project.name,
            "size": {"width": project.canvas.width, "height": project.canvas.height},
            "frames": len(project.frames),
        },
    )


@cli.command("info")
@click.option(
    "--include", default=None, help="Optional comma-separated sections: palette,validation."
)
@click.pass_obj
def info_command(state, include):
    """Describe project structure and stable layer IDs."""
    from cybersprite.core.errors import invalid
    from cybersprite.core.references import walk_layers

    project = _project(state)
    sections = set(include.split(",")) if include else set()
    if sections - {"palette", "validation"}:
        raise invalid("--include accepts palette,validation in M1.")
    result = {
        "name": project.name,
        "canvas": project.canvas.model_dump(),
        "frame_count": len(project.frames),
        "frames": [f.model_dump() for f in project.frames],
        "palette_size": len(project.palette.colors),
        "layers": [
            {
                "id": layer.id,
                "name": layer.name,
                "type": layer.type,
                "path": "/".join(node.name for node in (*ancestors, layer)),
                "visible": layer.visible,
            }
            for layer, ancestors in walk_layers(project.layers)
        ],
        "tags": [t.model_dump(by_alias=True, exclude_none=True) for t in project.tags],
        "slices": [s.id for s in project.slices],
        "tilesets": [t.id for t in project.tilesets],
    }
    for section in sorted(sections):
        result[section] = getattr(project, section).model_dump()
    _output(state, "get_info", result)


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

    from cybersprite.core.errors import CyberSpriteError, invalid
    from cybersprite.core.hashing import pixel_sha256
    from cybersprite.core.render import RenderOptions, indexed_result, render_result
    from cybersprite.formats.png import decode_png, encode_png, environment_fingerprint

    project = _project(state)
    if out.name.lower() == "project.json":
        raise invalid("Render output must not overwrite project.json; choose a .png destination.")
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
            "validation_ok": True,
            "validation_scope": "structural",
            "verified": verified,
        },
        result.warnings,
    )


@cli.command("validate")
@click.option("--strict", is_flag=True, help="Also fail on warnings (quality rules arrive in M2).")
@click.pass_obj
def validate_command(state, strict):
    """Validate structural invariants S-01..S-14. Quality checks arrive in M2."""
    from cybersprite.core.validation import validation_report

    project = _project(state)
    report = validation_report(project)
    _output(state, "validate", report)
    if not report["ok"] or strict and report["counts"]["warning"]:
        raise click.exceptions.Exit(1)


@cli.command("schema")
@click.argument("kind", type=click.Choice(["project", "sources", "all"]), default="all")
@click.option("--out", type=click.Path(path_type=Path), default=None)
@click.pass_obj
def schema_command(state, kind, out):
    """Return generated JSON Schemas or write them to a directory."""
    from cybersprite.core.schemas import generate_schemas

    generated = generate_schemas()
    names = list(generated) if kind == "all" else [kind]
    if out is None:
        _emit(state, "schema", {name: json.loads(generated[name]) for name in names})
    else:
        out.mkdir(parents=True, exist_ok=True)
        for name in names:
            (out / f"{name}.schema.json").write_bytes(generated[name])
        _emit(
            state, "schema", {"paths": [(out / f"{name}.schema.json").as_posix() for name in names]}
        )


@cli.command("doctor")
@click.pass_obj
def doctor_command(state):
    """Report versions, environment fingerprint, optional dependencies, and write access."""
    from importlib.metadata import PackageNotFoundError, version

    from cybersprite.formats.png import environment_fingerprint

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
        },
    )


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict", newline="\n")
    state: dict[str, Any] = {}
    try:
        result = cli.main(standalone_mode=False, obj=state)
        raise SystemExit(result if isinstance(result, int) else 0)
    except click.ClickException as error:
        from cybersprite.core.errors import invalid

        problem = invalid(error.format_message())
    except OSError as error:
        from cybersprite.core.errors import CyberSpriteError

        problem = CyberSpriteError("E_IO", str(error), "Check the path and file permissions.")
    except Exception as error:
        from cybersprite.core.errors import CyberSpriteError

        if isinstance(error, CyberSpriteError):
            problem = error
        else:
            problem = CyberSpriteError(
                "E_INTERNAL",
                f"Unexpected {type(error).__name__}: {error}",
                "Report this command and error to the CyberSprite maintainer.",
            )
    revision = state.get("revision")
    command = state.get("command")
    operation = (
        {"new": "new_project", "info": "get_info"}.get(command, command) if command else None
    )
    click.echo(
        json.dumps(
            {
                "ok": False,
                "op": operation,
                "project": state.get(
                    "project_path", str(state.get("project")) if state.get("project") else None
                ),
                "revision": {"before": revision, "after": revision},
                "error": problem.as_dict(),
            },
            ensure_ascii=False,
        )
    )
    raise SystemExit(problem.exit_code)
