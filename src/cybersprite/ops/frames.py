"""Frame permutation and cel operations preserve shared data before renumbering."""

from copy import deepcopy

from cybersprite.core.errors import invalid
from cybersprite.core.models import Frame, GroupLayer, ImageLayer, LinkCel
from cybersprite.core.references import cel_at, cel_owner, resolve_layer, walk_layers

from .common import (
    background_fit,
    detach,
    fail,
    frame_index,
    frames,
    groups,
    put_cel,
    set_groups,
    unlocked,
)


def remap(p, mapping, *, insertion=None):
    for layer, _ in walk_layers(p.layers):
        if isinstance(layer, GroupLayer):
            continue
        values = groups(layer)
        set_groups(
            layer,
            [
                (owner, {mapping[f]: z for f, z in members.items() if f in mapping})
                for owner, members in values
            ],
        )
    removed = []
    for tag in list(p.tags):
        if insertion is not None:
            at, count = insertion
            if at <= tag.from_:
                tag.from_ += count
                tag.to += count
            elif at <= tag.to:
                tag.to += count
        else:
            remaining = [f for f in range(tag.from_, tag.to + 1) if f in mapping]
            if not remaining:
                removed.append(tag.id)
                p.tags.remove(tag)
                continue
            # Surviving endpoints delimit the remapped interval, even if order reverses.
            tag.from_, tag.to = sorted((mapping[remaining[0]], mapping[remaining[-1]]))
    for slc in p.slices:
        moved = {}
        for key in slc.keys:
            if key.frame in mapping:
                new = deepcopy(key)
                new.frame = mapping[key.frame]
                moved[new.frame] = new
        for key in slc.keys:
            if key.frame not in mapping:
                later = [f for f in sorted(mapping) if f > key.frame]
                if later:
                    target = mapping[later[0]]
                    if target not in moved:
                        new = deepcopy(key)
                        new.frame = target
                        moved[target] = new
        # A key after the last surviving frame has no successor and is discarded.
        slc.keys = [moved[f] for f in sorted(moved)]
    p.slices = [slc for slc in p.slices if slc.keys]
    return removed


