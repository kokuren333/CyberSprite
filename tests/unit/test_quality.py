"""Detection and non-detection for every normative quality rule."""

from copy import deepcopy
from hashlib import sha256

import pytest

from cybersprite.core.canonical import json_bytes
from cybersprite.core.models import (
    ImageCel,
    Slice,
    SliceKey,
    Sources,
    Tag,
    Tile,
    TileCel,
    TilemapLayer,
    Tileset,
)
from cybersprite.core.projects import new_project
from cybersprite.core.quality import DEFAULT_LEVELS, report, validation_delta


def base():
    p = new_project(width=16, height=16, frames=2)
    p.layers[0].cels = [ImageCel(frame=0, x=1, y=1, w=2, h=1, pixels=["0101"])]
    return p


def prepare(rule):
    p = base()
    clean = deepcopy(p)
    if rule == "Q-PAL-01":
        p.validation.palette_max = 2
    elif rule == "Q-PAL-02":
        clean.layers[0].cels[0] = ImageCel(frame=0, x=1, y=1, w=3, h=1, pixels=["000102"])
    elif rule == "Q-PAL-03":
        p.palette.colors[2] = p.palette.colors[1]
    elif rule == "Q-PAL-04":
        p.palette.colors[1] = "#00000080"
    elif rule == "Q-PAL-05":
        p.validation.colors_per_frame_max = 1
    elif rule == "Q-PIX-01":
        p.validation.orphan_pixels_max = clean.validation.orphan_pixels_max = 0
        p.layers[0].cels[0].pixels = ["0102"]
    elif rule == "Q-PIX-02":
        p.layers[0].cels[0].pixels = ["0102"]
    elif rule == "Q-PIX-03":
        p.layers[0].cels[0].x = -10
    elif rule == "Q-LYR-01":
        p.layers[0].opacity = 128
    elif rule == "Q-LYR-02":
        p.layers[0].blend_mode = "multiply"
    elif rule == "Q-LYR-03":
        p.layers[0].cels = []
    elif rule == "Q-ANI-01":
        p.tags = [
            Tag(id="T1", name="loop", from_=0, to=1),
            Tag(id="T2", name="loop", from_=0, to=1),
        ]
        p.id_counters.tag = 2
    elif rule == "Q-ANI-02":
        p.validation.require_tag_coverage = clean.validation.require_tag_coverage = True
        p.tags = [Tag(id="T1", name="loop", from_=0, to=0)]
        clean.tags = [Tag(id="T1", name="loop", from_=0, to=1)]
        p.id_counters.tag = clean.id_counters.tag = 1
    elif rule == "Q-ANI-03":
        p.frames[0].duration_ms = 101
    elif rule == "Q-ANI-04":
        p.validation.silhouette_jitter_max = clean.validation.silhouette_jitter_max = 0
        p.tags = [Tag(id="T1", name="loop", from_=0, to=1)]
        p.id_counters.tag = 1
    elif rule == "Q-ANI-05":
        cel = deepcopy(p.layers[0].cels[0])
        cel.frame = 1
        p.layers[0].cels.append(cel)
    elif rule in ("Q-TIL-01", "Q-TIL-02"):
        for project in (p, clean):
            project.tilesets = [
                Tileset(id="TS1", name="tiles", tile_w=2, tile_h=1, tiles=[Tile(pixels=["0000"])])
            ]
            project.id_counters.tileset = 1
        p.tilesets[0].tiles.append(Tile(pixels=["0101"]))
        if rule == "Q-TIL-02":
            clean.tilesets[0].tiles.append(Tile(pixels=["0101"]))
            for project, ref in ((p, "1d"), (clean, "1")):
                project.layers.append(
                    TilemapLayer(
                        id="L2",
                        name="map",
                        tileset="TS1",
                        cels=[TileCel(frame=0, x=0, y=0, w=1, h=1, tiles=[ref])],
                    )
                )
                project.id_counters.layer = 2
    elif rule == "Q-SLC-01":
        p.slices = [Slice(id="S1", name="outside", keys=[SliceKey(frame=0, x=-1, y=0, w=2, h=2)])]
        p.id_counters.slice = 1
    return p, clean


