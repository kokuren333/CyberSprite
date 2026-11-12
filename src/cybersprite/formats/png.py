"""Minimal deterministic PNG codec for our 8-bit filter-0 indexed/RGBA files."""

import struct
import sys
import zlib
from dataclasses import dataclass

import numpy as np

from cybersprite import __version__
from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.pixels import rgba

SIGNATURE = b"\x89PNG\r\n\x1a\n"


def environment_fingerprint() -> str:
    return (
        f"cybersprite {__version__} / zlib {zlib.ZLIB_RUNTIME_VERSION} / "
        f"python {sys.version_info.major}.{sys.version_info.minor}"
    )


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def stored_zlib(raw: bytes) -> bytes:
    """RFC1950 header, byte-aligned stored DEFLATE blocks, big-endian Adler32."""
    result = bytearray(b"\x78\x01")
    for start in range(0, max(1, len(raw)), 65535):
        block = raw[start : start + 65535]
        final = start + 65535 >= len(raw)
        result.append(int(final))
        result.extend(struct.pack("<HH", len(block), len(block) ^ 65535))
        result.extend(block)
    result.extend(struct.pack(">I", zlib.adler32(raw)))
    return bytes(result)


def encode_png(
    pixels: np.ndarray, palette: list[str] | None = None, *, compression: str = "zlib"
) -> bytes:
    if (
        pixels.dtype != np.uint8
        or not (pixels.ndim == 2 or pixels.ndim == 3 and pixels.shape[2] == 4)
        or min(pixels.shape[:2]) < 1
    ):
        raise invalid("PNG output requires a nonempty uint8 indexed or RGBA array.")
    if compression not in ("stored", "zlib"):
        raise invalid("PNG compression must be stored or zlib.")
    height, width = pixels.shape[:2]
    indexed = pixels.ndim == 2
    result = SIGNATURE + _chunk(
        b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 3 if indexed else 6, 0, 0, 0)
    )
    if indexed:
        if palette is None or not 1 <= len(palette) <= 256 or int(pixels.max()) >= len(palette):
            raise invalid("Indexed PNG requires 1..256 colors covering every pixel index.")
        colors = [rgba(color) for color in palette]
        result += _chunk(b"PLTE", bytes(channel for color in colors for channel in color[:3]))
        last = max((i for i, color in enumerate(colors) if color[3] != 255), default=-1)
        if last >= 0:
            result += _chunk(b"tRNS", bytes(color[3] for color in colors[: last + 1]))
    raw = b"".join(b"\0" + row.tobytes(order="C") for row in pixels)
    compressed = stored_zlib(raw) if compression == "stored" else zlib.compress(raw, level=9)
    return result + _chunk(b"IDAT", compressed) + _chunk(b"IEND", b"")


@dataclass
class DecodedPNG:
    pixels: np.ndarray
    palette: list[str] | None

    def rgba(self) -> np.ndarray:
        if self.palette is None:
            return self.pixels.copy()
        return np.array([rgba(color) for color in self.palette], dtype=np.uint8)[self.pixels]


def decode_png(data: bytes) -> DecodedPNG:
    """Read only the subset written above; reject corruption and unsupported features."""

    def fail(message):
        return CyberSpriteError(
            "E_IO",
            f"Invalid CyberSprite PNG: {message}",
            "Re-export the image using the CyberSprite PNG writer.",
        )

    if not data.startswith(SIGNATURE):
        raise fail("signature is missing.")
    chunks = []
    offset = len(SIGNATURE)
    while offset < len(data):
        if offset + 12 > len(data):
            raise fail("truncated chunk header.")
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise fail("truncated chunk payload.")
        payload = data[offset + 8 : end - 4]
        crc = struct.unpack_from(">I", data, end - 4)[0]
        if zlib.crc32(kind + payload) != crc:
            raise fail("chunk CRC mismatch.")
        chunks.append((kind, payload))
        offset = end
    kinds = [kind for kind, _payload in chunks]
    if kinds not in (
        [b"IHDR", b"IDAT", b"IEND"],
        [b"IHDR", b"PLTE", b"IDAT", b"IEND"],
        [b"IHDR", b"PLTE", b"tRNS", b"IDAT", b"IEND"],
    ):
        raise fail("unexpected chunk order or unsupported chunks.")
    if len(chunks[0][1]) != 13 or chunks[-1][1]:
        raise fail("invalid IHDR or IEND size.")
    width, height, depth, color_type, comp, filt, interlace = struct.unpack(
        ">IIBBBBB", chunks[0][1]
    )
    if (
        depth != 8
        or color_type not in (3, 6)
        or comp
        or filt
        or interlace
        or not 1 <= width <= 1048576
        or not 1 <= height <= 1048576
        or width * height > 268435456
    ):
        raise fail("unsupported image dimensions or header.")
    values = dict(chunks)
    palette = None
    if color_type == 3:
        colors = values.get(b"PLTE", b"")
        alphas = values.get(b"tRNS", b"")
        if not colors or len(colors) % 3 or len(colors) > 768 or len(alphas) > len(colors) // 3:
            raise fail("invalid palette.")
        palette = [
            "#" + colors[i : i + 3].hex() + f"{alphas[i // 3] if i // 3 < len(alphas) else 255:02x}"
            for i in range(0, len(colors), 3)
        ]
    elif b"PLTE" in values:
        raise fail("RGBA file unexpectedly contains a palette.")
    stride = width * (1 if color_type == 3 else 4)
    expected = (stride + 1) * height
    try:
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(values[b"IDAT"], expected + 1)
        if (
            len(raw) != expected
            or not decompressor.eof
            or decompressor.unused_data
            or decompressor.unconsumed_tail
        ):
            raise fail("invalid compressed stream length.")
    except zlib.error as error:
        raise fail(f"decompression failed: {error}") from error
    rows = np.frombuffer(raw, dtype=np.uint8).reshape(height, stride + 1)
    if np.any(rows[:, 0] != 0):
        raise fail("only filter 0 is supported.")
    pixels = rows[:, 1:].copy()
    if color_type == 6:
        pixels = pixels.reshape(height, width, 4)
    elif palette is not None and int(pixels.max()) >= len(palette):
        raise fail("pixel index exceeds palette size.")
    return DecodedPNG(pixels, palette)
