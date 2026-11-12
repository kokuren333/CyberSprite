"""Layer, tag, slice and project metadata operations."""

from copy import deepcopy

from pydantic import ValidationError

from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.models import (
    GroupLayer,
    ImageCel,
    ImageLayer,
    Slice,
    Tag,
    TilemapLayer,
    ValidationSettings,
)
from cybersprite.core.pixels import pixels_to_rows, rgba
from cybersprite.core.references import resolve_layer, resolve_tag, walk_layers
from cybersprite.core.render import indexed_result

from .common import background_fit, fail, frame_index, siblings, unlocked


def destination(p, parent):
    if parent is None:
        return p.layers
    node = resolve_layer(p, parent)
    unlocked(p, node)
    if not isinstance(node, GroupLayer):
        fail("E_WRONG_LAYER_TYPE", "Parent must be a group.", type=node.type)
    return node.children


def place(p, items, layer, position):
    if position == "top":
        index = len(items)
    elif position == "bottom":
        index = int(bool(items and isinstance(items[0], ImageLayer) and items[0].background))
    else:
        data = position.model_dump()
        key = next(iter(data))
        ref = resolve_layer(p, data[key])
        if ref not in items:
            raise invalid("Position reference must have the same parent.")
        index = items.index(ref) + int(key == "above")
    items.insert(index, layer)


