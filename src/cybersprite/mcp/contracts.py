"""MCP presentation of registry contracts; operation implementations stay in ops."""

import json
from copy import deepcopy
from dataclasses import replace

from pydantic import Field, create_model

from cybersprite.ops.args import TxOptions

# SPEC 10 chapter order, including operations supplied by later milestones.
ORDER = """
new_project get_info list_platforms set_platform get_pixels get_palette validate
render_preview diff_preview get_history
undo redo apply_ops set_project_meta set_validation
set_pixel set_pixels draw_rows line rect ellipse polygon stroke fill erase replace_color
transform_region outline shift_ramp cleanup_pixels
add_frame delete_frames move_frames reverse_frames set_frame_duration set_cel clear_cel copy_cel
link_cel unlink_cel move_cel set_frame_ticks conform_palette
set_palette set_palette_color add_palette_colors remap_palette load_palette set_palette_frozen
add_layer update_layer delete_layer duplicate_layer merge_layers flatten
add_tag update_tag delete_tag add_slice update_slice delete_slice
add_tileset delete_tileset set_tile_pixels delete_tiles move_tiles set_tile set_tiles get_tiles
tileset_from_layer
resize_canvas crop_canvas scale_sprite transform_sprite
import_image import_aseprite export_image export_sheet export_animation export_aseprite
export_tileset export_palette export_plugin export_native
add_source list_sources get_source list_generators generate_image
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


def compact(schema):
    """Keep validation keywords; omit repeated presentation-only annotations."""
    if isinstance(schema, list):
        return [compact(item) for item in schema]
    if isinstance(schema, dict):
        return {
            key: (
                {name: compact(child) for name, child in value.items()}
                if key in {"properties", "$defs", "patternProperties"}
                else value
                if key in {"default", "const", "enum"}
                else compact(value)
            )
            for key, value in schema.items()
            if key not in {"title", "description", "discriminator"}
            and not key.startswith("x-cybersprite-")
        }
    return schema


ENVELOPE_SCHEMA = {
    "type": "object",
    "required": ["ok", "op", "project", "revision"],
    "oneOf": [
        {"properties": {"ok": {"const": True}}, "required": ["result"]},
        {"properties": {"ok": {"const": False}}, "required": ["error"]},
    ],
}


def compact_input(schema):
    """Advertise scalar constraints and small shapes; the Op parser stays authoritative.

    Full nested contracts remain available through ops describe and schema artifacts.
    Do not send external references that require clients to fetch a schema over a network.
    """
    definitions = compact(schema.get("$defs", {}))

    def visit(node):
        if isinstance(node, list):
            return [visit(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            name = node["$ref"].split("/")[-1]
            target = definitions[name]
            if len(json.dumps(target)) <= 160 or name in {"Brush", "OpCall"}:
                return visit(target)
            return {"type": target.get("type", "object")}
        result = {
            key: value if key in {"default", "const", "enum"} else visit(value)
            for key, value in node.items()
            if key != "$defs" and not (key == "default" and value is None)
        }
        # Nullable constraints apply only to their matching JSON type, so an optional
        # integer/string/array can share one shape with null without repeating anyOf.
        variants = result.get("anyOf")
        if variants and len(variants) == 2 and {"type": "null"} in variants:
            target = next(item for item in variants if item != {"type": "null"})
            if "type" in target and not ({"enum", "const"} & target.keys()):
                result.pop("anyOf")
                result.update(target)
                types = target["type"] if isinstance(target["type"], list) else [target["type"]]
                result["type"] = [*types, "null"]
        # Projection can turn several large variants into the same object shape.
        # Such branches overlap: oneOf would reject every object instead of
        # advertising the intended broad shape. Keep a valid union of unique shapes.
        for key in ("anyOf", "oneOf"):
            if key not in result:
                continue
            unique = []
            for item in result[key]:
                if item not in unique:
                    unique.append(item)
            if {"type": "object"} in unique:
                unique = [
                    item
                    for item in unique
                    if item.get("type") != "object" or item == {"type": "object"}
                ]
            if len(unique) == 1:
                result.pop(key)
                result.update(unique[0])
            elif unique != result[key]:
                result.pop(key)
                result["anyOf"] = unique
        if "enum" in result or "const" in result:
            result.pop("type", None)  # Values already determine their JSON types.
        return result

    return visit(compact(schema))


def describe(op):
    """Project registry contracts into compact, offline-compatible MCP declarations."""
    value = op.describe()
    fields = {"project": (str, Field(..., json_schema_extra={"x-cybersprite-path": "project"}))}
    if op.kind in {"mutate", "ingest"}:
        fields.update(
            {name: (f.annotation, deepcopy(f)) for name, f in TxOptions.model_fields.items()}
        )
    schema = create_model(op.name + "MCPInput", __base__=op.args, **fields).model_json_schema(
        by_alias=True
    )
    value["argumentSchema"] = schema
    value["inputSchema"] = compact_input(schema)
    value["outputSchema"] = deepcopy(ENVELOPE_SCHEMA)
    value["description"] = value["description"].split(" Coordinates are integer pixels")[0]
    return value
