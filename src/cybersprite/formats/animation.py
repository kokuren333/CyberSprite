"""Original GIF89a LZW writer and full-frame APNG writer/decoder."""

import io
import struct
import zlib

import numpy as np

from cybersprite.core.errors import invalid
from cybersprite.core.pixels import rgba

from .png import SIGNATURE, _chunk, decode_png, encode_png, stored_zlib


def lzw_encode(data: bytes, minimum: int) -> bytes:
    """GIF least-significant-bit-first LZW; reset at the 4096-code limit."""
    clear, stop = 1 << minimum, (1 << minimum) + 1
    table = {bytes([i]): i for i in range(clear)}
    width, next_code = minimum + 1, stop + 1
    result = bytearray()
    accumulator = bits = 0

    def emit(code):
        nonlocal accumulator, bits
        accumulator |= code << bits
        bits += width
        while bits >= 8:
            result.append(accumulator & 255)
            accumulator >>= 8
            bits -= 8

    emit(clear)
    word = b""
    for value in data:
        symbol = bytes([value])
        candidate = word + symbol
        if candidate in table:
            word = candidate
            continue
        emit(table[word])
        if next_code < 4096:
            table[candidate] = next_code
            next_code += 1
            # The decoder creates this entry after consuming the following code.
            if next_code > 1 << width and width < 12:
                width += 1
        else:
            emit(clear)
            table = {bytes([i]): i for i in range(clear)}
            width, next_code = minimum + 1, stop + 1
        word = symbol
    if word:
        emit(table[word])
        if next_code == 1 << width and width < 12:
            width += 1
    emit(stop)
    if bits:
        result.append(accumulator & 255)
    return bytes(result)


