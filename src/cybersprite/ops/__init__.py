"""Built-in Op definitions and the shared public execution entry point."""

import os
from contextlib import nullcontext
from copy import deepcopy
from functools import partial
from types import SimpleNamespace
from typing import Any, Literal

from pydantic import Field, ValidationError, create_model

from cybersprite.core import history
from cybersprite.core.canonical import dumps_project, load_project, project_path
from cybersprite.core.errors import invalid
from cybersprite.core.models import Model
from cybersprite.core.registry import EmptyResult, Op, OpContext, Registry
from cybersprite.core.transactions import synchronize, transact

from .args import ARGS, TxOptions
from .canvas import canvas_op
from .common import fail
from .descriptions import OPERATIONS
from .drawing import drawing
from .frames import frame_op
from .ingest import (
    GetSourceArgs,
    GetSourceResult,
    ImportArgs,
    ImportResult,
    ListSourcesArgs,
    ListSourcesResult,
    import_top,
    place,
    source_query,
)
from .palette import palette_op
from .previews import transaction_previews
from .queries import construct, query, summary
from .structure import layer_op, metadata_op, tag_slice_op

DRAWING = {
    "set_pixel",
    "set_pixels",
    "draw_rows",
    "line",
    "rect",
    "ellipse",
    "polygon",
    "stroke",
    "fill",
    "erase",
    "replace_color",
    "transform_region",
    "outline",
    "cleanup_pixels",
}
FRAME = {
    "add_frame",
    "delete_frames",
    "move_frames",
    "reverse_frames",
    "set_frame_duration",
    "set_cel",
    "clear_cel",
    "copy_cel",
    "link_cel",
    "unlink_cel",
}
PALETTE = {
    "set_palette",
    "set_palette_color",
    "add_palette_colors",
    "remap_palette",
    "load_palette",
    "set_palette_frozen",
}
LAYERS = {"add_layer", "update_layer", "delete_layer", "duplicate_layer", "merge_layers", "flatten"}
TAG_SLICE = {"add_tag", "update_tag", "delete_tag", "add_slice", "update_slice", "delete_slice"}
CANVAS = {"resize_canvas", "crop_canvas", "scale_sprite", "transform_sprite"}
QUERY = {
    "get_info",
    "get_pixels",
    "get_palette",
    "validate",
    "render_preview",
    "diff_preview",
    "get_history",
}
NON_IDEMPOTENT = {
    "transform_region",
    "outline",
    "cleanup_pixels",
    "add_frame",
    "delete_frames",
    "move_frames",
    "reverse_frames",
    "remap_palette",
    "duplicate_layer",
    "merge_layers",
    "scale_sprite",
    "transform_sprite",
    "undo",
    "redo",
    "apply_ops",
}
CONDITIONAL = {
    "new_project",
    "add_palette_colors",
    "copy_cel",
    "add_layer",
    "delete_layer",
    "add_tag",
    "delete_tag",
    "add_slice",
    "delete_slice",
    "crop_canvas",
}
DESTRUCTIVE = {
    "delete_layer",
    "delete_frames",
    "delete_tag",
    "delete_slice",
    "clear_cel",
    "erase",
    "flatten",
    "merge_layers",
    "crop_canvas",
    "set_palette",
}


class PixelResult(Model):
    pixels_written: int


def _result(name):
    if name == "cleanup_pixels":
        return create_model(
            "CleanupResult",
            __base__=PixelResult,
            positions=(list[dict], ...),
            positions_truncated=(bool, ...),
        )
    fields: dict[str, Any] = {
        "add_frame": {"frames": (list[int], ...)},
        "delete_frames": {"deleted": (list[int], ...), "removed_tags": (list[str], ...)},
        "move_frames": {"mapping": (dict[str, int], ...)},
        "add_palette_colors": {"indices": (list[int], ...)},
        "remap_palette": {"mapping": (dict[str, int], ...), "palette_size": (int, ...)},
        "set_validation": {"validation": (dict, ...)},
        "undo": {"restored_revision": (int, ...)},
        "redo": {"restored_revision": (int, ...)},
        "apply_ops": {"results": (list[dict], ...)},
        "new_project": {"summary": (dict, ...)},
        "get_info": {
            key: (Any, None)
            for key in (
                "summary",
                "layers",
                "frames",
                "tags",
                "slices",
                "tilesets",
                "palette",
                "sources",
                "validation",
                "history",
            )
        },
        "get_pixels": {
            "x": (int, ...),
            "y": (int, ...),
            "w": (int, ...),
            "h": (int, ...),
            "rows": (list[str], ...),
            "legend": (dict[str, int] | None, None),
            "used": (list[dict], ...),
        },
        "get_palette": {
            "transparent_index": (int, ...),
            "frozen": (bool, ...),
            "colors": (list[dict], ...),
        },
        "validate": {
            "ok": (bool, ...),
            "revision": (int, ...),
            "counts": (dict[str, int], ...),
            "issues": (list[dict], ...),
            "metrics": (dict, ...),
            "settings": (dict, ...),
            "scope": (str, ...),
        },
        "get_history": {
            "entries": (list[dict], ...),
            "can_undo": (bool, ...),
            "can_redo": (bool, ...),
        },
        "render_preview": {
            "paths": (list[str], ...),
            "scale": (int, ...),
            "width": (int, ...),
            "height": (int, ...),
            "images": (list[str], Field(default_factory=lambda: [])),
        },
        "diff_preview": {
            "frames": (list[dict], ...),
            "paths": (list[str], ...),
            "omitted_frames": (list[int], ...),
            "images": (list[str], Field(default_factory=lambda: [])),
        },
    }
    if name in DRAWING:
        return PixelResult
    if name in {"add_layer", "duplicate_layer", "merge_layers", "add_tag", "add_slice"}:
        return create_model(name + "Result", __base__=Model, id=(str, ...))
    if name not in fields:
        return EmptyResult
    return create_model(name + "Result", __base__=Model, **fields[name])


