import hashlib
import json
import random
from pathlib import Path

import numpy as np
import pytest

from cybersprite.pipeline import oklab

ROOT = Path(__file__).resolve().parents[2]


def test_pinned_vectors_and_every_grey():
    raw = (ROOT / "tests/vectors/color/oklab_fixed_v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "3d9223a18fd170a223118b015e6cf2d58be0c284cc2adad2306d86c6bca84a26"
    vectors = json.loads(raw)["vectors"]
    assert len(vectors) == 1262
    assert [v["rgb"] for v in vectors[:256]] == [[n] * 3 for n in range(256)]
    for v in vectors:
        assert oklab.rgb_to_oklab_fixed(v["rgb"]) == tuple(v["lab"])
    actual = oklab.rgb_to_oklab_fixed_numpy(np.array([v["rgb"] for v in vectors], dtype=np.uint8))
    np.testing.assert_array_equal(actual, [v["lab"] for v in vectors])
    assert actual.dtype == np.int64
    np.testing.assert_array_equal(oklab.rgb_to_oklab_fixed_numpy(np.array([255, 0, 0])), actual[256])


def test_tables_and_checksums(monkeypatch):
    assert oklab.LIN[0] == 0 and oklab.LIN[255] == 65535
    assert all(a <= b for a, b in zip(oklab.LIN, oklab.LIN[1:]))
    assert oklab.M1I == ((27015, 35149, 3372), (13887, 44610, 7038), (5787, 18463, 41286))
    assert oklab.M2I == ((13792, 52011, -267), (129630, -159160, 29530), (1698, 51300, -52997))
    for name in sorted(oklab.TABLE_SHA256):
        assert oklab.load_table(name)
    monkeypatch.setitem(oklab.TABLE_SHA256, "m1i_v1.json", "bad")
    with pytest.raises(ValueError, match="checksum"):
        oklab.load_table("m1i_v1.json")


def test_icbrt_exact_boundary_vectors_and_large_integers():
    for root in [0, 1, 2, 3, 31, 255, 4095, 65535, 65536, 10 ** 40]:
        cube = root ** 3
        assert oklab.icbrt(cube) == root
        if root:
            assert oklab.icbrt(cube - 1) == root - 1
        assert oklab.icbrt(cube + 1) == (1 if root == 0 else root)
    rng = random.Random(451)
    for _ in range(1000):
        n = rng.randrange(1 << 49)
        k = oklab.icbrt(n)
        assert k ** 3 <= n < (k + 1) ** 3
    with pytest.raises(ValueError):
        oklab.icbrt(-1)


def test_distance_does_not_wrap_uint8():
    assert oklab.dist2(np.array([0, 0, 0], dtype=np.uint8), [255, 255, 255]) == 195075
    assert oklab.dist2((65535, -20000, 10000), (0, 20000, -10000)) == 6294836225
