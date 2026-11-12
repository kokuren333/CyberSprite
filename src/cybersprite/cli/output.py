"""One result document per invocation, with an optional human summary."""

import json
from pathlib import Path

import click


def protect_project_output(state, path, *, directory=False):
    """Apply the export preflight to a CLI output written outside the Op registry.

    Returns the resolved destination. Errors are E_PATH_NOT_ALLOWED for paths
    outside the working directory or inside project.json/source/.cybersprite of
    the selected project (or any project above the destination), as for export.
    """
    from cybersprite.core.canonical import project_path
    from cybersprite.formats.common import guard_output

    selected = state.get("project")
    canonical = project_path(selected if selected is not None else Path.cwd())
    root = canonical.parent if selected is not None or canonical.exists() else None
    return guard_output(Path(path), root, directory=directory)


def write(state, envelope):
    if state.get("format") == "text":
        if not envelope["ok"]:
            error = envelope["error"]
            click.echo(f"{error['code']}: {error['message']} {error['hint']}")
            return
        result = envelope["result"]
        summary = result.get("summary", result)
        fields = [
            f"{key}={value}"
            for key, value in summary.items()
            if isinstance(value, (str, int, bool))
        ]
        for key, value in result.items():
            if isinstance(value, list):
                fields.append(f"{key}={len(value)}")
        click.echo(f"{envelope['op']}: " + (", ".join(fields[:8]) or "OK"))
        if envelope["op"] == "generate_image":
            for term in result.get("model_terms", []):
                click.echo(term["message"])
    else:
        click.echo(json.dumps(envelope, ensure_ascii=False, allow_nan=False))


def failure(state, error):
    from cybersprite.core.errors import CyberSpriteError, invalid

    if isinstance(error, click.ClickException):
        problem = invalid(error.format_message())
    elif isinstance(error, (OSError, UnicodeError)):
        problem = CyberSpriteError(
            "E_IO", str(error), "Check the path, UTF-8 encoding, and file permissions."
        )
    elif isinstance(error, CyberSpriteError):
        problem = error
    else:
        problem = CyberSpriteError(
            "E_INTERNAL",
            f"Unexpected {type(error).__name__}: {error}",
            "Report this command and error to the CyberSprite maintainer.",
        )
    revision = state.get("revision")
    write(
        state,
        {
            "ok": False,
            "op": state.get("op") or state.get("command"),
            "project": state.get("project_path")
            or (str(state["project"]) if state.get("project") else None),
            "revision": {"before": revision, "after": revision},
            "error": {
                **problem.as_dict(),
                **({"op_index": problem.op_index} if hasattr(problem, "op_index") else {}),
            },
        },
    )
    return problem.exit_code
