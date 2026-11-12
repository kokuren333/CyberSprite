"""English operation and argument documentation used by the registry schemas."""

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, create_model

ARGUMENTS = {
    "mask": "Optional protection: only_on/not_on colors and region, tested once before drawing.",
    "legend": (
        "Symbol-to-color mapping for sym rows; indices, exact colors or @name. Dot is reserved."
    ),
    "exclude_colors": (
        "Colors excluded from outline seeds; excluding the outside outline color is idempotent."
    ),
    "guide": (
        "Design source beside the preview: source, file, x/y crop origin, integer scale, mode=side."
    ),
    "tile_w": "Tile width in pixels (1-256).",
    "tile_h": "Tile height in pixels (1-256).",
    "tile": "Zero-based tile index; set_tile_pixels also accepts new to append.",
    "tiles": "Zero-based tile indices to delete; tile zero is immutable.",
    "col": "Zero-based column on the cel grid, including its origin offset.",
    "row": "Zero-based row on the cel grid, including its origin offset.",
    "base_index": "Display-only starting tile number; stored indices always start at zero.",
    "match_flips": "Permit exact existing tile matches with x, y, or diagonal reflections.",
    "on_used": "Reject deletion of referenced tiles, or clear their placements explicitly.",
    "layer": "Target layer ID, unique name, or group path.",
    "frame": "Zero-based frame index.",
    "frames": "Frame selection: zero-based index, index list, all, range 0-3, or tag:name.",
    "x": "Horizontal pixel coordinate from the canvas left edge.",
    "y": "Vertical pixel coordinate from the canvas top edge.",
    "x0": "Horizontal pixel coordinate of the line start, inclusive.",
    "y0": "Vertical pixel coordinate of the line start, inclusive.",
    "x1": "Horizontal pixel coordinate of the line end, inclusive.",
    "y1": "Vertical pixel coordinate of the line end, inclusive.",
    "w": "Width in integer pixels.",
    "h": "Height in integer pixels.",
    "width": "Width in integer pixels.",
    "height": "Height in integer pixels.",
    "color": "Palette index, @name, or an exact palette color; editing never approximates colors.",
    "colors": "Ordered palette colors as #rrggbbaa strings, at most 256 entries.",
    "pixels": "Pixel triples [x, y, palette index or exact palette color].",
    "points": "Ordered integer [x, y] coordinates.",
    "rows": "Rectangular pixel row strings using the selected format.",
    "format": (
        "Pixel row encoding: hex uses two hexadecimal digits per palette index; sym "
        "uses one character from "
        "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ for indices "
        "0-61 and . for the transparent index (palette at most 62 colors)."
    ),
    "skip_transparent": "Leave existing pixels unchanged where input uses the transparent index.",
    "brush": "Integer brush size (1-64) and square or circle footprint.",
    "filled": "Fill the shape interior instead of drawing only its boundary.",
    "closed": "Join the final polygon point back to the first.",
    "pixel_perfect": "Remove redundant corner pixels for a size-one stroke.",
    "connectivity": "Neighbor connectivity: 4 uses edges, 8 also includes diagonals.",
    "sample": "Read flood-fill boundaries from this layer or the rendered composite.",
    "region": (
        "Canvas selection: all, rect, ellipse, polygon, mask, color, wand, bounded and/or/not tree."
    ),
    "from_": "Inclusive starting frame index.",
    "to": "Inclusive ending frame index.",
    "layers": "Layer references to include; omission uses the operation default selection.",
    "tilesets": "Also process tileset pixels when supported.",
    "action": "Move selected pixels (clearing the source) or copy them.",
    "dx": "Horizontal integer displacement; positive moves right.",
    "dy": "Vertical integer displacement; positive moves down.",
    "flip": "Horizontal (h) or vertical (v) reflection; omit to keep orientation.",
    "rotate": "Clockwise rotation in integer degrees: 0, 90, 180, or 270.",
    "target_layer": "Destination layer reference; omit to use the source layer.",
    "target_frame": "Destination zero-based frame index; omit to use the source frame.",
    "overwrite_transparent": "Allow transparent input pixels to erase destination pixels.",
    "placement": "Put the outline outside or inside the existing opaque silhouette.",
    "min_cluster": "Minimum connected same-color component size to retain.",
    "protect": "Palette indices or exact palette colors that cleanup must preserve.",
    "max_passes": "Maximum cleanup passes; processing stops when no pixels change.",
    "at": "Insertion frame index; omit to append.",
    "count": "Number of frames to insert.",
    "duration_ms": "Frame display duration in integer milliseconds (1-65535).",
    "cels": (
        "Initialize inserted cels as empty, independent copies, links, or automatic continuity."
    ),
    "copy_from": "Zero-based source frame for copied or linked cels.",
    "before": "Move the selected frame range before this zero-based index.",
    "opacity": "Opacity from 0 (transparent) to 255 (opaque).",
    "z_index": "Integer cel stacking offset relative to layer order.",
    "user_data": "Typed user metadata (text, display color, and properties).",
    "to_layer": "Destination layer reference; omit to use the source layer.",
    "to_frame": "Zero-based destination frame index.",
    "mode": "Copy or move the source cel.",
    "on_conflict": "How to handle an occupied destination: replace, error, or skip.",
    "source_frame": "Zero-based frame owning the image data to link.",
    "names": "Palette-index keys mapped to human-readable color names.",
    "transparent_index": "Palette index representing transparent pixels.",
    "on_shrink": "Policy for removed palette entries: error, remap_nearest, or to_transparent.",
    "index": "Zero-based palette entry index.",
    "name": "Human-readable resource name, at most 255 characters.",
    "reuse_existing": "Reuse exact matching palette colors instead of appending duplicates.",
    "order": "Explicit permutation of old palette indices in new order.",
    "sort_by": "Sort palette entries by integer perceptual lightness, hue, or pixel usage.",
    "merge_duplicates": "Share identical entries instead of keeping duplicates.",
    "remove_unused": "Remove palette entries with no pixel references.",
    "keep_transparent_first": "Keep the transparent palette entry at index zero.",
    "source": "Palette preset name or palette file path.",
    "frozen": "Prevent adding, removing, or changing palette colors while true.",
    "type": "Layer kind: image, group, or tilemap.",
    "parent": "Parent group reference; omit for a top-level layer.",
    "position": "Stack position: top, bottom, or an above/below layer reference.",
    "blend_mode": "Layer blend mode; non-normal modes use the v1 fallback renderer.",
    "visible": "Include this layer in normal rendering.",
    "continuous": "Use linked cels when automatically extending the layer timeline.",
    "tileset": "Tileset ID associated with this operation.",
    "if_exists": "Policy when a matching resource already exists; see the allowed enum values.",
    "locked": "Prevent edits to this layer and its descendants.",
    "collapsed": "Store the group collapsed state for clients.",
    "background": "Background palette index or color; omission preserves transparency.",
    "missing_ok": "Treat an already absent resource as a successful no-op.",
    "down": "Upper layer reference to merge into the layer below it.",
    "flatten": (
        "Require exact palette closure (strict) or explicitly map to nearest palette colors."
    ),
    "visible_only": "Composite only visible layers when flattening.",
    "direction": "Tag playback direction: forward, reverse, pingpong, or pingpong_reverse.",
    "repeat": "Tag repeat/leg count; zero uses the default playback behavior.",
    "tag": "Tag ID or unique name selecting the frame range.",
    "keys": "Ordered slice keys with zero-based frame and integer bounds.",
    "slice": "Slice ID or unique name.",
    "set_key": "Slice key to insert or replace at its frame.",
    "remove_key": "Zero-based frame of the slice key to remove.",
    "anchor": "Canvas resize anchor using compass directions; c means center.",
    "discard_outside": "Discard cel pixels outside the new canvas bounds.",
    "rect": (
        "Integer rectangle {x,y,w,h}; content requests the opaque content bounds when supported."
    ),
    "factor": "Integer nearest-neighbor enlargement factor (2-16).",
    "grid": "Stored integer document grid settings.",
    "pixel_ratio": "Integer display pixel ratio {w,h}.",
    "settings": "Validation settings to patch; omitted fields retain their values.",
    "ops": "Ordered ordinary mutate calls, committed together as one atomic transaction.",
    "label": "Human-readable history label for the transaction.",
    "steps": "Number of history entries to undo or redo (1-200).",
    "palette": "Built-in palette name, palette file path, or ordered RGBA color list.",
    "layer_name": "Name of the initial image layer.",
    "include": "Project information sections to return.",
    "rules": "Quality rule IDs to include; omission evaluates all configured rules.",
    "scale": "Integer nearest-neighbor scale; auto fits previews within their size limit.",
    "rulers": "Add integer coordinate rulers to the diagnostic preview.",
    "onion": "Number of previous and next frames to include as onion skins (0-8 each).",
    "inline": "Include base64 PNG data for clients that display inline images.",
    "from_revision": "Earlier history revision; omission uses the previous revision.",
    "to_revision": "Later history revision; omission uses the current revision.",
    "limit": "Maximum number of recent history entries to return (1-1000).",
}