def _special(_ctx, _args):
    raise invalid("This operation must be invoked as a top-level call.")


_registry = None


def registry():
    global _registry
    if _registry is None:
        _registry = Registry()
        for name in sorted(ARGS):
            function = next(
                (
                    fn
                    for group, fn in (
                        (DRAWING, drawing),
                        (FRAME, frame_op),
                        (PALETTE, palette_op),
                        (LAYERS, layer_op),
                        (TAG_SLICE, tag_slice_op),
                        (CANVAS, canvas_op),
                        (QUERY, query),
                        ({"set_project_meta", "set_validation"}, metadata_op),
                    )
                    if name in group
                ),
                None,
            )
            apply = partial(function, name=name) if function else _special
            kind: Literal["query", "mutate"] = "query" if name in QUERY else "mutate"
            idem: Literal["R", "N", "C", "I"] = (
                "R"
                if name in QUERY
                else "N"
                if name in NON_IDEMPOTENT
                else "C"
                if name in CONDITIONAL
                else "I"
            )
            description = OPERATIONS[name] + (
                " Coordinates are integer pixels from the canvas top left; frames start at zero. "
                "invalid references, locked targets, or invalid arguments fail explicitly."
            )
            _registry.register(
                Op(
                    name,
                    ARGS[name],
                    apply,
                    _result(name),
                    kind,
                    idem,
                    name in DESTRUCTIVE,
                    description,
                )
            )
        from .export_ops import register_exports

        register_exports(_registry)
        _registry.register(
            Op(
                "import_image",
                ImportArgs,
                place,
                ImportResult,
                "ingest",
                "N",
                description="Convert with provenance and gates, then place transactionally.",
            )
        )
        for name, arguments, result in (
            ("list_sources", ListSourcesArgs, ListSourcesResult),
            ("get_source", GetSourceArgs, GetSourceResult),
        ):
            _registry.register(
                Op(
                    name,
                    arguments,
                    partial(source_query, name=name),
                    result,
                    "query",
                    "R",
                    description="Inspect stored source provenance and conversion reports.",
                )
            )
    return _registry


def execute(name, project, args=None, *, actor=None, label=None, **options):
    """CLI, MCP and GUI share this entry; exceptions retain structured codes and op_index."""
    actor = os.environ.get("CYBERSPRITE_ACTOR", "cli") if actor is None else actor
    definition = registry().get(name)
    args = deepcopy(args or {})
    for key in TxOptions.model_fields:
        if key in args:
            options[key] = args.pop(key)
    try:
        tx = TxOptions.model_validate(options)
    except ValidationError as error:
        raise invalid(
            "Invalid transaction options.",
            issues=error.errors(include_context=False, include_input=False),
        ) from error
    parsed = definition.parse(args)
    root = project_path(project).parent
    if name == "import_aseprite" and definition.kind == "ingest":
        if options:
            raise invalid("Transaction options are accepted only by mutate operations.")
        from .export_ops import execute_import

        return execute_import(project, parsed, actor=actor)
    if name == "import_image" and definition.kind == "ingest":
        return import_top(registry(), project, parsed, tx, actor)
    if name in ("list_sources", "get_source") and not project_path(project).exists():
        value = definition.apply(SimpleNamespace(root=root), parsed)
        definition.result.model_validate(value)
        return {
            "ok": True,
            "op": name,
            "project": root.as_posix(),
            "revision": 0,
            "result": value,
            "warnings": [],
        }
    if name == "new_project":
        target = project_path(project)
        p = construct(parsed, root)
        with nullcontext() if tx.dry_run else history.ProjectLock(root, actor):
            if target.exists():
                if parsed.if_exists != "open":
                    fail(
                        "E_EXISTS",
                        "Project already exists; use if_exists=open to reuse it.",
                        path=target.as_posix(),
                    )
                p = load_project(target)
                if (p.canvas.width, p.canvas.height) != (parsed.width, parsed.height):
                    raise invalid(
                        "Existing project dimensions do not match the requested dimensions."
                    )
            elif not tx.dry_run:
                history.atomic_write(target, dumps_project(p))
        if not tx.dry_run:
            synchronize(root, p, actor=actor)
        return {
            "ok": True,
            "op": name,
            "project": root.as_posix(),
            "revision": p.revision,
            "result": {"summary": summary(p, root)},
            "warnings": [],
        }
    if definition.kind == "mutate":
        calls = (
            [item.model_dump() for item in parsed.ops]
            if name == "apply_ops"
            else [{"op": name, "args": args}]
        )
        return transact(
            registry(),
            project,
            calls,
            tx,
            op=name,
            label=label if label is not None else parsed.label if name == "apply_ops" else None,
            actor=actor,
            previewer=transaction_previews,
        )
    if options:
        raise invalid("Transaction options are accepted only by mutate operations.")
    p = synchronize(root, load_project(project), actor=actor)
    value = definition.apply(OpContext(p, root), parsed)
    # Validate output without injecting optional absent query sections.
    definition.result.model_validate(value)
    return {
        "ok": True,
        "op": name,
        "project": root.as_posix(),
        "revision": p.revision,
        "result": value,
        "warnings": [],
    }
