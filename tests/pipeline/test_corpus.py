import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from corpus.synthetic import cases, corpus_grid, perturbed, run_case
from cybersprite.pipeline.grid import detect_grid

CASES = list(cases())
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("name,image,truth,factor", CASES, ids=[c[0] for c in CASES])
def test_a_exact_recovery_and_repeat_bytes(name, image, truth, factor):
    settings = corpus_grid(name, factor)
    original = image.tobytes()
    first, report = run_case(image, grid_settings=settings)
    second, repeated = run_case(image, grid_settings=settings)
    np.testing.assert_array_equal(first, truth)
    assert first.tobytes() == second.tobytes()
    assert json.dumps(report, sort_keys=True) == json.dumps(repeated, sort_keys=True)
    assert report["accepted"]
    assert report["grid"]["grid_score"] == 1000 and report["metrics"]["fidelity"] == 0
    assert image.tobytes() == original


@pytest.mark.parametrize("variant", ["integer-noise", "edge-mix"])
def test_b_style_scores_only(variant):
    name, image, _, factor = next(c for c in CASES if c[0] == "ramp-s4-crop00")
    degraded = perturbed(image, variant)
    _, report = run_case(degraded, degraded=True)
    assert 0 <= report["grid"]["grid_score"] <= 1000
    assert report["metrics"]["fidelity"] >= 0
    assert report["grid"]["detected"]


def test_sparse_shapes_need_explicit_grid_under_specified_peak_rule():
    name, image, truth, factor = next(c for c in CASES if c[0] == "shapes-s4-crop00")
    auto = detect_grid(image)
    assert auto["grid_score"] < 990
    actual, report = run_case(image, grid_settings=corpus_grid(name, factor))
    assert np.array_equal(actual, truth) and report["accepted"]


def test_hash_seed_independence_across_processes():
    code = """import sys,json; sys.path.insert(0,'tests/pipeline')
from corpus.synthetic import *
name,image,truth,factor=next(c for c in cases() if c[0]=='ramp-s4-crop00')
_,report=run_case(image); print(json.dumps(report,sort_keys=True))
"""
    outputs = []
    for seed in ("1", "451"):
        outputs.append(subprocess.check_output([sys.executable, "-c", code], cwd=ROOT,
                       env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(ROOT / "src")}))
    assert outputs[0] == outputs[1]
