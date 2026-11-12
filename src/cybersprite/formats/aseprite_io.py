"""The sole aseprite-package boundary, pinned to the evaluated Apache-2.0 version."""

import json
import struct
from copy import deepcopy
from pathlib import Path
from typing import get_args
from uuid import UUID

import aseprite as ap
import numpy as np

from cybersprite.core.canonical import dumps_project
from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.models import (
    BlendMode,
    Canvas,
    Frame,
    Grid,
    GroupLayer,
    ImageCel,
    ImageLayer,
    LinkCel,
    Palette,
    Project,
    Size,
    Slice,
    SliceKey,
    Tag,
    Tile,
    TileCel,
    TilemapLayer,
    Tileset,
    UserData,
)
from cybersprite.core.normalize import normalize_cels
from cybersprite.core.pixels import (
    TileRef,
    pixels_from_rows,
    pixels_to_rows,
    rgba,
    tiles_from_rows,
    tiles_to_rows,
)
from cybersprite.core.references import cel_owner, walk_layers
from cybersprite.core.validation import require_valid

from .common import fail

PACKAGE_VERSION = "0.1.0"
META_KEY = "$cybersprite"
BLENDS = get_args(BlendMode)
DIRECTIONS = ("forward", "reverse", "pingpong", "pingpong_reverse")
TYPED = {name.lower(): member for name, member in ap.PropertyType.__members__.items()}
WRAPPED = {
    name: TYPED[name]
    for name in (
        "int8",
        "uint8",
        "int16",
        "uint16",
        "int32",
        "uint32",
        "int64",
        "uint64",
        "fixed",
        "float",
        "double",
        "point",
        "size",
        "rect",
        "uuid",
    )
}


def _shape(value):
    if isinstance(value, dict):
        if "$type" in value and "value" in value:
            result = {
                "typed": value["$type"],
                "object": isinstance(value["value"], dict),
                "integer": type(value["value"]) is int,
            }
            if value["$type"] in ("float", "double"):
                result["scalar"] = value["value"]
            return result
        return {"map": {key: _shape(value[key]) for key in sorted(value)}}
    if isinstance(value, list):
        return {"list": [_shape(v) for v in value]}
    return "null" if value is None else "plain"


def _property(name, value):
    if isinstance(value, dict) and "$type" in value and "value" in value:
        kind = WRAPPED.get(value["$type"])
        if kind is None:
            raise invalid("Unknown typed user-data property.", type=value["$type"])
        raw = value["value"]
        if kind in (ap.PropertyType.POINT, ap.PropertyType.SIZE, ap.PropertyType.RECT):
            if isinstance(raw, dict):
                keys = {
                    ap.PropertyType.POINT: ("x", "y"),
                    ap.PropertyType.SIZE: ("w", "h"),
                    ap.PropertyType.RECT: ("x", "y", "w", "h"),
                }[kind]
                raw = tuple(raw[key] for key in keys)
            else:
                raw = tuple(raw)
        elif kind == ap.PropertyType.UUID:
            raw = UUID(raw)
    elif value is None:
        kind, raw = ap.PropertyType.STRING, ""
    elif type(value) is bool:
        kind, raw = ap.PropertyType.BOOL, value
    elif type(value) is int:
        kind = ap.PropertyType.INT32 if -(1 << 31) <= value < 1 << 31 else ap.PropertyType.INT64
        raw = value
    elif isinstance(value, str):
        kind, raw = ap.PropertyType.STRING, value
    elif isinstance(value, list):
        properties = [_property("", entry) for entry in value]
        kind, raw = ap.PropertyType.VECTOR, (0, [(p.kind, p.value) for p in properties])
    elif isinstance(value, dict):
        kind, raw = ap.PropertyType.PROPERTIES, [_property(k, value[k]) for k in sorted(value)]
    else:
        # Float metadata is copied as data; geometry and compositing never use it.
        kind, raw = ap.PropertyType.DOUBLE, value
    return ap.UserProperty(name, kind, raw)


