"""Common budgets and durable saves also cover source-only ingestion."""

import numpy as np
import pytest

from cybersprite import ops
from cybersprite.core import limits, sources
from cybersprite.core.errors import CyberSpriteError
from cybersprite.formats.png import encode_png


def test_add_source_shares_decode_budget_across_inputs(tmp_path, monkeypatch):
    raster = tmp_path / "input.png"
    raster.write_bytes(encode_png(np.full((2, 2, 4), 255, dtype=np.uint8)))
    project = tmp_path / "p"
    monkeypatch.setattr(limits, "DECODED_BYTES", 16)
    with pytest.raises(CyberSpriteError) as caught:
        ops.execute(
            "add_source",
            project,
            {"files": [str(raster), str(raster)], "provenance": {"license": "CC0-1.0"}},
        )
    assert caught.value.code == "E_LIMIT_EXCEEDED"
    assert caught.value.details == {"limit_name": "decoded_bytes", "requested": 32, "limit": 16}
    assert not (project / "source/manifest.json").exists()


def test_source_queries_before_project_creation(tmp_path):
    raster = tmp_path / "input.png"
    raster.write_bytes(encode_png(np.full((2, 2, 4), 255, dtype=np.uint8)))
    project = tmp_path / "p"
    result = ops.execute(
        "add_source",
        project,
        {"files": str(raster), "provenance": {"license": "CC0-1.0"}},
    )
    source_id = result["result"]["source"]
    assert ops.execute("list_sources", project)["result"]["sources"][0]["use"] == "design"
    assert ops.execute("get_source", project, {"id": source_id})["result"]["id"] == source_id
    assert not (project / "project.json").exists()


def test_source_save_failure_restores_originals_and_retry(tmp_path, monkeypatch):
    raster = tmp_path / "input.png"
    raster.write_bytes(encode_png(np.full((2, 2, 4), 255, dtype=np.uint8)))
    project = tmp_path / "p"
    ops.execute("new_project", project, {"width": 2, "height": 2})
    original = (project / "project.json").read_bytes()
    write = sources.atomic_write

    def fail_manifest(path, data):
        if path.name == "manifest.json":
            raise OSError("Injected manifest save failure")
        return write(path, data)

    monkeypatch.setattr(sources, "atomic_write", fail_manifest)
    args = {"files": str(raster), "provenance": {"license": "CC0-1.0"}}
    with pytest.raises(CyberSpriteError) as caught:
        ops.execute("add_source", project, args, idempotency_key="source-once")
    assert caught.value.code == "E_IO"
    assert not list((project / "source").glob("SRC*/*"))
    assert not (project / "source/manifest.json").exists()
    assert (project / "project.json").read_bytes() == original
    monkeypatch.setattr(sources, "atomic_write", write)
    result = ops.execute("add_source", project, args, idempotency_key="source-once")
    assert result["result"]["source"] is not None
    replay = ops.execute("add_source", project, args, idempotency_key="source-once")
    assert replay["replayed"]
    assert replay["result"] == result["result"]
    assert (project / "project.json").read_bytes() == original
