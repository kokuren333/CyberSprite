"""Header-only raster reservations before delegating to input codecs."""

import re
import struct
import zlib

from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.limits import (
    FRAME_COUNT,
    SOURCE_AREA,
    DecodeBudget,
    check_limit,
    source_dimensions,
)


def pillow_bomb_error(error):
    """Pillow may reject a huge header before returning its lazy image object."""
    match = re.search(r"\((\d+) pixels\)", str(error))
    requested = int(match[1]) if match else str(error)
    return CyberSpriteError(
        "E_LIMIT_EXCEEDED",
        "Source header exceeds the raster pixel budget.",
        "Resize the source to sides at most 8192 pixels and area at most 67108864 pixels.",
        {"limit_name": "source_area", "requested": requested, "limit": SOURCE_AREA},
    )


def native_limits(sprite):
    """Also protect callers converting an already-decoded adapter object."""
    source_dimensions(sprite.width, sprite.height)
    check_limit("source_frames", len(sprite.frames), FRAME_COUNT, "Import at most 4096 frames.")
    budget = DecodeBudget()
    for tileset in sprite.tilesets:
        if tileset.pixels is not None:
            budget.reserve_pixels(tileset.tile_width, tileset.tile_height, tileset.tile_count)
    for frame in sprite.frames:
        for cel in frame.cels:
            if cel.pixels is not None:
                budget.reserve_pixels(cel.pixels.width, cel.pixels.height)
            if cel.tilemap is not None:
                budget.reserve_pixels(cel.tilemap.width, cel.tilemap.height)


def aseprite_limits(data):
    """Scan container/chunk headers; never ask the adapter to inflate unchecked rasters."""
    if len(data) < 128 or struct.unpack_from("<H", data, 4)[0] != 0xA5E0:
        return  # The adapter reports malformed signatures.
    count, width, height, depth = struct.unpack_from("<HHHH", data, 6)
    source_dimensions(width, height)
    check_limit("source_frames", count, FRAME_COUNT, "Import at most 4096 frames.")
    budget = DecodeBudget()
    streams = []
    offset = 128
    for _ in range(count):
        size, magic, old_count = struct.unpack_from("<IHH", data, offset)
        if size < 16 or magic != 0xF1FA or offset + size > len(data):
            raise ValueError("Invalid frame header or size.")
        chunks = struct.unpack_from("<I", data, offset + 12)[0] or old_count
        cursor, end = offset + 16, offset + size
        for _ in range(chunks):
            length, kind = struct.unpack_from("<IH", data, cursor)
            if length < 6 or cursor + length > end:
                raise ValueError("Invalid chunk size.")
            body = memoryview(data)[cursor + 6 : cursor + length]
            if kind == 0x2005:  # Image or tilemap cel, including off-canvas cels.
                cel_type = struct.unpack_from("<H", body, 7)[0]
                if cel_type in (0, 2, 3):
                    w, h = struct.unpack_from("<HH", body, 16)
                    budget.reserve_pixels(w, h)
                    if cel_type == 2:
                        streams.append((body[20:], w * h * (depth // 8)))
                    elif cel_type == 3:
                        bits = struct.unpack_from("<H", body, 20)[0]
                        if bits != 32:
                            raise ValueError("Only 32-bit tile references are supported.")
                        streams.append((body[48:], w * h * 4))
            elif kind == 0x2023:  # Embedded tiles are one compressed vertical strip.
                _, flags, tiles, w, h = struct.unpack_from("<IIIHH", body)
                budget.reserve_pixels(w, h, tiles)
                name_len = struct.unpack_from("<H", body, 32)[0]
                start = 34 + name_len + (8 if flags & 1 else 0)
                if flags & 2:
                    compressed_size = struct.unpack_from("<I", body, start)[0]
                    streams.append(
                        (
                            body[start + 4 : start + 4 + compressed_size],
                            w * h * tiles * (depth // 8),
                        )
                    )
            cursor += length
        offset = end
    # Bound expansion even when an input stream lies about its dimensions. Validate
    # in 64 KiB pieces, so the adapter's subsequent full inflation is known bounded.
    for compressed, expected in streams:
        try:
            decoder = zlib.decompressobj()
            pending, total = compressed, 0
            while pending:
                raw = decoder.decompress(pending, min(65_536, expected - total + 1))
                total += len(raw)
                if total > expected:
                    raise ValueError("Compressed raster exceeds its declared dimensions.")
                pending = decoder.unconsumed_tail
            if total != expected or not decoder.eof or decoder.unused_data:
                raise ValueError("Compressed raster length does not match its dimensions.")
        except zlib.error as error:
            raise ValueError("Invalid compressed raster stream.") from error