OPERATIONS = {
    "delete_tileset": (
        "Delete an unused tileset; E_IN_USE lists referencing layers. "
        "Remove or reassign those layers first. missing_ok tolerates only a missing tileset."
    ),
    "add_tileset": "Create a tileset containing immutable transparent tile zero.",
    "set_tile_pixels": "Replace one tile image or append a new tile, affecting all references.",
    "delete_tiles": "Delete tiles, compact indices, and remap or clear all placements atomically.",
    "move_tiles": "Move an inclusive tile range before an old index and remap all placements.",
    "set_tile": "Set one grid placement with canonical x, y, d reflection flags.",
    "set_tiles": "Write rectangular rows of tile references on the cel grid.",
    "get_tiles": "Read a tile rectangle, or the entire trimmed cel when rect is omitted.",
    "tileset_from_layer": "Convert an image layer to a tilemap with exact tile deduplication.",
    "set_pixel": "Write one indexed pixel at an integer canvas coordinate.",
    "set_pixels": (
        "Write explicit pixel triples or color a list of coordinates; later duplicates win."
    ),
    "draw_rows": (
        "Write a rectangular block of palette-index rows at the given top-left coordinate."
    ),
    "line": "Draw an inclusive integer Bresenham line with the selected brush.",
    "rect": "Draw a filled or boundary rectangle within integer pixel bounds.",
    "ellipse": "Draw an integer midpoint ellipse within the supplied bounding rectangle.",
    "polygon": "Draw ordered polygon edges or fill the interior using the even-odd rule.",
    "stroke": "Join stroke points with integer lines and stamp the selected brush.",
    "fill": "Flood-fill the connected equal-index region containing the seed pixel.",
    "erase": "Replace all selected pixels with the transparent palette index.",
    "replace_color": (
        "Replace an exact indexed color in selected regions, frames, and unlocked layers."
    ),
    "transform_region": (
        "Move or copy a selected region with integer translation, reflection, and rotation."
        " Flip is applied first, then clockwise rotation. "
        "Tile flags instead apply transpose, then x flip, then y flip."
    ),
    "outline": "Add an inside or outside outline to opaque pixels using the selected connectivity.",
    "cleanup_pixels": (
        "Replace small same-color pixel components while preserving protected colors."
    ),
    "add_frame": "Insert frames and initialize their cels as empty, copied, linked, or continuous.",
    "delete_frames": "Delete selected frames and remap cels, tags, and slice keys.",
    "move_frames": "Move an inclusive frame range before another frame and remap references.",
    "reverse_frames": "Reverse an inclusive frame range and remap timeline references.",
    "set_frame_duration": "Set the integer millisecond duration of selected frames.",
    "set_cel": "Patch cel position, stacking offset, opacity, and user metadata.",
    "clear_cel": "Remove the cel at a layer/frame without deleting the layer or frame.",
    "copy_cel": "Copy or move a cel to another layer/frame with an explicit conflict policy.",
    "link_cel": "Make selected frames share the source frame image data.",
    "unlink_cel": "Replace a linked cel with an independent copy of its resolved image data.",
    "set_palette": "Replace the ordered palette with an explicit policy for removed indices.",
    "set_palette_color": "Change one palette entry and optionally its stored name.",
    "add_palette_colors": (
        "Append exact RGBA colors or reuse existing entries and return their indices."
    ),
    "remap_palette": (
        "Reorder, merge, or prune palette entries and rewrite every affected pixel reference."
    ),
    "load_palette": "Read a named preset or palette file and replace or append its exact colors.",
    "set_palette_frozen": "Freeze or unfreeze palette changes without changing pixel data.",
    "add_layer": "Create an image, group, or tilemap layer at an explicit stack position.",
    "update_layer": "Patch layer properties, parent, stack position, and metadata.",
    "delete_layer": "Delete a layer and its descendants with an optional missing-resource no-op.",
    "duplicate_layer": "Copy a layer subtree with fresh IDs and independent cel data.",
    "merge_layers": (
        "Composite selected layers into one, requiring palette closure unless nearest is explicit."
    ),
    "flatten": "Composite the selected document layers into one indexed image layer.",
    "add_tag": "Create a named inclusive frame range with playback direction and repeat settings.",
    "update_tag": "Patch tag range, playback settings, name, color, metadata, or list position.",
    "delete_tag": "Delete a tag by ID or unique name.",
    "add_slice": (
        "Create a named slice with integer frame-specific bounds and optional center/pivot."
    ),
    "update_slice": "Patch slice properties or insert, replace, and remove individual frame keys.",
    "delete_slice": "Delete a slice by ID or unique name.",
    "resize_canvas": (
        "Resize integer canvas bounds around an anchor, optionally discarding outside pixels."
    ),
    "crop_canvas": "Crop to an explicit rectangle or the opaque content bounds.",
    "scale_sprite": "Enlarge canvas, cels, slices, and grid by an integer nearest-neighbor factor.",
    "transform_sprite": "Reflect or quarter-turn the complete sprite using integer coordinates.",
    "set_project_meta": "Patch project name, grid, pixel ratio, and user metadata.",
    "set_validation": "Patch quality rule thresholds and severities used after every transaction.",
    "apply_ops": "Apply an ordered batch of ordinary mutate operations as one atomic transaction.",
    "undo": (
        "Restore preceding history states and commit the restored data as a new "
        "revision with previews."
    ),
    "redo": (
        "Restore undone history states and commit the restored data as a new "
        "revision with previews."
    ),
    "new_project": (
        "Create an indexed project at revision zero, or open a dimension-compatible "
        "existing project."
    ),
    "get_info": (
        "Read selected project structure, palette, source, validation, or history sections."
    ),
    "get_pixels": (
        "Read an integer canvas rectangle as exact hexadecimal or symbolic palette-index rows."
    ),
    "get_palette": (
        "Read the ordered palette, transparent index, freeze state, names, and pixel usage."
    ),
    "validate": (
        "Evaluate structural invariants and configured quality rules with deterministic metrics."
    ),
    "render_preview": (
        "Render separate frames (at most eight) or a composite strip/grid with diagnostic overlays."
        " Set tileset to render a labeled grid of its zero-based data indices instead."
    ),
    "diff_preview": "Compare history revisions with pixel counts and before/after/highlight PNGs.",
    "get_history": "Read recent transaction entries and whether undo or redo is available.",
}