def _value(prop, shape=None):
    kind, raw = prop.kind, prop.value
    if shape == "null" and kind == ap.PropertyType.STRING and raw == "":
        return None
    if kind == ap.PropertyType.PROPERTIES:
        shapes = shape.get("map", {}) if isinstance(shape, dict) else {}
        return {p.name: _value(p, shapes.get(p.name)) for p in sorted(raw, key=lambda p: p.name)}
    if kind == ap.PropertyType.VECTOR:
        element, items = raw
        shapes = shape.get("list", []) if isinstance(shape, dict) else []
        return [
            _value(
                ap.UserProperty("", ap.PropertyType(k), v), shapes[i] if i < len(shapes) else None
            )
            for i, (k, v) in enumerate(items if element == 0 else [(element, v) for v in items])
        ]
    if kind == ap.PropertyType.UUID:
        raw = str(raw)
    elif kind in (ap.PropertyType.POINT, ap.PropertyType.SIZE, ap.PropertyType.RECT):
        keys = {
            ap.PropertyType.POINT: ("x", "y"),
            ap.PropertyType.SIZE: ("w", "h"),
            ap.PropertyType.RECT: ("x", "y", "w", "h"),
        }[kind]
        raw = (
            dict(zip(keys, raw, strict=True))
            if isinstance(shape, dict) and shape.get("object")
            else list(raw)
        )
    explicit = isinstance(shape, dict) and "typed" in shape
    if explicit and "scalar" in shape:
        format = "<f" if kind == ap.PropertyType.FLOAT else "<d"
        if struct.pack(format, raw) == struct.pack(format, shape["scalar"]):
            raw = shape["scalar"]
    if explicit or (
        shape is None and kind.name.lower() in WRAPPED and kind != ap.PropertyType.INT32
    ):
        return {"$type": kind.name.lower(), "value": raw}
    return raw


def _to_ud(data, label, metadata):
    if data is None or not data.text and data.color is None and not data.properties:
        return None
    metadata["shapes"][label] = _shape(data.properties)
    props = [
        _property(k, data.properties[k])
        for k in sorted(data.properties)
        if k != "$ext" or not data.properties[k]
    ]
    mappings = [ap.PropertiesMap(0, props)] if props else []
    for extension in sorted(data.properties.get("$ext", {})):
        values = data.properties["$ext"][extension]
        mappings.append(
            ap.PropertiesMap(
                metadata["extension_ids"][extension],
                [_property(k, values[k]) for k in sorted(values)],
            )
        )
    return ap.UserData(
        text=data.text or None,
        color=ap.Color(*rgba(data.color)) if data.color else None,
        properties=mappings,
    )


def _from_ud(data, label, metadata):
    if not data:
        return None
    shape = metadata.get("shapes", {}).get(label, {})
    shapes = shape.get("map", {}) if isinstance(shape, dict) else {}
    properties = {}
    for mapping in sorted(data.properties, key=lambda m: m.key):
        extension = metadata.get("_extension_names", {}).get(mapping.key, str(mapping.key))
        extension_shapes = shapes.get("$ext", {}).get("map", {}).get(extension, {}).get("map", {})
        values = {
            p.name: _value(p, (shapes if mapping.key == 0 else extension_shapes).get(p.name))
            for p in sorted(mapping.properties, key=lambda p: p.name)
        }
        if mapping.key == 0:
            properties.update(values)
        else:
            properties.setdefault("$ext", {})[extension] = values
    if not data.text and data.color is None and not properties:
        return None
    return UserData(
        text=data.text or "",
        color="#" + bytes(data.color).hex() if data.color else None,
        properties=properties,
    )


