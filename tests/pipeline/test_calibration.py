import json
from pathlib import Path

from tools.calibrate_pipeline import next_version, thresholds

ROOT = Path(__file__).resolve().parents[2]


def test_calibrated_defaults_follow_recorded_measurements():
    measured = json.loads((ROOT / "tests/pipeline/calibration_metrics.json").read_bytes())
    defaults = json.loads((ROOT / "src/cybersprite/data/pipeline_defaults.json").read_bytes())
    assert (
        defaults["calibration"]["legacy_calibration_version"] == measured["calibration"]["version"]
    )
    assert defaults["calibration"]["legacy_metric_cases"] == measured["calibration"]["cases"]
    assert defaults["calibration"]["pending"] == []
    rows = measured["records"]
    assert len(rows) == 547
    assert sum(r["grid_exact"] for r in rows if r["category"] == "c-auto") >= 62
    assert {c: sum(r["category"] == c for r in rows) for c in "abcef"} == {
        "a": 255,
        "b": 136,
        "c": 34,
        "e": 12,
        "f": 34,
    }
    assert all(r["exact"] for r in rows if r["category"] == "a")
    assert (
        next_version(defaults, measured, rows, measured["grid_score"], measured["fidelity"])
        == defaults["calibration"]["version"]
    )
    assert (
        next_version(
            defaults, measured, rows + rows[:1], measured["grid_score"], measured["fidelity"]
        )
        == defaults["calibration"]["version"] + 1
    )
    for metric, higher in (("grid_score", True), ("fidelity", False)):
        result = thresholds(rows, metric, higher)
        assert measured[metric] == result
        assert defaults["presets"]["ai"]["gates"][metric] == result["thresholds"]
        fail = result["thresholds"][0]
        assert all(
            r[metric] >= fail if higher else r[metric] <= fail
            for r in rows
            if r["category"] in "abc"
        )


def test_generated_corpus_integrity():
    import hashlib

    directory = ROOT / "tests/pipeline/corpus/generated"
    manifest = json.loads((directory / "manifest.json").read_bytes())
    assert manifest["independent_generations"] == len(manifest["images"]) == 16
    assert sum(row["category"] == "d" for row in manifest["images"]) == 13
    assert sum(path.stat().st_size for path in directory.iterdir() if path.is_file()) <= 12_000_000
    for row in manifest["images"]:
        assert hashlib.sha256((directory / row["file"]).read_bytes()).hexdigest() == row["sha256"]
        assert not row["processing"]["resized"] and row["ground_truth"] is None
        assert row["license"].startswith("unknown") and row["prompt"] and row["date"]
