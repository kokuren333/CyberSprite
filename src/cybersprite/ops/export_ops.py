"""Registered export functions and new-project .aseprite ingestion."""

from functools import partial

from cybersprite.core import history
from cybersprite.core.canonical import load_project, project_path
from cybersprite.core.models import GroupLayer, Placement
from cybersprite.core.projects import create_project
from cybersprite.core.references import walk_layers
from cybersprite.core.registry import Op
from cybersprite.core.sources import record_import
from cybersprite.core.transactions import synchronize
from cybersprite.formats.common import fail, output_path
from cybersprite.formats.export import EXPORTERS
from cybersprite.formats.export_args import (
    EXPORT_ARGS,
    ExportResult,
    ImportAsepriteArgs,
    ImportResult,
)


def apply_export(ctx, args, name):
    return EXPORTERS[name](ctx.project, args, ctx.root)


def _ingest_only(_ctx, _args):
    fail("E_INVALID_ARGS", "import_aseprite must be invoked as a top-level operation.")


def register_exports(registry):
    for name in sorted(EXPORT_ARGS):
        registry.register(
            Op(
                name,
                EXPORT_ARGS[name],
                partial(apply_export, name=name),
                ExportResult,
                "export",
                "E",
                False,
                "Export indexed project data and verify the file read back from disk.",
            )
        )
    registry.register(
        Op(
            "import_aseprite",
            ImportAsepriteArgs,
            _ingest_only,
            ImportResult,
            "ingest",
            "C",
            False,
            "Create a project from .aseprite and record the original file as a source.",
        )
    )


def execute_import(project, args, *, actor="cli"):
    from cybersprite.formats.aseprite_io import read_aseprite

    from .queries import summary

    target = project_path(project)
    root = target.parent
    file = output_path(args.file)
    # Parse and validate all bytes before creating the destination.
    p, dropped = read_aseprite(file, {"quantize": args.quantize})
    source = None
    with history.ProjectLock(root, actor):
        if target.exists():
            if args.if_exists != "open":
                fail(
                    "E_EXISTS",
                    "Project already exists; choose a new path or if_exists=open.",
                    path=target.as_posix(),
                )
            p, dropped = load_project(target), []
        else:
            # create_project uses exclusive creation, never replaces an existing project.json.
            create_project(target, p)
            try:
                placements = [
                    Placement(
                        revision=p.revision,
                        layer=layer.id,
                        frames=sorted(c.frame for c in layer.cels),
                    )
                    for layer, _ in walk_layers(p.layers)
                    if not isinstance(layer, GroupLayer) and layer.cels
                ]
                source = record_import(
                    root, file, p.canvas.width, p.canvas.height, placements=placements
                )
            except Exception:
                target.unlink(missing_ok=True)
                raise
    synchronize(root, p, actor=actor)
    warnings = [dict(code="W_DROPPED_ON_IMPORT", **item) for item in dropped]
    return dict(
        ok=True,
        op="import_aseprite",
        project=root.as_posix(),
        revision=p.revision,
        result=dict(summary=summary(p, root), dropped=dropped, source=source),
        warnings=warnings,
    )
