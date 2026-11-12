import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cybersprite.formats.png import decode_png

ROOT = Path(__file__).resolve().parents[2]


def invoke(*args, cwd=ROOT):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, "-m", "cybersprite", *map(str, args)],
        cwd=cwd,
        env=env,
        capture_output=True,
        encoding="utf-8",
    )
    return result, json.loads(result.stdout)


def test_fresh_cli_workflow(tmp_path):
    path = tmp_path / "新規.csprite"
    result, output = invoke("new", path, "--size", "3x2", "--frames", "2", "--name", "日本語")
    assert result.returncode == 0 and output["revision"] == 0
    assert output["op"] == "new_project" and output["result"]["name"] == "日本語"
    initial = (path / "project.json").read_bytes()
    result, output = invoke("-p", path, "info", "--include", "palette,validation")
    assert result.returncode == 0 and output["result"]["frame_count"] == 2
    image = tmp_path / "out.png"
    result, output = invoke(
        "-p",
        path,
        "render",
        "--frame",
        "1",
        "--out",
        image,
        "--scale",
        "2",
        "--indexed",
        "--compression",
        "stored",
    )
    assert result.returncode == 0 and output["result"]["verified"] is True
    assert output["result"]["validation_ok"] is True
    assert decode_png(image.read_bytes()).pixels.shape == (4, 6)
    result, output = invoke("-p", path, "validate", "--strict")
    assert result.returncode == 0 and output["result"]["issues"] == []
    assert output["result"]["scope"] == "structural"
    assert (path / "project.json").read_bytes() == initial
    result, output = invoke("info", cwd=path)
    assert result.returncode == 0 and output["revision"] == 0


def test_appendix_cli_workflow(tmp_path):
    path = ROOT / "tests/fixtures/appendix_a/project.json"
    result, output = invoke("-p", path, "info")
    assert result.returncode == 0 and output["revision"] == 5
    for frame in (0, 1):
        result, output = invoke(
            "-p", path, "render", "--frame", frame, "--out", tmp_path / f"frame{frame}.png"
        )
        assert result.returncode == 0 and output["result"]["verified"]
    result, output = invoke("-p", path, "validate")
    assert result.returncode == 0 and output["result"]["ok"]


@pytest.mark.parametrize(
    ("args", "expected_exit", "code"),
    [
        (("info",), 3, "E_PROJECT_NOT_FOUND"),
        (("not-a-command",), 2, "E_INVALID_ARGS"),
        (("new", "p", "--size", "abc"), 2, "E_INVALID_ARGS"),
        (("new", "p", "--size", "2x2", "--background", "1"), 6, "E_UNSUPPORTED"),
        (("new", "p", "--size", "8193x1"), 6, "E_LIMIT_EXCEEDED"),
        (("new", "p", "--size", "8192x8192"), 6, "E_LIMIT_EXCEEDED"),
        (("new", "p", "--size", "2x2", "--frames", "0"), 2, "E_INVALID_ARGS"),
        (("new", "p", "--size", "2x2", "--duration", "0"), 2, "E_INVALID_ARGS"),
        (("new", "p", "--size", "2x2", "--palette", "garbage"), 2, "E_INVALID_ARGS"),
        (("render", "--out", "x.png", "--frame", "bad"), 2, "E_INVALID_ARGS"),
    ],
)
def test_error_json_and_exit_codes(tmp_path, args, expected_exit, code):
    result, output = invoke(*args, cwd=tmp_path)
    assert result.returncode == expected_exit, output
    assert output["ok"] is False and output["error"]["code"] == code
    assert output["error"]["message"] and output["error"]["hint"]
    assert not result.stderr


def test_no_overwrites_or_writes_on_error(tmp_path):
    project = tmp_path / "p"
    invoke("new", project, "--size", "2x2")
    initial = (project / "project.json").read_bytes()
    result, output = invoke("new", project, "--size", "4x4")
    assert result.returncode == 3 and output["error"]["code"] == "E_EXISTS"
    assert output["op"] == "new_project"
    result, output = invoke("-p", project, "render", "--out", project / "project.json")
    assert result.returncode == 2 and output["error"]["code"] == "E_INVALID_ARGS"
    result, output = invoke("-p", project, "render", "--frame", "9", "--out", tmp_path / "bad.png")
    assert result.returncode == 3 and output["error"]["code"] == "E_FRAME_OUT_OF_RANGE"
    assert output["revision"] == {"before": 0, "after": 0}
    assert not (tmp_path / "bad.png").exists()
    assert (project / "project.json").read_bytes() == initial


def test_doctor_schema_and_version(tmp_path):
    result, output = invoke("doctor")
    assert result.returncode == 0 and "environment_fingerprint" in output["result"]
    result, output = invoke("schema", "all", "--out", tmp_path)
    assert result.returncode == 0
    assert (tmp_path / "project.schema.json").is_file()
    assert (tmp_path / "sources.schema.json").is_file()
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from cybersprite.cli import cli; "
            "assert 'numpy' not in sys.modules and 'pydantic' not in sys.modules; "
            "cli.main(['--version'])",
        ],
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0 and probe.stdout.strip() == "cybersprite, version 0.1.0"