@pytest.mark.parametrize(
    "rule", sorted(set(DEFAULT_LEVELS) - {"Q-SRC-01", "Q-SRC-02", "Q-SRC-03", "Q-SRC-04"})
)
def test_each_quality_rule_detects_and_does_not_detect(rule):
    p, clean = prepare(rule)
    assert rule in {i["rule"] for i in report(p)["issues"]}
    assert rule not in {i["rule"] for i in report(clean)["issues"]}


@pytest.mark.parametrize("rule", ["Q-SRC-01", "Q-SRC-02", "Q-SRC-03", "Q-SRC-04"])
def test_source_quality_detection_and_no_placements(tmp_path, rule):
    p = base()
    source = tmp_path / "source/SRC1"
    source.mkdir(parents=True)
    data = b"original image bytes"
    (source / "original.png").write_bytes(data)
    value = {
        "id": "SRC1",
        "kind": "imported",
        "files": [
            {
                "path": "SRC1/original.png",
                "sha256": sha256(data).hexdigest(),
                "width": 1,
                "height": 1,
                "bytes": len(data),
            }
        ],
        "provider": "file",
        "model": None,
        "prompt": "",
        "negative_prompt": "",
        "seed": None,
        "params": {},
        "license": "CC0-1.0",
        "rights_note": "",
        "url": "",
        "created_at": "2026-11-12T00:00:00Z",
        "imported_at": "2026-11-12T00:00:00Z",
        "pipeline": {
            "preset": "test",
            "params": {},
            "report": {"grid_score": 900},
            "result_sha256": "a" * 64,
            "accepted": True,
            "gates_overridden": [],
        },
        "placements": [{"revision": 0, "layer": "L1", "frames": [0]}],
    }
    if rule == "Q-SRC-01":
        value["pipeline"]["gates_overridden"] = ["grid"]
    elif rule == "Q-SRC-02":
        value["license"] = "unknown"
    elif rule == "Q-SRC-04":
        value["model"] = {
            "id": "test/model",
            "license": "CC0-1.0",
            "sha256": "a" * 64,
            "adapters": [],
        }
        value["params"] = {
            "model_registry": {
                "id": "test/model",
                "license": "CC0-1.0",
                "commercial_use": "unknown",
            }
        }
    else:
        (source / "original.png").write_bytes(b"changed")
    manifest = Sources.model_validate({"sources": [value]})
    path = tmp_path / "source/manifest.json"
    path.write_bytes(json_bytes(manifest.model_dump()))
    result = report(p, root=tmp_path)
    assert rule in {i["rule"] for i in result["issues"]}
    assert result["metrics"]["sources"]["grid_scores"] == {"SRC1": 900}
    if rule == "Q-SRC-04":
        manifest.sources[0].params["model_registry"]["commercial_use"] = "yes"
        path.write_bytes(json_bytes(manifest.model_dump()))
        assert rule not in {i["rule"] for i in report(p, root=tmp_path)["issues"]}
        manifest.sources[0].params["model_registry"]["commercial_use"] = "unknown"
    manifest.sources[0].placements = []
    path.write_bytes(json_bytes(manifest.model_dump()))
    assert rule not in {i["rule"] for i in report(p, root=tmp_path)["issues"]}


def test_severity_order_points_limit_and_metrics():
    p = base()
    p.layers[0].cels = [
        ImageCel(
            frame=0,
            x=0,
            y=0,
            w=16,
            h=16,
            pixels=[
                "".join("01" if x % 2 == y % 2 == 0 else "00" for x in range(16)) for y in range(16)
            ],
        )
    ]
    p.validation.orphan_pixels_max = 0
    p.validation.severity = {"Q-PIX-01": "error", "Q-PAL-02": "off", "Q-PIX-02": "warning"}
    result = report(p)
    assert not result["ok"] and result["issues"][0]["rule"] == "Q-PIX-01"
    assert all(len(i["where"]["points"]) <= 64 for i in result["issues"])
    assert result["metrics"]["orphan_pixels_total"] == 64
    assert "Q-PAL-02" not in {i["rule"] for i in result["issues"]}
    assert result["counts"]["error"] == 1


def test_delta_identity_and_array_sum_max_contract():
    p = base()
    before = report(p)
    p.layers[0].cels[0].x = 4
    after = report(p)
    delta = validation_delta(before, after)
    assert not delta["new_issues"] and not delta["resolved_issues"]
    assert "opaque_bbox" not in delta["metrics_delta"]
    p.validation.palette_max = 1
    result = validation_delta(after, report(p))
    assert result["new_issues"][0]["rule"] == "Q-PAL-01"
    assert not result["ok"]
    before["metrics"]["orphan_pixels"] = [1, 2]
    after["metrics"]["orphan_pixels"] = [2, 1]
    assert "orphan_pixels" not in validation_delta(before, after)["metrics_delta"]


