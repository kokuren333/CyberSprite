"""Original GB bitplanes and independent decoder, with strict indexed mapping."""

import numpy as np
from pydantic import Field

from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.models import ImageCel, ImageLayer, Model
from cybersprite.core.palette_units import resources, violations
from cybersprite.core.pixels import pixels_from_rows, rgba
from cybersprite.core.quality_platform import evaluate
from cybersprite.core.references import resolve_layer

from .export_args import ExportBase, PluginExportArgs


class NativeOptions(Model):
    tileset: str | None = Field(None, description="Tileset ID or unique name; includes tile zero.")
    layer: str | None = Field(None, description="Non-group layer ID or unique name; all frames.")


class NativeArgs(ExportBase):
    out: str = Field(
        description="Raw tile output path.", json_schema_extra={"x-cybersprite-path": "output"}
    )
    format: str = Field("gb-2bpp", description="Native exporter name; initially gb-2bpp.")
    tileset: str | None = Field(None, description="Tileset ID or unique name.")
    layer: str | None = Field(None, description="Non-group layer ID or unique name.")
    palette_out: str | None = Field(
        None,
        description="Reserved; not yet supported.",
        json_schema_extra={"x-cybersprite-path": "output"},
    )
    map_out: str | None = Field(
        None,
        description="Reserved; not yet supported.",
        json_schema_extra={"x-cybersprite-path": "output"},
    )


def encode_gb(tiles):
    output = bytearray()
    for tile in tiles:
        if tile.shape != (8, 8) or tile.dtype != np.uint8 or np.any(tile > 3):
            raise invalid("GB encoding requires uint8 8x8 local values in 0..3.")
        for row in tile:
            low, high = 0, 0
            for value in row:
                low = (low << 1) | (int(value) & 1)
                high = (high << 1) | (int(value) >> 1)
            output.extend((low, high))
    return bytes(output)


def decode_gb(raw):
    """Decode from offsets and bit masks; shares no encoder packing logic."""
    if len(raw) % 16:
        raise invalid("GB tile data length must be a multiple of 16 bytes.")
    result = []
    for offset in range(0, len(raw), 16):
        tile = np.zeros((8, 8), dtype=np.uint8)
        for y in range(8):
            for x in range(8):
                mask = 128 >> x
                tile[y, x] = bool(raw[offset + 2 * y] & mask) + 2 * bool(
                    raw[offset + 2 * y + 1] & mask
                )
        result.append(tile)
    return result


def _refuse(message, **details):
    raise CyberSpriteError(
        "E_VALIDATION_FAILED",
        message,
        "Remap the selected indices or correct the platform; lossy mapping is refused.",
        details,
    )


