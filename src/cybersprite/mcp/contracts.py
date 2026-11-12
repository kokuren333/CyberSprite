"""MCP presentation of registry contracts; operation implementations stay in ops."""

from copy import deepcopy
from dataclasses import replace
from typing import Literal

from pydantic import Field, create_model

from cybersprite.core.models import Model
from cybersprite.ops.args import TxOptions

# SPEC 10 chapter order, including operations supplied by later milestones.
ORDER = """
new_project get_info get_pixels get_palette validate render_preview diff_preview get_history
undo redo apply_ops set_project_meta set_validation
set_pixel set_pixels draw_rows line rect ellipse polygon stroke fill erase replace_color
transform_region outline cleanup_pixels
add_frame delete_frames move_frames reverse_frames set_frame_duration set_cel clear_cel copy_cel
link_cel unlink_cel
set_palette set_palette_color add_palette_colors remap_palette load_palette set_palette_frozen
add_layer update_layer delete_layer duplicate_layer merge_layers flatten
add_tag update_tag delete_tag add_slice update_slice delete_slice
add_tileset delete_tileset set_tile_pixels delete_tiles move_tiles set_tile set_tiles get_tiles
tileset_from_layer
resize_canvas crop_canvas scale_sprite transform_sprite
import_image import_aseprite export_image export_sheet export_animation export_aseprite
export_tileset export_palette list_sources get_source list_generators generate_image
""".split()
MINIMAL = frozenset(
    """
new_project get_info get_pixels get_palette validate render_preview diff_preview apply_ops undo
import_image export_image export_sheet export_animation
""".split()
)
GENERATION = frozenset({"list_generators", "generate_image"})
FORBIDDEN = frozenset({"run_lua", "run_script", "eval", "exec", "shell", "run_command"})

# Compatibility metadata for M2 definitions. New ops should put x-cybersprite-path
# on their own Field(json_schema_extra=...), including nested/list fields.
LEGACY_PATHS = {
    "new_project": {"palette": "palette"},
    "load_palette": {"source": "palette"},
    "import_image": {"files": "input"},
    "import_aseprite": {"file": "input"},
    "export_image": {"out": "output"},
    "export_sheet": {"out": "output", "data_out": "output"},
    "export_animation": {"out": "output"},
    "export_aseprite": {"out": "output"},
    "export_tileset": {"out": "output", "data_out": "output"},
    "export_palette": {"out": "output"},
}


def with_path_metadata(op):
    fields = {}
    for name, kind in LEGACY_PATHS.get(op.name, {}).items():
        if name not in op.args.model_fields:
            continue
        field = deepcopy(op.args.model_fields[name])
        field.json_schema_extra = {**(field.json_schema_extra or {}), "x-cybersprite-path": kind}
        fields[name] = (field.annotation, field)
    if fields:
        return replace(op, args=create_model(op.name + "PathArgs", __base__=op.args, **fields))
    return op


class ErrorInfo(Model):
    code: str
    message: str
    details: dict
    hint: str
    op_index: int | None = None


class Failure(Model):
    ok: Literal[False]
    op: str
    project: str
    revision: dict[str, int]
    error: ErrorInfo


def describe(op):
    """Generate both envelope branches from the Op and shared pydantic models."""
    value = op.describe()
    fields = {"project": (str, Field(..., json_schema_extra={"x-cybersprite-path": "project"}))}
    if op.kind in {"mutate", "ingest"}:
        fields.update(
            {name: (f.annotation, deepcopy(f)) for name, f in TxOptions.model_fields.items()}
        )
    value["inputSchema"] = create_model(
        op.name + "MCPInput", __base__=op.args, **fields
    ).model_json_schema(by_alias=True)
    success = value["outputSchema"]
    success["properties"]["ok"] = {"const": True, "type": "boolean"}
    # Inline PNG data lives only in MCP image blocks, not the JSON envelope.
    for definition in success.get("$defs", {}).values():
        definition.get("properties", {}).pop("images", None)
    failure = Failure.model_json_schema()
    defs = {**success.pop("$defs", {}), **failure.pop("$defs", {})}
    # Root "type": "object" is required by older MCP protocol versions (e.g. 2025-06-18).
    value["outputSchema"] = {"type": "object", "oneOf": [success, failure], "$defs": defs}
    return value