def test_partial_offcanvas_is_info_and_rules_frame_filters():
    p = base()
    p.layers[0].cels[0].x = -1
    result = report(p)
    issue = next(i for i in result["issues"] if i["rule"] == "Q-PIX-03")
    assert issue["level"] == "info"
    assert not report(p, selected_frames=[1], rules=["Q-PIX-03"])["issues"]


def test_background_transparent_index_is_opaque_for_cluster_metrics():
    p = new_project(width=1, height=1)
    p.layers[0].background = True
    p.layers[0].cels = [ImageCel(frame=0, x=0, y=0, w=1, h=1, pixels=["00"])]
    result = report(p)
    assert result["metrics"]["orphan_pixels_total"] == 1
    assert result["metrics"]["opaque_pixels"] == [1]


@pytest.mark.parametrize("transparent_index", [0, 2])
@pytest.mark.parametrize("use_cache", [False, True])
def test_unused_palette_excludes_only_reserved_transparent_index(transparent_index, use_cache):
    p = new_project(width=2, height=1)
    p.palette.transparent_index = transparent_index
    p.palette.colors[0], p.palette.colors[transparent_index] = (
        p.palette.colors[transparent_index],
        p.palette.colors[0],
    )
    opaque = [i for i in range(3) if i != transparent_index]
    p.layers[0].cels = [
        ImageCel(frame=0, x=0, y=0, w=2, h=1, pixels=["".join(f"{i:02x}" for i in opaque)])
    ]
    before = report(p, use_cache=use_cache)
    assert "Q-PAL-02" not in {i["rule"] for i in before["issues"]}
    assert before["metrics"]["unused_palette"] == 0
    assert before["metrics"]["colors_used"] == 2

    p.layers[0].cels[0].pixels = [f"{opaque[0]:02x}" * 2]
    after = report(p, use_cache=use_cache)
    issue = next(i for i in after["issues"] if i["rule"] == "Q-PAL-02")
    assert issue["message"] == f"Unused palette indices: [{opaque[1]}]."
    assert after["metrics"]["unused_palette"] == 1
    delta = validation_delta(before, after)
    assert delta["metrics_delta"]["unused_palette"] == {"before": 0, "after": 1}
    assert issue in delta["new_issues"]

    p.layers[0].cels[0].pixels = [f"{opaque[0]:02x}{transparent_index:02x}"]
    used_transparency = report(p, use_cache=use_cache)
    assert used_transparency["metrics"]["unused_palette"] == 1
    assert used_transparency["metrics"]["colors_used"] == 2


def test_empty_transparent_only_palette_is_not_unused():
    p = new_project(width=1, height=1)
    p.palette.colors = ["#00000000"]
    p.palette.names = {}
    result = report(p)
    assert "Q-PAL-02" not in {i["rule"] for i in result["issues"]}
    assert result["metrics"]["unused_palette"] == 0
    assert result["metrics"]["colors_used"] == 0


@pytest.mark.parametrize("rule", ["Q-PIX-01", "Q-PIX-02"])
def test_pixel_issues_attribute_a_single_visible_layer(rule):
    from cybersprite.core.models import ImageLayer

    p = new_project(width=4, height=4)
    p.validation.orphan_pixels_max = 0
    p.layers[0].cels = [ImageCel(frame=0, x=1, y=1, w=1, h=1, pixels=["01"])]
    p.layers.append(ImageLayer(id="L2", name="Empty"))
    p.id_counters.layer = 2
    issue = next(i for i in report(p)["issues"] if i["rule"] == rule)
    assert issue["where"]["layer"] == "L1"
    p.layers[1].cels = [ImageCel(frame=0, x=3, y=3, w=1, h=1, pixels=["02"])]
    issue = next(i for i in report(p)["issues"] if i["rule"] == rule)
    assert issue["where"]["layer"] is None  # One frame-wide issue includes both layers.
    p.layers[1].visible = False
    issue = next(i for i in report(p)["issues"] if i["rule"] == rule)
    assert issue["where"]["layer"] == "L1"
