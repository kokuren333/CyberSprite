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
add_source register_reference list_sources get_source list_generators generate_image
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
            and key != "x-cybersprite-region-mask"
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

    result = visit(compact(schema))
    # Each tool is self-contained. Share identical property shapes locally only
    # when the complete serialized schema gets smaller, including definition cost.
    properties = result.get("properties", {})
    groups = {}
    for name, shape in properties.items():
        key = json.dumps(shape, sort_keys=True)
        groups.setdefault(key, []).append(name)
    for key in sorted(groups):
        names = groups[key]
        if len(names) < 2:
            continue
        candidate = deepcopy(result)
        definitions = candidate.setdefault("$defs", {})
        name = "S" + str(len(definitions))
        definitions[name] = properties[names[0]]
        for field in names:
            candidate["properties"][field] = {"$ref": "#/$defs/" + name}
        if len(json.dumps(candidate)) < len(json.dumps(result)):
            result = candidate
    return result


# Concise presentation only; full descriptions remain in registry contracts.
MCP_DESCRIPTIONS = dict(
    line.split(":", 1)
    for line in """
new_project:Create or open a project.
get_info:Read selected project sections.
list_platforms:List or resolve platforms.
set_platform:Set the platform snapshot.
get_pixels:Read indexed pixel rows.
get_palette:Read palette entries and names.
validate:Validate structure and quality.
render_preview:Render decorated previews.
diff_preview:Compare history revisions.
get_history:Read recent history.
undo:Undo the last transaction.
redo:Redo the last undo.
apply_ops:Apply operations atomically.
set_project_meta:Set project metadata.
set_validation:Set quality rule settings.
set_pixel:Write one indexed pixel.
set_pixels:Write indexed pixel points.
draw_rows:Write encoded pixel rows.
line:Draw an integer line.
rect:Draw a rectangle.
ellipse:Draw an integer ellipse.
polygon:Draw a polygon.
stroke:Draw a freehand path.
fill:Flood-fill a connected region.
erase:Erase a selected region.
replace_color:Replace an exact palette index.
transform_region:Move or transform a region.
outline:Outline selected opaque pixels.
shift_ramp:Shift one step within a ramp.
cleanup_pixels:Remove small pixel clusters.
add_frame:Insert timeline frames.
delete_frames:Delete timeline frames.
move_frames:Reorder timeline frames.
reverse_frames:Reverse a frame selection.
set_frame_duration:Set frame durations in ms.
set_cel:Set cel position or opacity.
clear_cel:Clear selected cels.
copy_cel:Copy a cel.
link_cel:Link to a cel's image data.
unlink_cel:Detach linked cel data.
move_cel:Move with explicit sharing scope.
set_frame_ticks:Allocate rational frame ticks.
conform_palette:Conform RGB to platform colors.
set_palette:Replace the exact palette.
set_palette_color:Set one palette entry.
add_palette_colors:Append palette colors.
remap_palette:Remap indices project-wide.
load_palette:Load and remap a palette.
set_palette_frozen:Freeze or unfreeze the palette.
add_layer:Create a layer.
update_layer:Set layer properties.
delete_layer:Delete a layer subtree.
duplicate_layer:Copy a layer subtree.
merge_layers:Merge adjacent sibling layers.
flatten:Flatten layers preserving RGBA.
add_tag:Create an animation tag.
update_tag:Set tag properties.
delete_tag:Delete a tag.
add_slice:Create a named slice.
update_slice:Set slice keys or properties.
delete_slice:Delete a slice.
add_tileset:Create a tile set.
delete_tileset:Delete an unreferenced tile set.
set_tile_pixels:Edit a tile's indexed pixels.
delete_tiles:Delete tiles and fix references.
move_tiles:Reorder tiles and fix references.
set_tile:Place one tile reference.
set_tiles:Place a tile grid.
get_tiles:Read tile references.
tileset_from_layer:Extract a layer into tiles.
resize_canvas:Resize with an integer anchor.
crop_canvas:Crop canvas and cel positions.
scale_sprite:Scale by an integer factor.
transform_sprite:Flip or quarter-turn the sprite.
import_image:Convert, check gates and place.
import_aseprite:Import with source provenance.
export_image:Export and verify raster images.
export_sheet:Export and verify a sprite sheet.
export_animation:Export and verify GIF or APNG.
export_aseprite:Export and verify project data.
export_tileset:Export and verify tile images.
export_palette:Export and verify the palette.
export_plugin:Export using an enabled plugin.
export_native:Export and decode native tiles.
add_source:Register design originals only.
list_sources:List stored source provenance.
get_source:Read one source and its report.
""".strip().splitlines()
)


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
    value["description"] = MCP_DESCRIPTIONS.get(
        op.name, value["description"].split(" Coordinates are integer pixels")[0]
    )
    return value