def gif_durations(durations):
    return [max(2, (duration + 5) // 10) * 10 for duration in durations]


def encode_gif(frames, palette, transparent_index, durations, *, loop=0, transparent=None):
    if not frames or len(frames) != len(durations):
        raise invalid("GIF requires one duration per frame.")
    height, width = frames[0].shape
    if max(width, height) > 65535:
        raise invalid("GIF dimensions must fit unsigned 16-bit fields.")
    table_size = 1 << max(1, (len(palette) - 1).bit_length())
    table_bits = table_size.bit_length() - 1
    colors = bytes(v for color in palette for v in rgba(color)[:3])
    colors += b"\0" * (3 * (table_size - len(palette)))
    result = bytearray(
        b"GIF89a"
        + struct.pack("<HHBBB", width, height, 0xF0 | (table_bits - 1), transparent_index, 0)
    )
    result.extend(colors)
    # loop is total plays: 1 has no extension; positive n stores n-1 repeats.
    if loop != 1:
        result.extend(b"!\xff\x0bNETSCAPE2.0\x03\x01" + struct.pack("<H", max(0, loop - 1)) + b"\0")
    if transparent is None:
        transparent = [bool(np.any(frame == transparent_index)) for frame in frames]
    disposal = 2 if any(transparent) else 1
    minimum = max(2, table_bits)
    for frame, duration, has_transparency in zip(
        frames, gif_durations(durations), transparent, strict=True
    ):
        if frame.dtype != np.uint8 or frame.shape != (height, width):
            raise invalid("GIF frames must be identically sized uint8 index arrays.")
        result.extend(
            b"!\xf9\x04"
            + struct.pack(
                "<BHB", (disposal << 2) | int(has_transparency), duration // 10, transparent_index
            )
            + b"\0"
        )
        result.extend(b"," + struct.pack("<HHHHB", 0, 0, width, height, 0))
        encoded = lzw_encode(frame.tobytes(), minimum)
        result.append(minimum)
        for start in range(0, len(encoded), 255):
            block = encoded[start : start + 255]
            result.append(len(block))
            result.extend(block)
        result.append(0)
    result.append(0x3B)
    return bytes(result)


def decode_gif(data):
    """Independent reader used only for verification; Pillow never writes exports."""
    from PIL import Image

    frames, durations = [], []
    with Image.open(io.BytesIO(data)) as image:
        repeats = image.info.get("loop")
        plays = 1 if repeats is None else 0 if repeats == 0 else repeats + 1
        for index in range(image.n_frames):
            image.seek(index)
            frames.append(np.array(image.convert("RGBA"), dtype=np.uint8))
            durations.append(image.info.get("duration", 0))
    return frames, durations, plays


def encode_apng(frames, durations, palette=None, *, loop=0, compression="zlib"):
    if not frames or len(frames) != len(durations):
        raise invalid("APNG requires one duration per frame.")
    first = encode_png(frames[0], palette, compression=compression)
    chunks = list(_chunks(first))
    header = b"".join(_chunk(k, v) for k, v in chunks if k in (b"IHDR", b"PLTE", b"tRNS"))
    result = SIGNATURE + header + _chunk(b"acTL", struct.pack(">II", len(frames), loop))
    sequence = 0
    height, width = frames[0].shape[:2]
    for index, (frame, duration) in enumerate(zip(frames, durations, strict=True)):
        if frame.shape != frames[0].shape or frame.dtype != np.uint8 or not 1 <= duration <= 65535:
            raise invalid("APNG frames must share dimensions/mode and have 1..65535 ms durations.")
        result += _chunk(
            b"fcTL", struct.pack(">IIIIIHHBB", sequence, width, height, 0, 0, duration, 1000, 0, 0)
        )
        sequence += 1
        raw = b"".join(b"\0" + row.tobytes() for row in frame)
        compressed = stored_zlib(raw) if compression == "stored" else zlib.compress(raw, level=9)
        if index == 0:
            result += _chunk(b"IDAT", compressed)
        else:
            result += _chunk(b"fdAT", struct.pack(">I", sequence) + compressed)
            sequence += 1
    return result + _chunk(b"IEND", b"")


def _chunks(data):
    if not data.startswith(SIGNATURE):
        raise ValueError("Invalid PNG signature.")
    offset = len(SIGNATURE)
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("Truncated PNG chunk.")
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4 : offset + 8]
        end = offset + length + 12
        if end > len(data):
            raise ValueError("Truncated PNG payload.")
        payload = data[offset + 8 : end - 4]
        if zlib.crc32(kind + payload) != struct.unpack_from(">I", data, end - 4)[0]:
            raise ValueError("PNG chunk CRC mismatch.")
        yield kind, payload
        offset = end


def decode_apng(data):
    """Decode our full-frame subset, checking controls as well as all PNG pixels."""
    header, frames, durations = [], [], []
    control = None
    sequence = 0
    count = plays = None
    ended = False
    for kind, payload in _chunks(data):
        if ended:
            raise ValueError("APNG data follows IEND.")
        if kind in (b"IHDR", b"PLTE", b"tRNS"):
            if count is not None:
                raise ValueError("APNG header follows animation control.")
            header.append((kind, payload))
        elif kind == b"acTL":
            if count is not None:
                raise ValueError("Duplicate APNG animation control.")
            count, plays = struct.unpack(">II", payload)
        elif kind == b"fcTL":
            if control is not None:
                raise ValueError("Missing APNG frame data.")
            seq, w, h, x, y, numerator, denominator, disposal, blend = struct.unpack(
                ">IIIIIHHBB", payload
            )
            iw, ih = struct.unpack_from(">II", header[0][1])
            if (
                seq != sequence
                or (w, h) != (iw, ih)
                or x
                or y
                or disposal
                or blend
                or denominator != 1000
            ):
                raise ValueError("Unsupported APNG frame control.")
            sequence += 1
            control = numerator
        elif kind in (b"IDAT", b"fdAT"):
            if control is None or count is None or (kind == b"IDAT") != (not frames):
                raise ValueError("Unexpected APNG frame data.")
            if kind == b"fdAT":
                seq = struct.unpack_from(">I", payload)[0]
                if seq != sequence:
                    raise ValueError("APNG sequence mismatch.")
                sequence += 1
                payload = payload[4:]
            png = SIGNATURE + b"".join(_chunk(k, v) for k, v in header)
            frames.append(decode_png(png + _chunk(b"IDAT", payload) + _chunk(b"IEND", b"")))
            durations.append(control)
            control = None
        elif kind == b"IEND":
            if payload or control is not None:
                raise ValueError("Invalid APNG end.")
            ended = True
        else:
            raise ValueError("Unexpected APNG chunk.")
    if not ended or count != len(frames) or not frames:
        raise ValueError("APNG frame count/end mismatch.")
    return frames, durations, plays
