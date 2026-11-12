import hashlib
import struct
import zlib

import numpy as np
import pytest

from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.hashing import pixel_sha256
from cybersprite.formats.png import (
    SIGNATURE,
    decode_png,
    encode_png,
    environment_fingerprint,
    stored_zlib,
)


@pytest.mark.parametrize("compression", ["stored", "zlib"])
@pytest.mark.parametrize("indexed", [False, True])
def test_png_roundtrip_and_chunks(compression, indexed):
    pixels = (
        np.array([[0, 1, 2], [2, 1, 0]], dtype=np.uint8)
        if indexed
        else np.array(
            [[[1, 2, 3, 4], [5, 6, 7, 255]], [[100, 200, 255, 0], [99, 88, 77, 128]]],
            dtype=np.uint8,
        )
    )
    palette = ["#00000000", "#ff000080", "#ffffffff", "#00ff00ff"] if indexed else None
    data = encode_png(pixels, palette, compression=compression)
    assert data == encode_png(pixels, palette, compression=compression)
    output = decode_png(data)
    np.testing.assert_array_equal(output.pixels, pixels)
    assert output.palette == palette
    offset = len(SIGNATURE)
    kinds, payloads = [], {}
    while offset < len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4 : offset + 8]
        kinds.append(kind)
        payloads[kind] = data[offset + 8 : offset + 8 + size]
        offset += 12 + size
    assert kinds == (
        [b"IHDR", b"PLTE", b"tRNS", b"IDAT", b"IEND"] if indexed else [b"IHDR", b"IDAT", b"IEND"]
    )
    if indexed:
        assert payloads[b"tRNS"] == b"\0\x80"
        assert len(payloads[b"PLTE"]) == 12


@pytest.mark.parametrize("size", [0, 1, 65534, 65535, 65536, 131070, 131071])
def test_stored_deflate_boundaries(size):
    data = bytes(i % 256 for i in range(size))
    packed = stored_zlib(data)
    assert zlib.decompress(packed) == data
    assert packed[:2] == b"\x78\x01"
    assert packed[-4:] == struct.pack(">I", zlib.adler32(data))
    pos, total = 2, 0
    while True:
        final = packed[pos]
        length, complement = struct.unpack_from("<HH", packed, pos + 1)
        assert final in (0, 1) and complement == length ^ 65535
        total += length
        pos += 5 + length
        if final:
            break
    assert total == size and pos == len(packed) - 4


def test_no_trns_for_all_opaque():
    data = encode_png(np.zeros((1, 1), dtype=np.uint8), ["#000000ff"])
    assert b"tRNS" not in data


def test_corrupt_png_rejected():
    data = encode_png(np.zeros((2, 2, 4), dtype=np.uint8))
    corrupted = bytearray(data)
    corrupted[40] ^= 1
    for broken in (b"no PNG", data[:-1], data + b"garbage", bytes(corrupted)):
        with pytest.raises(CyberSpriteError):
            decode_png(broken)


def test_hash_header_is_specified_bytes():
    pixels = np.array([[0, 1, 2]], dtype=np.uint8)
    assert (
        pixel_sha256(pixels) == hashlib.sha256(b"CSPX1\x03\0\0\0\x01\0\0\0\0\0\x01\x02").hexdigest()
    )
    rgba = np.zeros((1, 3, 4), dtype=np.uint8)
    assert (
        pixel_sha256(rgba)
        == hashlib.sha256(b"CSPX1" + struct.pack("<IIB", 3, 1, 1) + bytes(12)).hexdigest()
    )
    assert " / zlib " in environment_fingerprint() and " / python 3." in environment_fingerprint()