def to_native(p):
    if ap.__version__ != PACKAGE_VERSION:
        fail(
            "E_UNSUPPORTED",
            "Unexpected aseprite package version; install the pinned version.",
            expected=PACKAGE_VERSION,
        )
    user_data = [p.user_data]
    for layer, _ in walk_layers(p.layers):
        user_data.append(layer.user_data)
        if not isinstance(layer, GroupLayer):
            user_data.extend(c.user_data for c in layer.cels if not isinstance(c, LinkCel))
    for ts in p.tilesets:
        user_data.extend([ts.user_data, *(t.user_data for t in ts.tiles)])
    user_data.extend(item.user_data for item in [*p.tags, *p.slices])
    extensions = sorted(
        {key for data in user_data if data for key in data.properties.get("$ext", {})}
    )
    metadata = dict(
        version=1,
        name=p.name,
        **({"platform": p.platform.model_dump(by_alias=True)} if p.platform else {}),
        frozen=p.palette.frozen,
        **({"ramps": [r.model_dump() for r in p.palette.ramps]} if p.palette.ramps else {}),
        shapes={},
        extension_ids={name: n + 1 for n, name in enumerate(extensions)},
        tag_user_colors=[t.user_data.color if t.user_data else None for t in p.tags],
        slice_user_colors=[s.user_data.color if s.user_data else None for s in p.slices],
        slice_optional=[
            [
                dict(frame=k.frame, center=k.center is not None, pivot=k.pivot is not None)
                for k in s.keys
            ]
            for s in p.slices
        ],
    )
    sprite = ap.Sprite(p.canvas.width, p.canvas.height, ap.ColorMode.INDEXED, empty=True)
    sprite.external_files = [
        ap.ExternalFile(n + 1, ap.ExternalFileType.EXTENSION_PROPS, name)
        for n, name in enumerate(extensions)
    ]
    sprite.palette = ap.Palette(
        [
            ap.Color(*rgba(c), name=p.palette.names.get(str(i)))
            for i, c in enumerate(p.palette.colors)
        ]
    )
    sprite.num_colors = len(p.palette.colors)
    sprite.transparent_index = p.palette.transparent_index
    sprite.pixel_width, sprite.pixel_height = p.canvas.pixel_ratio.w, p.canvas.pixel_ratio.h
    sprite.grid = ap.Grid(p.canvas.grid.x, p.canvas.grid.y, p.canvas.grid.w, p.canvas.grid.h)
    sprite.color_profile = ap.ColorProfile(
        ap.ColorProfileType.SRGB if p.canvas.color_profile == "srgb" else ap.ColorProfileType.NONE
    )
    sprite.frames = [ap.Frame(duration_ms=f.duration_ms) for f in p.frames]
    ts_indices = {ts.id: n for n, ts in enumerate(p.tilesets)}
    for index, ts in enumerate(p.tilesets):
        raw = b"".join(pixels_from_rows(t.pixels, ts.tile_w, ts.tile_h).tobytes() for t in ts.tiles)
        flags = (
            6
            | (8 if ts.match_flips.x else 0)
            | (16 if ts.match_flips.y else 0)
            | (32 if ts.match_flips.d else 0)
        )
        sprite.tilesets.append(
            ap.Tileset(
                id=index,
                name=ts.name,
                tile_count=len(ts.tiles),
                tile_width=ts.tile_w,
                tile_height=ts.tile_h,
                base_index=ts.base_index,
                flags=flags,
                pixels=ap.Pixels(ts.tile_w, ts.tile_h * len(ts.tiles), raw, ap.ColorMode.INDEXED),
                user_data=_to_ud(ts.user_data, f"tileset/{index}", metadata),
                tile_user_data=[
                    _to_ud(tile.user_data, f"tileset/{index}/tile/{j}", metadata)
                    for j, tile in enumerate(ts.tiles)
                ],
            )
        )
    for index, (layer, ancestors) in enumerate(walk_layers(p.layers)):
        ud = _to_ud(layer.user_data, f"layer/{index}", metadata)
        props = layer.user_data.properties if layer.user_data else {}
        native = ap.Layer(
            name=layer.name,
            kind=ap.LayerType({"image": 0, "group": 1, "tilemap": 2}[layer.type]),
            child_level=len(ancestors),
            blend_mode=ap.BlendMode(BLENDS.index(layer.blend_mode)),
            opacity=layer.opacity,
            visible=layer.visible,
            editable=not layer.locked,
            lock_movement=bool(props.get("$ase", {}).get("lock_movement", False)),
            user_data=ud,
        )
        if isinstance(layer, GroupLayer):
            native.collapsed = layer.collapsed
        else:
            native.prefer_linked_cels = layer.continuous
            if isinstance(layer, ImageLayer):
                native.background = layer.background
            else:
                native.tileset_index = ts_indices[layer.tileset]
        sprite.layers.append(native)
        if isinstance(layer, GroupLayer):
            continue
        for cel in sorted(layer.cels, key=lambda c: c.frame):
            owner = cel_owner(layer, cel)
            frame = sprite.frames[cel.frame]
            options = dict(x=owner.x, y=owner.y, opacity=owner.opacity, z_index=cel.z_index)
            if isinstance(cel, LinkCel):
                frame.set_linked_cel(index, cel.link, **options)
                continue
            if isinstance(layer, ImageLayer):
                raw = pixels_from_rows(cel.pixels, cel.w, cel.h).tobytes()
                native_cel = frame.set_cel(
                    index, ap.Pixels(cel.w, cel.h, raw, ap.ColorMode.INDEXED), **options
                )
            else:
                refs = [r for row in tiles_from_rows(cel.tiles, cel.w, cel.h) for r in row]
                raw = b"".join(
                    struct.pack(
                        "<I",
                        r.index
                        | (0x80000000 if r.x else 0)
                        | (0x40000000 if r.y else 0)
                        | (0x20000000 if r.d else 0),
                    )
                    for r in refs
                )
                tm = ap.Tilemap(
                    cel.w, cel.h, 32, 0x1FFFFFFF, 0x80000000, 0x40000000, 0x20000000, raw
                )
                native_cel = frame.set_tilemap_cel(index, tm, **options)
            native_cel.user_data = _to_ud(cel.user_data, f"layer/{index}/cel/{cel.frame}", metadata)
    for index, tag in enumerate(p.tags):
        ud = _to_ud(tag.user_data, f"tag/{index}", metadata) or ap.UserData()
        # The wire format's tag color is also emitted as user data for current readers.
        ud.color = ap.Color(*rgba(tag.color))
        sprite.tags.append(
            ap.Tag(
                tag.name,
                tag.from_,
                tag.to,
                ap.LoopDirection(DIRECTIONS.index(tag.direction)),
                tag.repeat,
                rgba(tag.color)[:3],
                ud,
            )
        )
    for index, s in enumerate(p.slices):
        ud = _to_ud(s.user_data, f"slice/{index}", metadata) or ap.UserData()
        ud.color = ap.Color(*rgba(s.color))
        sprite.slices.append(
            ap.Slice(
                s.name,
                [
                    ap.SliceKey(
                        k.frame,
                        k.x,
                        k.y,
                        k.w,
                        k.h,
                        ap.NinePatch(k.center.x, k.center.y, k.center.w, k.center.h)
                        if k.center
                        else None,
                        (k.pivot.x, k.pivot.y) if k.pivot else None,
                    )
                    for k in s.keys
                ],
                ud,
            )
        )
    sprite.user_data = _to_ud(p.user_data, "sprite", metadata) or ap.UserData()
    if p.user_data and META_KEY in p.user_data.properties:
        raise invalid("Sprite user_data uses the reserved $cybersprite property name.")
    root_map = next((m for m in sprite.user_data.properties if m.key == 0), None)
    if root_map is None:
        root_map = ap.PropertiesMap(0, [])
        sprite.user_data.properties.insert(0, root_map)
    encoded = json.dumps(
        metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    if len(encoded.encode("utf-8")) <= 65535:
        value = ap.UserProperty(META_KEY, ap.PropertyType.STRING, encoded)
    else:
        # A native STRING is limited to 65535 bytes; property vectors are not.
        value = ap.UserProperty(
            META_KEY,
            ap.PropertyType.VECTOR,
            (
                int(ap.PropertyType.STRING),
                [encoded[i : i + 8192] for i in range(0, len(encoded), 8192)],
            ),
        )
    root_map.properties.append(value)
    return sprite


def _color(c):
    return "#" + bytes(c).hex()


def from_native(sprite, *, name="Imported", quantize=None, source_limits=True):
    from .decode_limits import native_limits

    native_limits(sprite, source_limits=source_limits)
    dropped = []

    def drop(kind, **details):
        dropped.append(dict(element=kind, **details))

    metadata = {}
    native_ud = deepcopy(sprite.user_data)
    if native_ud:
        for mapping in native_ud.properties:
            if mapping.key == 0:
                for prop in list(mapping.properties):
                    if prop.name == META_KEY:
                        try:
                            encoded = prop.value
                            if prop.kind == ap.PropertyType.VECTOR:
                                element, parts = encoded
                                if element == int(ap.PropertyType.STRING):
                                    encoded = "".join(parts)
                            candidate = json.loads(encoded)
                            if candidate.get("version") == 1:
                                metadata = candidate
                                mapping.properties.remove(prop)
                        except (ValueError, TypeError, AttributeError):
                            pass
    width, height = sprite.width, sprite.height
    ratio = (sprite.pixel_width, sprite.pixel_height)
    if ratio not in ((1, 1), (2, 1), (1, 2)):
        drop("pixel_ratio", original=list(ratio))
        ratio = (1, 1)
    profile = sprite.color_profile
    color_profile = (
        "none" if profile is None or profile.kind == ap.ColorProfileType.NONE else "srgb"
    )
    if profile and profile.kind == ap.ColorProfileType.ICC:
        drop("embedded_icc")
    metadata["_extension_names"] = {
        file.id: file.name
        for file in sprite.external_files
        if file.kind == ap.ExternalFileType.EXTENSION_PROPS
    }
    for file in sprite.external_files:
        if file.kind != ap.ExternalFileType.EXTENSION_PROPS:
            drop("external_file", id=file.id, name=file.name)
    for mask in sprite.masks:
        drop("mask", name=mask.name)
    for chunk in sprite.unknown_chunks:
        drop("unknown_chunk", type=chunk.chunk_type, frame=chunk.frame_index)
    palette = [_color(c) for c in sprite.palette]
    names = {str(i): c.name for i, c in enumerate(sprite.palette) if c.name is not None}
    ti = sprite.transparent_index
    indexed = sprite.color_mode == ap.ColorMode.INDEXED
    changed = indexed and any(f.palette is not None for f in sprite.frames[1:])
    mappings = []
    if indexed and not changed and len(palette) <= 256:
        mappings = [list(range(len(palette))) for _ in sprite.frames]
    elif indexed and len(palette) <= 256:
        for frame in range(len(sprite.frames)):
            mapping = []
            for index, c in enumerate(sprite.palette_at(frame)):
                color = _color(c)
                if index == ti:
                    mapping.append(ti)
                elif any(c == color and i != ti for i, c in enumerate(palette)):
                    mapping.append(next(i for i, c in enumerate(palette) if c == color and i != ti))
                else:
                    mapping.append(len(palette))
                    if c.name is not None:
                        names[str(len(palette))] = c.name
                    palette.append(color)
            mappings.append(mapping)
        drop("frame_palettes", action="merged")
    else:
        palette, names, ti = ["#00000000"], {}, 0
    p = Project(
        name=metadata.get("name", name),
        platform=metadata.get("platform"),
        canvas=Canvas(
            width=width,
            height=height,
            grid=Grid(
                x=sprite.grid.x,
                y=sprite.grid.y,
                w=sprite.grid.width or 16,
                h=sprite.grid.height or 16,
            ),
            pixel_ratio=Size(w=ratio[0], h=ratio[1]),
            color_profile=color_profile,
        ),
        palette=Palette(colors=["#00000000"], transparent_index=0),
        frames=[Frame(duration_ms=f.duration_ms or 100) for f in sprite.frames],
        layers=[],
    )
    image_payloads = []
    background_targets = set()

    def convert(pixels, frame, background=False):
        channels = pixels.color_mode.bytes_per_pixel
        data = np.frombuffer(pixels.data, dtype=np.uint8).reshape(
            pixels.height, pixels.width, channels
        )
        if indexed and mappings:
            indices = data[..., 0]
            if int(indices.max(initial=0)) >= len(mappings[frame]):
                raise invalid("Aseprite pixel index exceeds its frame palette.", frame=frame)
            converted = np.asarray(mappings[frame], dtype=np.int32)[indices]
            # int32 remains temporary until the final palette budget is checked.
            return converted
        if indexed:
            table = np.array([tuple(c) for c in sprite.palette_at(frame)], dtype=np.uint8)
            data = table[data[..., 0]]
        elif channels == 2:
            data = np.concatenate((np.repeat(data[..., :1], 3, axis=2), data[..., 1:]), axis=2)
        else:
            data = data.copy()
        if not background:
            data[data[..., 3] == 0] = 0
        converted = np.empty(data.shape[:2], dtype=np.int32)
        lookup = {c: i for i, c in enumerate(palette)}
        for y, row in enumerate(data):
            for x, c in enumerate(row):
                color = "#" + bytes(c).hex()
                if color not in lookup:
                    lookup[color] = len(palette)
                    palette.append(color)
                converted[y, x] = lookup[color]
        return converted

    ts_ids, old_tilesets = {}, set()
    for index, native in enumerate(sprite.tilesets):
        if native.pixels is None:
            fail(
                "E_UNSUPPORTED",
                "External tileset has no embedded tile pixels.",
                tileset=native.name,
            )
        ts_id = p.id_counters.issue("tileset")
        ts_ids[native.id] = ts_id
        data = convert(native.pixels, 0)
        if (
            native.pixels.width != native.tile_width
            or native.pixels.height != native.tile_height * native.tile_count
        ):
            raise invalid("Tileset image dimensions do not match its tile dimensions/count.")
        old = not native.flags & 4
        if old:
            old_tilesets.add(native.id)
        tiles = [Tile(pixels=["00" * native.tile_width] * native.tile_height)] if old else []
        for j in range(native.tile_count):
            pixels = data[j * native.tile_height : (j + 1) * native.tile_height]
            # Large palettes are finalized below; rows are temporarily allowed wider indices.
            tile = Tile(
                pixels=["00" * native.tile_width] * native.tile_height,
                user_data=_from_ud(
                    native.tile_user_data[j] if j < len(native.tile_user_data) else None,
                    f"tileset/{index}/tile/{j}",
                    metadata,
                ),
            )
            tiles.append(tile)
            image_payloads.append((tile, pixels))
        p.tilesets.append(
            Tileset(
                id=ts_id,
                name=native.name,
                tile_w=native.tile_width,
                tile_h=native.tile_height,
                base_index=native.base_index,
                match_flips=dict(
                    x=bool(native.flags & 8), y=bool(native.flags & 16), d=bool(native.flags & 32)
                ),
                user_data=_from_ud(native.user_data, f"tileset/{index}", metadata),
                tiles=tiles,
            )
        )
    stack, layer_map = [], {}
    skipped_level = None
    for index, native in enumerate(sprite.layers):
        if skipped_level is not None and native.child_level > skipped_level:
            drop("reference_descendant", layer=native.name)
            continue
        skipped_level = None
        if native.reference:
            drop("reference_layer", layer=native.name)
            if native.kind == ap.LayerType.GROUP:
                skipped_level = native.child_level
            continue
        if native.uuid is not None:
            drop("layer_uuid", layer=native.name)
        ud = _from_ud(native.user_data, f"layer/{index}", metadata)
        if native.lock_movement or ud and "lock_movement" in ud.properties.get("$ase", {}):
            ud = ud or UserData()
            ud.properties.setdefault("$ase", {})["lock_movement"] = native.lock_movement
        blend = int(native.blend_mode)
        if blend >= len(BLENDS):
            drop("unknown_blend_mode", value=blend)
            blend = 0
        common = dict(
            id=p.id_counters.issue("layer"),
            name=native.name,
            visible=native.visible,
            locked=not native.editable,
            opacity=native.opacity if sprite.valid_layer_opacity else 255,
            blend_mode=BLENDS[blend],
            user_data=ud,
        )
        if native.kind == ap.LayerType.GROUP:
            layer = GroupLayer(**common, collapsed=native.collapsed)
        elif native.kind == ap.LayerType.TILEMAP:
            if native.tileset_index not in ts_ids:
                fail(
                    "E_UNSUPPORTED",
                    "Tilemap references a missing embedded tileset.",
                    layer=native.name,
                )
            layer = TilemapLayer(
                **common, continuous=native.prefer_linked_cels, tileset=ts_ids[native.tileset_index]
            )
        else:
            layer = ImageLayer(
                **common, continuous=native.prefer_linked_cels, background=native.background
            )
        while stack and stack[-1][0] >= native.child_level:
            stack.pop()
        if native.child_level:
            if not stack or stack[-1][0] != native.child_level - 1:
                raise invalid(
                    "Aseprite layer hierarchy contains an orphaned child.", layer=native.name
                )
            stack[-1][1].children.append(layer)
        else:
            p.layers.append(layer)
        if isinstance(layer, GroupLayer):
            stack.append((native.child_level, layer))
        layer_map[index] = layer

    def native_owner(index, frame):
        seen = set()
        cel = sprite.frames[frame].cel(index)
        while cel and cel.link is not None:
            if cel.link in seen or not 0 <= cel.link < len(sprite.frames):
                raise invalid("Aseprite contains a cyclic or invalid cel link.")
            seen.add(cel.link)
            cel = sprite.frames[cel.link].cel(index)
        if cel is None:
            raise invalid("Aseprite link targets a missing cel.")
        return cel

    links = []
    for frame, native_frame in enumerate(sprite.frames):
        for native in native_frame.cels:
            layer = layer_map.get(native.layer_index)
            if layer is None or isinstance(layer, GroupLayer):
                continue
            if native.extra is not None:
                drop("cel_extra", layer=layer.name, frame=frame)
            owner = native_owner(native.layer_index, frame)
            source_frame = frame if native.link is None else native.link
            same = (
                native.link is not None
                and not changed
                and (native.x, native.y, native.opacity, native.user_data)
                == (owner.x, owner.y, owner.opacity, None)
            )
            if same:
                links.append(
                    (layer, LinkCel(frame=frame, link=source_frame, z_index=native.z_index))
                )
                continue
            common = dict(
                frame=frame,
                x=native.x,
                y=native.y,
                opacity=native.opacity,
                z_index=native.z_index,
                user_data=_from_ud(
                    native.user_data or owner.user_data,
                    f"layer/{native.layer_index}/cel/{frame}",
                    metadata,
                ),
            )
            if owner.tilemap is not None:
                tm = owner.tilemap
                step = (tm.bits_per_tile + 7) // 8
                shift = (tm.tile_id_mask & -tm.tile_id_mask).bit_length() - 1
                refs = []
                for j in range(tm.width * tm.height):
                    value = int.from_bytes(tm.tiles[j * step : (j + 1) * step], "little")
                    tile = (value & tm.tile_id_mask) >> shift
                    if sprite.layers[native.layer_index].tileset_index in old_tilesets:
                        tile = 0 if tile == tm.tile_id_mask >> shift else tile + 1
                    refs.append(
                        TileRef(
                            tile,
                            bool(value & tm.x_flip_mask) if tile else False,
                            bool(value & tm.y_flip_mask) if tile else False,
                            bool(value & tm.d_flip_mask) if tile else False,
                        )
                    )
                layer.cels.append(
                    TileCel(
                        **common,
                        w=tm.width,
                        h=tm.height,
                        tiles=tiles_to_rows(
                            [refs[y * tm.width : (y + 1) * tm.width] for y in range(tm.height)]
                        ),
                    )
                )
            elif owner.pixels is not None and owner.pixels.width and owner.pixels.height:
                data = convert(owner.pixels, frame, getattr(layer, "background", False))
                cel = ImageCel(
                    **common,
                    w=owner.pixels.width,
                    h=owner.pixels.height,
                    pixels=["00" * owner.pixels.width] * owner.pixels.height,
                )
                layer.cels.append(cel)
                image_payloads.append((cel, data))
                if layer.background:
                    background_targets.add(id(cel))
            else:
                drop("empty_cel", layer=layer.name, frame=frame)
    for layer, link in links:
        layer.cels.append(link)
    # Reserve transparency even for an all-opaque raster; index zero must remain empty.
    if len(palette) > 256:
        if quantize is None:
            fail(
                "E_NEEDS_QUANTIZE",
                "Imported colors exceed the indexed palette budget.",
                colors=len(palette),
                limit=256,
            )
        from .input_adapter import quantize_arrays

        targets = [(obj, data) for obj, data in image_payloads if isinstance(obj, (ImageCel, Tile))]
        table = np.array([rgba(c) for c in palette], dtype=np.uint8)
        background_table = table.copy()
        background_table[..., 3] = 255
        table[ti] = 0
        images = [
            (background_table if id(obj) in background_targets else table)[data]
            for obj, data in targets
        ]
        outputs, colors = quantize_arrays(images, quantize)
        palette = ["#" + bytes(c).hex() for c in colors]
        ti, names = 0, {}
        for (obj, _), data in zip(targets, outputs, strict=True):
            obj.pixels = pixels_to_rows(data)
    else:
        for obj, data in image_payloads:
            if isinstance(obj, (ImageCel, Tile)):
                obj.pixels = pixels_to_rows(data.astype(np.uint8))
    if not palette or ti >= len(palette):
        raise invalid("Aseprite transparent index is outside its palette.")
    p.palette = Palette(
        ramps=metadata.get("ramps", []),
        colors=palette,
        names=names,
        transparent_index=ti,
        frozen=metadata.get("frozen", False),
    )
    if old_tilesets:
        for ts in p.tilesets:
            if ts.id in [ts_ids[i] for i in sorted(old_tilesets)]:
                ts.tiles[0].pixels = [f"{ti:02x}" * ts.tile_w] * ts.tile_h
    for index, native in enumerate(sprite.tags):
        ud = _from_ud(native.user_data, f"tag/{index}", metadata)
        if index < len(metadata.get("tag_user_colors", [])) and ud:
            ud.color = metadata["tag_user_colors"][index]
        color = (
            _color(native.user_data.color)[:7]
            if native.user_data and native.user_data.color
            else "#" + bytes(native.color).hex()
        )
        direction = int(native.direction)
        if direction >= len(DIRECTIONS):
            drop("unknown_tag_direction", value=direction)
            direction = 0
        p.tags.append(
            Tag(
                id=p.id_counters.issue("tag"),
                name=native.name,
                **{"from": native.from_frame},
                to=native.to_frame,
                direction=DIRECTIONS[direction],
                repeat=native.repeat,
                color=color,
                user_data=ud,
            )
        )
    for index, native in enumerate(sprite.slices):
        ud = _from_ud(native.user_data, f"slice/{index}", metadata)
        if index < len(metadata.get("slice_user_colors", [])) and ud:
            ud.color = metadata["slice_user_colors"][index]
        color = (
            _color(native.user_data.color)
            if native.user_data and native.user_data.color
            else "#19c3e6ff"
        )
        keys = [
            SliceKey(
                frame=k.frame,
                x=k.x,
                y=k.y,
                w=k.width,
                h=k.height,
                center=dict(
                    x=k.nine_patch.x, y=k.nine_patch.y, w=k.nine_patch.width, h=k.nine_patch.height
                )
                if k.nine_patch
                else None,
                pivot=dict(x=k.pivot[0], y=k.pivot[1]) if k.pivot else None,
            )
            for k in native.keys
        ]
        optional = metadata.get("slice_optional", [])
        if index < len(optional):
            flags_by_frame = {flags["frame"]: flags for flags in optional[index]}
            for key in keys:
                flags = flags_by_frame.get(key.frame, {})
                if (
                    flags.get("center") is False
                    and key.center
                    and not any(key.center.model_dump().values())
                ):
                    key.center = None
                if (
                    flags.get("pivot") is False
                    and key.pivot
                    and not any(key.pivot.model_dump().values())
                ):
                    key.pivot = None
        p.slices.append(
            Slice(
                id=p.id_counters.issue("slice"),
                name=native.name,
                color=color,
                user_data=ud,
                keys=keys,
            )
        )
    p.user_data = _from_ud(native_ud, "sprite", metadata)
    p = normalize_cels(p)
    return require_valid(p), dropped


def encode_aseprite(project):
    try:
        from .decode_limits import project_output_limits

        project_output_limits(project)
        return to_native(project).to_bytes()
    except (ValueError, TypeError, OverflowError, struct.error) as error:
        raise invalid(
            "Cannot encode .aseprite metadata or dimensions.", reason=str(error)
        ) from error


def decode_aseprite(data, *, name="Imported", quantize=None, source_limits=True):
    try:
        from .decode_limits import aseprite_limits

        aseprite_limits(data, source_limits=source_limits)
        return from_native(
            ap.Sprite.from_bytes(data), name=name, quantize=quantize, source_limits=source_limits
        )
    except (
        ap.AsepriteError,
        ValueError,
        TypeError,
        IndexError,
        KeyError,
        OverflowError,
        struct.error,
    ) as error:
        raise CyberSpriteError(
            "E_IO",
            f"Cannot decode .aseprite: {error}",
            "Check the source file and inspect unsupported metadata.",
        ) from error


def read_aseprite(path, options=None):
    path = Path(path)
    try:
        return decode_aseprite(
            path.read_bytes(), name=path.stem, quantize=(options or {}).get("quantize")
        )
    except OSError as error:
        raise CyberSpriteError(
            "E_IO", f"Cannot read .aseprite: {error}", "Check the source path and permissions."
        ) from error


def equivalent(first, second):
    """Compare the normative round-trip fields, renumbering IDs structurally."""

    def canonical(p):
        p = deepcopy(p)
        layer_ids = {layer.id: f"L{n + 1}" for n, (layer, _) in enumerate(walk_layers(p.layers))}
        ts_ids = {ts.id: f"TS{n + 1}" for n, ts in enumerate(p.tilesets)}
        for layer, _ in walk_layers(p.layers):
            layer.id = layer_ids[layer.id]
            if isinstance(layer, TilemapLayer):
                layer.tileset = ts_ids[layer.tileset]
        for n, ts in enumerate(p.tilesets):
            ts.id = f"TS{n + 1}"
        for n, tag in enumerate(p.tags):
            tag.id = f"T{n + 1}"
        for n, slice in enumerate(p.slices):
            slice.id = f"S{n + 1}"
        # dumps_project also removes empty user_data and lowercases palette entries.
        value = json.loads(dumps_project(p))
        for key in ("revision", "id_counters", "validation", "extensions"):
            value.pop(key)
        return value

    return canonical(first) == canonical(second)