def layer_op(ctx, a, name):
    p = ctx.project
    if name == "add_layer":
        items = destination(p, a.parent)
        matches = [node for node in items if node.name == a.name]
        if matches and a.if_exists != "allow":
            if a.if_exists == "reuse":
                return {"id": matches[0].id}
            fail("E_EXISTS", "Layer name already exists under this parent.", id=matches[0].id)
        if sum(1 for _ in walk_layers(p.layers)) >= 1024:
            fail("E_LIMIT_EXCEEDED", "Layer count cannot exceed 1024.", limit=1024)
        values = dict(
            id=p.id_counters.issue("layer"),
            name=a.name,
            opacity=a.opacity,
            blend_mode=a.blend_mode,
            visible=a.visible,
        )
        if a.type == "group":
            layer = GroupLayer(**values)
        elif a.type == "image":
            layer = ImageLayer(**values, continuous=a.continuous)
        else:
            if a.tileset not in [ts.id for ts in p.tilesets]:
                fail("E_TILESET_NOT_FOUND", "A tilemap layer requires an existing tileset ID.")
            layer = TilemapLayer(**values, continuous=a.continuous, tileset=a.tileset)
        place(p, items, layer, a.position)
        return {"id": layer.id}
    if name == "flatten":
        # Preserve the root ID, so invoking this naturally idempotent operation twice is a no-op.
        layers = [node.id for node, _ in walk_layers(p.layers) if not isinstance(node, GroupLayer)]
        for node, _ in walk_layers(p.layers):
            unlocked(p, node)
        if (
            len(p.layers) == 1
            and isinstance(p.layers[0], ImageLayer)
            and (
                p.layers[0].opacity == 255
                and p.layers[0].blend_mode == "normal"
                and p.layers[0].visible
            )
        ):
            return {}
        if not layers:
            layer = ImageLayer(id=p.layers[0].id, name=p.layers[0].name)
        else:
            bottom = next(node for node, _ in walk_layers(p.layers) if node.id == layers[0])
            layer = ImageLayer(id=bottom.id, name=bottom.name)
        for f in range(len(p.frames)):
            data = indexed_result(
                p, f, {"include_hidden": not a.visible_only, "flatten": a.flatten}
            ).pixels
            layer.cels.append(
                ImageCel(
                    frame=f,
                    x=0,
                    y=0,
                    w=p.canvas.width,
                    h=p.canvas.height,
                    pixels=pixels_to_rows(data),
                )
            )
        p.layers = [layer]
        return {}
    if name == "merge_layers":
        if (a.layers is None) == (a.down is None):
            raise invalid("Provide layers or down, exclusively.")
        if a.down is not None:
            upper = resolve_layer(p, a.down)
            items = siblings(p, upper)
            index = items.index(upper)
            if index == 0:
                raise invalid("No layer exists immediately below this layer.")
            chosen = [items[index - 1], upper]
        else:
            chosen = [resolve_layer(p, ref) for ref in a.layers]
            items = siblings(p, chosen[0]) if chosen else []
        if len({node.id for node in chosen}) < 2 or any(node not in items for node in chosen):
            raise invalid("Merge requires at least two distinct layers with the same parent.")
        for node in chosen:
            unlocked(p, node)
            if not isinstance(node, ImageLayer):
                fail("E_WRONG_LAYER_TYPE", "Merge requires image layers.")
        chosen.sort(key=items.index)
        bottom = chosen[0]
        # Render in an isolated root so group opacity is not applied twice after the merge.
        temp = deepcopy(p)
        temp.layers = deepcopy(chosen)
        cels = []
        for f in range(len(p.frames)):
            data = indexed_result(temp, f, {"include_hidden": True, "flatten": a.flatten}).pixels
            cels.append(
                ImageCel(
                    frame=f,
                    x=0,
                    y=0,
                    w=p.canvas.width,
                    h=p.canvas.height,
                    pixels=pixels_to_rows(data),
                )
            )
        bottom.cels, bottom.opacity, bottom.blend_mode = cels, 255, "normal"
        for node in chosen[1:]:
            items.remove(node)
        return {"id": bottom.id}
    try:
        layer = resolve_layer(p, a.layer)
    except CyberSpriteError as error:
        if name == "delete_layer" and a.missing_ok and error.code == "E_LAYER_NOT_FOUND":
            return {}
        raise
    items = siblings(p, layer)
    if name == "update_layer":
        # A locked layer can be unlocked or have display properties updated.
        changing_content = a.model_fields_set & {"background", "parent", "position"}
        if changing_content:
            unlocked(p, layer)
        for key in sorted(a.model_fields_set - {"layer", "parent", "position", "background"}):
            if not hasattr(layer, key):
                fail("E_WRONG_LAYER_TYPE", f"Layer type {layer.type} has no {key} property.")
            setattr(layer, key, deepcopy(getattr(a, key)))
        if a.parent is not None or a.position is not None or "parent" in a.model_fields_set:
            if a.parent is not None and isinstance(layer, GroupLayer):
                if a.parent in [n.id for n, _ in walk_layers([layer])] or resolve_layer(
                    p, a.parent
                ).id in [n.id for n, _ in walk_layers([layer])]:
                    raise invalid("A group cannot be moved under itself or its descendants.")
            target = destination(p, a.parent) if "parent" in a.model_fields_set else items
            items.remove(layer)
            place(p, target, layer, a.position or "top")
        if a.background is not None:
            if not isinstance(layer, ImageLayer):
                fail("E_WRONG_LAYER_TYPE", "Only image layers can be backgrounds.")
            if a.background:
                for node, _ in walk_layers(p.layers):
                    if isinstance(node, ImageLayer) and node is not layer and node.background:
                        raise invalid("Only one background layer is allowed.", layer=node.id)
                siblings(p, layer).remove(layer)
                p.layers.insert(0, layer)
                layer.opacity, layer.blend_mode = 255, "normal"
            layer.background = a.background
            background_fit(p, layer)
        return {}
    unlocked(p, layer)
    if name == "delete_layer":
        remaining = [
            n
            for n, _ in walk_layers(p.layers)
            if n.id not in {item.id for item, _ in walk_layers([layer])}
        ]
        if not remaining:
            raise invalid("At least one layer must remain.")
        items.remove(layer)
        return {}
    copy = deepcopy(layer)
    for node, _ in walk_layers([copy]):
        node.id = p.id_counters.issue("layer")
        if isinstance(node, ImageLayer):
            node.background = False
    copy.name = a.name or layer.name + " copy"
    items.insert(items.index(layer) + 1, copy)
    return {"id": copy.id}


def resolve_slice(p, ref):
    matches = [s for s in p.slices if s.id == ref] or [s for s in p.slices if s.name == ref]
    if not matches:
        fail(
            "E_SLICE_NOT_FOUND",
            "Slice was not found.",
            reference=ref,
            candidates=[s.id for s in p.slices],
        )
    if len(matches) != 1:
        fail(
            "E_AMBIGUOUS_REF",
            "Slice name matches multiple slices; use an ID.",
            candidates=[s.id for s in matches],
        )
    return matches[0]


