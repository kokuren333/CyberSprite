"""Content-cache equivalence across real transactions and independent byte encoders."""

import gzip
from copy import deepcopy
from random import Random

import pytest

from cybersprite.core import quality
from cybersprite.core.canonical import _ordered, dumps_project, json_bytes, load_project
from cybersprite.core.history import snapshot_bytes
from cybersprite.core.models import UserData
from cybersprite.core.normalize import normalize_cels
from cybersprite.core.quality import report, validation_delta
from cybersprite.core.transactions import _transaction_copy
from cybersprite.ops import execute
from tools.bench import fixture
from tools.m5_cases import tile_project


@pytest.mark.parametrize("seed", range(881, 889))
def test_random_op_sequences_cached_reports_and_deltas_match_full(tmp_path, seed):
    rng = Random(seed)
    root = tmp_path / "sequence.csprite"
    execute("new_project", root, {"width": 8, "height": 8, "frames": 4})
    execute("add_layer", root, {"name": "Other"}, preview="none")
    execute("add_tag", root, {"name": "all", "from": 0, "to": 3}, preview="none")
    for i in range(65):
        before = load_project(root)
        cached_before = report(before, root=root)
        full_before = report(before, root=root, use_cache=False)
        layer, frame = rng.choice(["L1", "L2"]), rng.randrange(4)
        choice = i % 13
        if choice < 3:
            name, args = (
                "set_pixel",
                {
                    "layer": layer,
                    "frame": frame,
                    "x": rng.randrange(8),
                    "y": rng.randrange(8),
                    "color": rng.randrange(3),
                },
            )
        elif choice == 3:
            name, args = "update_layer", {"layer": layer, "visible": bool(rng.randrange(2))}
        elif choice == 4:
            name, args = "update_layer", {"layer": layer, "opacity": rng.choice([128, 255])}
        elif choice == 5:
            name, args = (
                "set_palette_color",
                {"index": 1, "color": rng.choice(["#000000ff", "#ff0000ff"])},
            )
        elif choice == 6:
            name, args = (
                "set_validation",
                {
                    "settings": {
                        "min_cluster": rng.randrange(1, 5),
                        "orphan_pixels_max": rng.randrange(3),
                        "colors_per_frame_max": rng.randrange(1, 4),
                        "severity": {"Q-PIX-02": rng.choice(["off", "error", "info"])},
                    }
                },
            )
        elif choice == 7:
            name, args = (
                "set_frame_duration",
                {"frames": [frame], "duration_ms": rng.choice([91, 100])},
            )
        elif choice == 8:
            name, args = "reverse_frames", {"from": 0, "to": 3}
        elif choice == 9:
            name, args = "clear_cel", {"layer": layer, "frame": frame}
        elif choice == 10:
            name, args = "set_project_meta", {"name": f"State {rng.randrange(3)}"}
        elif choice == 11:
            name, args = (
                "update_layer",
                {"layer": layer, "blend_mode": rng.choice(["normal", "multiply"])},
            )
        else:
            name, args = (
                "set_palette_color",
                {"index": 2, "color": rng.choice(["#ffffffff", "#ffffff80"])},
            )
        result = execute(name, root, args, preview="none")
        after = load_project(root)
        cached_after, full_after = (
            report(after, root=root),
            report(after, root=root, use_cache=False),
        )
        assert json_bytes(cached_before) == json_bytes(full_before)
        assert json_bytes(cached_after) == json_bytes(full_after)
        assert result["validation"] == validation_delta(full_before, full_after)
        assert validation_delta(cached_before, cached_after) == result["validation"]
        assert dumps_project(after) == json_bytes(_ordered(after))


def test_cached_points_cannot_be_poisoned_by_a_report_consumer():
    p = fixture(2)
    p.layers[0].cels[0].pixels = ["0100", "0000"]
    expected = report(p, use_cache=False)
    value = report(p)
    point_issue = next(i for i in value["issues"] if i["where"]["points"])
    point_issue["where"]["points"][0][0] = 100
    assert report(p) == expected


def test_tiles_links_groups_and_settings_cache_invalidation():
    p = tile_project()
    for i in range(12):
        report(p)
        p.tilesets[0].tiles[1].pixels[0] = ("01" if i % 2 else "02") * p.tilesets[0].tile_w
        p.validation.min_cluster = i + 1
        p.frames[0].duration_ms = 100 + i
        assert json_bytes(report(p)) == json_bytes(report(p, use_cache=False))


def test_transaction_copy_and_normalization_detach_all_mutable_data():
    p = fixture(8, 2, 3)
    p.user_data = UserData(properties={"nested": [{"pixels": ["Original"], "value": 1.5}]})
    original = deepcopy(p)
    q = _transaction_copy(p)
    assert q == original
    q.layers[0].cels[0].pixels[0] = "00" * 8
    q.user_data.properties["nested"][0]["pixels"].append("Changed")
    assert p == original
    assert normalize_cels(q) == normalize_cels(deepcopy(q), in_place=True)
    assert p == original


def test_canonical_row_cache_matches_reference_for_controls_and_extension_keys():
    p = fixture(2)
    p.name = '日本語 " \\ \b\t\n\f\r\x00\x1f'
    p.extensions = {"test.data": {"pixels": [{"quoted": "\\n"}], "tiles": [1, 2]}}
    p.user_data = UserData(properties={"nested": [True, None, 1.5, {}, []]})
    reference = json_bytes(_ordered(p))
    assert dumps_project(p) == reference
    zipped = snapshot_bytes(p, canonical=reference)
    assert zipped == snapshot_bytes(p)
    assert gzip.decompress(zipped) == reference
    assert zipped[4:8] == bytes(4) and zipped[9] == 255


def test_frame_cache_is_bounded_and_does_not_hide_invalid_frame(monkeypatch):
    quality._FRAME_CACHE.clear()
    monkeypatch.setattr(quality, "_FRAME_CACHE_BYTES", 48 * 1024)
    for i in range(70):
        p = fixture(2)
        p.layers[0].cels[0].x = i
        report(p)
    assert (
        sum(quality._frame_bytes(value) for value in quality._FRAME_CACHE.values())
        <= quality._FRAME_CACHE_BYTES
    )
    assert quality.cached_frame_rgba(p, -1) is None
    assert quality.cached_frame_rgba(p, True) is None