OPERATIONS["move_cel"] = "Move a cel by integer offsets with explicit frame or shared scope."

OVERRIDES = {
    (
        "update_layer",
        "background",
    ): "Make this image layer an opaque canvas-sized bottom background when true.",
    ("add_tag", "color"): "Raw display color as #rrggbb; it need not belong to the palette.",
    ("update_tag", "color"): "Raw display color as #rrggbb; it need not belong to the palette.",
    (
        "add_slice",
        "color",
    ): "Raw display color as #rrggbb or #rrggbbaa; it need not belong to the palette.",
    (
        "update_slice",
        "color",
    ): "Raw display color as #rrggbb or #rrggbbaa; it need not belong to the palette.",
    (
        "render_preview",
        "background",
    ): "Checker, palette index/exact color, or raw #rrggbb decoration.",
    ("set_tile", "flip"): "Reflection flags in x, y, d order; diagonal is applied first.",
    ("set_tiles", "rows"): "Tile reference rows, e.g. 0 1 1x 2yd, separated by spaces.",
    ("move_tiles", "from_"): "First zero-based tile index of the inclusive range (at least one).",
    ("move_tiles", "to"): "Last zero-based tile index of the inclusive range.",
    ("move_tiles", "before"): "Old tile index before which to insert; tile count appends.",
    ("get_tiles", "rect"): "Rectangle {x,y,w,h} in grid tile units; omission reads the whole cel.",
    ("replace_color", "from_"): "Palette index or exact palette color to replace.",
    ("replace_color", "to"): "Replacement palette index or exact palette color.",
    ("load_palette", "mode"): "Replace the palette or append imported colors.",
    ("new_project", "frames"): "Initial frame count (at least one).",
    (
        "set_palette_color",
        "color",
    ): "New RGBA color as #rrggbbaa; this operation explicitly edits the palette.",
    ("render_preview", "grid"): "Overlay the stored integer document grid.",
    ("update_tag", "position"): "Zero-based position in the ordered tag list.",
}


def argument_model(name: str, model: type[BaseModel]) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for key, original in model.model_fields.items():
        field = deepcopy(original)
        if not field.description:
            field.description = OVERRIDES.get((name, key), ARGUMENTS[key])
        fields[key] = (field.annotation, field)
    return create_model(model.__name__, __base__=model, **fields)