def frame_op(ctx, a, name):
    p = ctx.project
    n = len(p.frames)
    if name == "add_frame":
        at = n if a.at is None else a.at
        if not 0 <= at <= n:
            fail("E_FRAME_OUT_OF_RANGE", "Insertion position is out of range.", frames=n)
        if n + a.count > 4096:
            fail("E_LIMIT_EXCEEDED", "Frame count exceeds 4096.", limit=4096)
        source = max(0, at - 1) if a.copy_from is None else frame_index(p, a.copy_from)
        duration = a.duration_ms or p.frames[max(0, at - 1)].duration_ms
        saved = {
            layer.id: deepcopy(cel_owner(layer, cel_at(layer, source)))
            for layer, _ in walk_layers(p.layers)
            if not isinstance(layer, GroupLayer)
        }
        mapping = {f: f if f < at else f + a.count for f in range(n)}
        remap(p, mapping, insertion=(at, a.count))
        p.frames[at:at] = [Frame(duration_ms=duration) for _ in range(a.count)]
        for layer, _ in walk_layers(p.layers):
            if isinstance(layer, GroupLayer):
                continue
            mode = "link" if a.cels == "auto" and layer.continuous else a.cels
            if mode == "auto":
                mode = "empty"
            if isinstance(layer, ImageLayer) and layer.background and mode == "empty":
                mode = "copy"
            cel = saved[layer.id]
            if cel is None or mode == "empty":
                continue
            if mode == "copy":
                for f in range(at, at + a.count):
                    put_cel(layer, cel, f)
            else:
                values = groups(layer)
                for _owner, members in values:
                    if mapping[source] in members:
                        members.update({f: cel.z_index for f in range(at, at + a.count)})
                set_groups(layer, values)
            background_fit(p, layer)
        return {"frames": list(range(at, at + a.count))}
    if name == "delete_frames":
        selected = frames(p, a.frames)
        if len(selected) == n:
            raise invalid("At least one frame must remain.")
        order = [f for f in range(n) if f not in selected]
        mapping = {f: i for i, f in enumerate(order)}
        removed = remap(p, mapping)
        p.frames = [p.frames[f] for f in order]
        return {"deleted": selected, "removed_tags": removed}
    if name in ("move_frames", "reverse_frames"):
        start, end = frame_index(p, a.from_), frame_index(p, a.to)
        if start > end:
            raise invalid("from must not exceed to.")
        order = list(range(n))
        if name == "reverse_frames":
            order[start : end + 1] = reversed(order[start : end + 1])
        else:
            block = order[start : end + 1]
            del order[start : end + 1]
            before = len(order) if a.before == n else a.before
            if not 0 <= before <= len(order):
                raise invalid("before must be an insertion index in the remaining sequence.")
            order[before:before] = block
        mapping = {old: new for new, old in enumerate(order)}
        remap(p, mapping)
        p.frames = [p.frames[f] for f in order]
        return (
            {"mapping": {str(k): mapping[k] for k in sorted(mapping)}}
            if name == "move_frames"
            else {}
        )
    if name == "set_frame_duration":
        for f in frames(p, a.frames):
            p.frames[f].duration_ms = a.duration_ms
        return {}
    layer = resolve_layer(p, a.layer)
    unlocked(p, layer)
    if isinstance(layer, GroupLayer):
        fail("E_WRONG_LAYER_TYPE", "Groups do not have cels.", type=layer.type)
    frame = a.source_frame if name == "link_cel" else a.frame
    frame_index(p, frame)
    cel = cel_at(layer, frame)
    owner = cel_owner(layer, cel)
    if name == "clear_cel":
        if isinstance(layer, ImageLayer) and layer.background:
            detach(layer, frame)
            background_fit(p, layer)
        else:
            detach(layer, frame)
        return {}
    if owner is None:
        fail("E_CEL_NOT_FOUND", "No cel exists at this frame.", layer=layer.id, frame=frame)
    linked = [
        c.frame
        for c in layer.cels
        if c.frame == owner.frame or isinstance(c, LinkCel) and c.link == owner.frame
    ]
    if name == "set_cel":
        if (
            isinstance(layer, ImageLayer)
            and layer.background
            and (a.x not in (None, 0) or a.y not in (None, 0))
        ):
            raise invalid("Background cel position must remain (0, 0); resize the canvas instead.")
        for key in sorted(a.model_fields_set - {"layer", "frame", "z_index"}):
            setattr(owner, key, deepcopy(getattr(a, key)))
        if a.z_index is not None:
            cel.z_index = a.z_index
        if len(linked) > 1 and a.model_fields_set - {"layer", "frame", "z_index"}:
            ctx.linked_frames.update(linked)
            ctx.link_groups.add(tuple(sorted(linked)))
    elif name == "unlink_cel":
        if len(linked) > 1:
            copy = deepcopy(owner)
            copy.z_index = cel.z_index
            put_cel(layer, copy, frame)
    elif name == "copy_cel":
        target = resolve_layer(p, a.to_layer or a.layer)
        unlocked(p, target)
        frame_index(p, a.to_frame)
        if target.type != layer.type:
            fail("E_WRONG_LAYER_TYPE", "Source and target cel types must match.")
        if layer.type == "tilemap" and target.tileset != layer.tileset:
            raise invalid("Copy tilemap cels only between layers using the same tileset.")
        if target is layer and frame == a.to_frame:
            return {}
        if cel_at(target, a.to_frame) is not None:
            if a.on_conflict == "error":
                fail("E_EXISTS", "Destination cel already exists.", frame=a.to_frame)
            if a.on_conflict == "skip":
                return {}
        copy = deepcopy(owner)
        copy.z_index = cel.z_index
        put_cel(target, copy, a.to_frame)
        if a.mode == "move":
            detach(layer, frame)
            background_fit(p, layer)
    elif name == "link_cel":
        selected = frames(p, a.frames)
        values = groups(layer)
        shared = next((o, m) for o, m in values if frame in m)
        for _o, members in values:
            for f in selected:
                if f != frame:
                    members.pop(f, None)
        shared[1].update(
            {f: cel_at(layer, f).z_index if cel_at(layer, f) else cel.z_index for f in selected}
        )
        set_groups(layer, values)
        ctx.linked_frames.update(sorted(shared[1]))
        if len(shared[1]) > 1:
            ctx.link_groups.add(tuple(sorted(shared[1])))
    return {}