class GBExporter:
    plugin_api = 1
    native = True
    name = "gb-2bpp"
    extension = "2bpp"
    options_model = NativeOptions

    def verification_frames(self, p, render, options):
        if (options.tileset is None) == (options.layer is None):
            raise invalid("Select exactly one of tileset or layer for native export.")
        if p.platform is None or p.platform.system.palette is None:
            raise invalid("Native GB export requires a platform with system.palette row mapping.")
        spec = p.platform.system.palette
        if spec.row_size != 4:
            raise invalid("gb-2bpp requires platform palette.row_size=4.")
        # Native structural constraints cannot be disabled through quality severity.
        strict = p.model_copy(deep=True)
        strict.validation.severity.update({key: "error" for key in ("Q-PLT-02", "Q-PLT-03")})
        issues, _ = evaluate(strict, [0] * len(p.frames))
        structural = [i for i in issues if i["rule"] in ("Q-PLT-02", "Q-PLT-03")]
        if structural:
            _refuse(
                "Native export requires representable colors and binary alpha.", issues=structural
            )
        if any(rgba(c)[3] not in (0, 255) for c in p.palette.colors):
            _refuse("Native export cannot encode partial alpha.")
        palette = np.array([rgba(c) for c in p.palette.colors], dtype=np.uint8)
        palette[p.palette.transparent_index] = (0, 0, 0, 0)
        sources = []
        if options.tileset is not None:
            matches = [
                t for t in p.tilesets if t.id == options.tileset or t.name == options.tileset
            ]
            if len(matches) != 1:
                raise invalid("Select one existing tileset ID; names must be unique.")
            ts = matches[0]
            if (ts.tile_w, ts.tile_h) != (8, 8):
                raise invalid("gb-2bpp requires 8x8 tiles; resize the tileset explicitly.")
            bad = [v for v in violations(p) if v.get("tileset") == ts.id]
            temp = p.model_copy(deep=True)
            temp.canvas.width = temp.canvas.height = 8
            for tile in ts.tiles:
                data = pixels_from_rows(tile.pixels, 8, 8)
                temp.layers = [
                    ImageLayer(
                        id="L1",
                        name="Native verification",
                        cels=[ImageCel(frame=0, x=0, y=0, w=8, h=8, pixels=tile.pixels)],
                    )
                ]
                sources.append((data, render(temp, 0)))
        else:
            layer = resolve_layer(p, options.layer)
            if layer.type == "group":
                raise invalid("Select an image or tilemap layer for native export.")
            w, h = p.canvas.width, p.canvas.height
            if w % 8 or h % 8:
                raise invalid("Native layer canvas dimensions must be multiples of 8.")
            if w // 8 * (h // 8) * len(p.frames) > 65536:
                raise invalid("Native export accepts at most 65536 tiles; split the frame range.")
            bad = [v for v in violations(p) if v.get("layer") == layer.id]
            # Resource arrays retain duplicate RGB entries and their explicit bank indices.
            for frame in range(len(p.frames)):
                data = np.full((h, w), p.palette.transparent_index, dtype=np.uint8)
                for part, ox, oy, _ in resources(
                    p, selected_layer=layer.id, selected_frame=frame, include_tilesets=False
                ):
                    ph, pw = part.shape
                    x0, y0, x1, y1 = max(0, ox), max(0, oy), min(w, ox + pw), min(h, oy + ph)
                    if x1 > x0 and y1 > y0:
                        data[y0:y1, x0:x1] = part[y0 - oy : y1 - oy, x0 - ox : x1 - ox]
                rendered = render(p, frame, {"layers": [layer.id]})
                for y in range(0, h, 8):
                    for x in range(0, w, 8):
                        sources.append((data[y : y + 8, x : x + 8], rendered[y : y + 8, x : x + 8]))
        if bad:
            _refuse("Selected resource violates palette row closure.", findings=bad)
        if len(sources) > 65536:
            raise invalid("Native export accepts at most 65536 tiles; split the resource.")
        self.tiles, self.tables, expected = [], [], []
        offset = 1 if spec.slot0 == "color" else 0
        ti = p.palette.transparent_index
        for data, reference in sources:
            indices = [int(v) for v in np.unique(data)]
            opaque = [i for i in indices if i != ti]
            if any(rgba(p.palette.colors[i])[3] != 255 for i in opaque):
                _refuse("Non-transparent native slots require alpha 255.", indices=opaque)
            rows = {(i - offset) // 4 for i in opaque}
            if (
                len(rows) > 1
                or any(not 0 <= r < spec.rows for r in rows)
                or spec.slot0 == "color"
                and ti in indices
                or spec.slot0 != "color"
                and any(i % 4 == 0 for i in opaque)
            ):
                _refuse("Tile cannot be represented by one GB palette row.", indices=indices)
            bank = min(rows) if rows else 0
            table = np.zeros((4, 4), dtype=np.uint8)
            for slot in range(4):
                index = bank * 4 + slot + offset
                if index < len(palette):
                    table[slot] = palette[index]
            if spec.slot0 != "color":
                table[0] = (0, 0, 0, 0)
            local = ((data.astype(np.int32) - offset) % 4).astype(np.uint8)
            if spec.slot0 != "color":
                local[data == ti] = 0
            if not np.array_equal(table[local], reference):
                _refuse(
                    "Local palette mapping differs from the renderer; correct alpha or opacity."
                )
            self.tiles.append(local)
            self.tables.append(table)
            expected.append(reference)
        return expected

    def write(self, document, render, out, options):
        out.write_bytes(encode_gb(self.tiles))
        return dict(
            files=[], fingerprint="gb-2bpp-v1", warnings=[], validation_ok=True, verified=False
        )

    def decode(self, raw):
        values = decode_gb(raw)
        if len(values) != len(self.tables):
            raise ValueError("GB tile count differs from the prepared resource.")
        return [table[tile] for table, tile in zip(self.tables, values, strict=True)]


def export_native(p, args, root=None):
    from .plugin_export import export_plugin, resolve_exporter

    if args.palette_out is not None or args.map_out is not None:
        raise CyberSpriteError(
            "E_UNSUPPORTED",
            "Native palette_out/map_out are not implemented.",
            "Omit sidecar paths; this version exports raw tile bytes only.",
        )
    exporter = resolve_exporter(args.format)
    if not getattr(exporter, "native", False):
        raise invalid("export_native requires an exporter declaring native=true.")
    # Plugin options are validated by the selected exporter, including external native formats.
    return export_plugin(
        p,
        PluginExportArgs(
            out=args.out,
            overwrite=args.overwrite,
            allow_invalid=args.allow_invalid,
            format=args.format,
            options=dict(tileset=args.tileset, layer=args.layer),
        ),
        root,
    )