def tag_slice_op(ctx, a, name):
    p = ctx.project
    kind = "tag" if name.endswith("tag") else "slice"
    if kind == "slice" and getattr(a, "color", None) is not None:
        rgba(a.color)
        if len(a.color) == 7:
            a = a.model_copy(update={"color": a.color + "ff"})
    items = p.tags if kind == "tag" else p.slices
    resolver = resolve_tag if kind == "tag" else resolve_slice
    if name.startswith("add_"):
        matches = [item for item in items if item.name == a.name]
        if matches and a.if_exists == "error":
            fail("E_EXISTS", f"{kind.title()} name already exists.", id=matches[0].id)
        values = a.model_dump(exclude={"if_exists"}, exclude_none=True)
        if matches and a.if_exists == "update":
            item = matches[0]
            for key in sorted(values):
                setattr(item, key, deepcopy(values[key]) if key != "keys" else deepcopy(a.keys))
        else:
            if len(items) >= (1024 if kind == "tag" else 4096):
                fail("E_LIMIT_EXCEEDED", f"Too many {kind} objects.")
            cls = Tag if kind == "tag" else Slice
            item = cls(id=p.id_counters.issue(kind), **values)
            items.append(item)
    else:
        try:
            item = resolver(p, getattr(a, kind))
        except CyberSpriteError as error:
            if (
                name.startswith("delete_")
                and a.missing_ok
                and error.code == f"E_{kind.upper()}_NOT_FOUND"
            ):
                return {}
            raise
        if name.startswith("delete_"):
            items.remove(item)
            return {}
        for key in sorted(a.model_fields_set - {kind, "position", "set_key", "remove_key"}):
            setattr(item, key, deepcopy(getattr(a, key)))
        if kind == "tag" and a.position is not None:
            if not 0 <= a.position < len(items):
                raise invalid("Tag position is outside the tag array.")
            items.remove(item)
            items.insert(a.position, item)
        if kind == "slice":
            if a.set_key is not None:
                item.keys = [k for k in item.keys if k.frame != a.set_key.frame] + [
                    deepcopy(a.set_key)
                ]
            if a.remove_key is not None:
                item.keys = [k for k in item.keys if k.frame != a.remove_key]
    if kind == "tag":
        if not 0 <= item.from_ <= item.to < len(p.frames):
            raise invalid("Tag requires 0 <= from <= to < frame count.")
        if not 0 <= item.repeat <= 65535 or len(rgba(item.color)) != 4 or len(item.color) != 7:
            raise invalid("Tag repeat must be 0..65535 and color must be #rrggbb.")
    else:
        if not item.keys or len({k.frame for k in item.keys}) != len(item.keys):
            raise invalid("Slice requires nonempty keys with unique frames.")
        for key in item.keys:
            frame_index(p, key.frame)
        item.keys.sort(key=lambda k: k.frame)
        rgba(item.color)
        if len(item.color) != 9:
            raise invalid("Slice color must be #rrggbbaa.")
    return {"id": item.id} if name.startswith("add_") else {}


def metadata_op(ctx, a, name):
    p = ctx.project
    if name == "set_project_meta":
        for key in sorted(a.model_fields_set):
            if key in ("grid", "pixel_ratio"):
                setattr(p.canvas, key, deepcopy(getattr(a, key)))
            else:
                setattr(p, key, deepcopy(getattr(a, key)))
        if (p.canvas.pixel_ratio.w, p.canvas.pixel_ratio.h) not in ((1, 1), (2, 1), (1, 2)):
            raise invalid("pixel_ratio must be 1:1, 2:1, or 1:2.")
        return {}
    values = p.validation.model_dump()
    values.update(a.settings.model_dump(exclude_unset=True))
    try:
        p.validation = ValidationSettings.model_validate(values)
    except ValidationError as error:
        raise invalid("Invalid validation settings.", reason=str(error)) from error
    return {"validation": p.validation.model_dump()}
