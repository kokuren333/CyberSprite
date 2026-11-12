"""Full-report equivalence, frame reuse, and the lightweight info contract."""

import json
import subprocess
import sys
from random import Random

import numpy as np
import pytest

from cybersprite import ops
from cybersprite.core import quality
from cybersprite.core.components import Components
from cybersprite.core.models import ImageCel, ImageLayer
from cybersprite.core.pixels import pixels_to_rows
from cybersprite.core.projects import create_project, new_project
from tests.unit.test_components import reference_clusters
from tools.benchmark_r1_b2 import fixture


def oracle_analysis(image, ti):
    parts = reference_clusters(image, ti)
    labels = np.full(image.shape, -1, dtype=np.int32)
    for i, part in enumerate(parts):
        for x, y in part:
            labels[y, x] = i
    return Components(
        labels,
        np.array([len(part) for part in parts], dtype=np.int64),
        np.array([part[0][1] * image.shape[1] + part[0][0] for part in parts], dtype=np.int64),
    )


@pytest.mark.parametrize("seed", range(12))
def test_full_report_matches_legacy_cluster_oracle(seed, monkeypatch):
    rng = Random(1141 + seed)
    p = fixture(13, 11, 2, 3)
    p.palette.colors.append("#804020ff")
    for layer in p.layers:
        for cel in layer.cels:
            image = np.array(
                [[rng.randrange(4) for _ in range(13)] for _ in range(11)], dtype=np.uint8
            )
            cel.pixels = pixels_to_rows(image)
    p.palette.transparent_index = seed % 4
    p.validation.min_cluster = (2, 4, 65, 200)[seed % 4]
    p.validation.orphan_pixels_max = 0
    if seed % 2:
        p.layers[1].opacity = 128
    expected = quality.report(p, use_cache=False)
    assert expected["metrics"]["frames"] == 3
    monkeypatch.setattr(quality, "clusters", oracle_analysis)
    assert quality.report(p, use_cache=False) == expected


def test_attribution_uses_pixels_beyond_the_64_reported_points():
    p = new_project(width=260, height=1)
    p.layers = [ImageLayer(id=f"L{i + 1}", name=f"Layer {i + 1}") for i in range(2)]
    p.id_counters.layer = 2
    for layer, indices in zip(p.layers, (range(0, 128, 2), [258]), strict=True):
        image = np.zeros((1, 260), dtype=np.uint8)
        image[0, indices] = 1
        layer.cels = [ImageCel(frame=0, x=0, y=0, w=260, h=1, pixels=pixels_to_rows(image))]
    p.validation.orphan_pixels_max = 0
    result = quality.report(p)
    issues = [i for i in result["issues"] if i["rule"] in ("Q-PIX-01", "Q-PIX-02")]
    assert len(issues) == 2
    for issue in issues:
        assert issue["where"]["layer"] is None
        assert issue["where"]["points"] == [[x, 0] for x in range(0, 128, 2)]
    assert result["metrics"]["orphan_pixels_total"] == 65


def test_more_than_64_distinct_frames_are_reused_across_reports(monkeypatch):
    p = fixture(32, 32, 1, 70)
    quality._FRAME_CACHE.clear()
    original = quality.clusters
    calls = []

    def count(image, ti):
        calls.append(1)
        return original(image, ti)

    monkeypatch.setattr(quality, "clusters", count)
    first = quality.report(p)
    assert len(calls) == 70
    assert quality.report(p) == first
    assert len(calls) == 70
    p.layers[0].cels[0].pixels[1] = "02" + p.layers[0].cels[0].pixels[1][2:]
    assert quality.report(p) == quality.report(p, use_cache=False)
    assert len(calls) == 141  # One changed frame, then 70 explicitly uncached frames.


def test_summary_omits_validation_and_explicit_validation_still_runs(tmp_path, monkeypatch):
    root = tmp_path / "info.csprite"
    p = new_project(width=3, height=3)
    create_project(root, p)
    import cybersprite.core.transactions as transactions
    import cybersprite.ops.queries as queries

    reports = []
    original = queries.report

    def count(*args, **kwargs):
        reports.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(queries, "report", count)
    monkeypatch.setattr(transactions, "report", count)
    result = ops.execute("get_info", root)["result"]
    assert "validation_ok" not in result["summary"]
    assert not reports
    result = ops.execute("get_info", root, {"include": ["summary", "validation"]})["result"]
    assert result["validation"]["ok"]
    assert len(reports) == 1


def test_transactions_reuse_unchanged_frames_in_both_validation_reports(tmp_path, monkeypatch):
    root = tmp_path / "many.csprite"
    create_project(root, fixture(32, 32, 1, 70))
    quality._FRAME_CACHE.clear()
    original = quality.clusters
    calls = []

    def count(image, ti):
        calls.append(1)
        return original(image, ti)

    monkeypatch.setattr(quality, "clusters", count)
    # Read-only history queries no longer validate (R1-B1); warm the cache explicitly.
    ops.execute("validate", root)
    assert len(calls) == 70
    for color in (2, 1):
        result = ops.execute(
            "set_pixel",
            root,
            {
                "layer": "L1",
                "frame": 0,
                "x": 1,
                "y": 1,
                "color": color,
                "preview": "none",
            },
        )
        assert result["validation"]["ok"]
        assert len(calls) == 71


def test_info_loads_contracts_without_loading_unrelated_op_implementations(tmp_path):
    root = tmp_path / "lazy.csprite"
    create_project(root, new_project(width=3, height=3))
    code = """
import json, sys
from cybersprite import ops
registry = ops.registry()
definitions = registry.all()
assert len(definitions) >= 80
registry.get("get_info").describe()
ops.execute("get_info", sys.argv[1])
assert ops.execute("list_sources", sys.argv[1])["result"]["sources"] == []
print(json.dumps(sorted(sys.modules)))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(root)],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    modules = json.loads(result.stdout)
    for name in ("drawing", "frames", "palette", "structure", "canvas", "tiles", "ingest"):
        assert "cybersprite.ops." + name not in modules
    for name in (
        "cybersprite.pipeline.runner",
        "cybersprite.formats.export",
        "cybersprite.generate.backends",
        "PIL.Image",
    ):
        assert name not in modules
