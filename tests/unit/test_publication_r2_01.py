"""R2-01: CLI outputs written outside the Op registry use the export preflight.

Each case reproduces REVIEW_2 R2-01: the destination aliases the project's
canonical file, its history journal, or a registered source. The CLI must
refuse with the same error as export and leave every existing byte unchanged.
"""

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest
from click.testing import CliRunner

from cybersprite.cli import cli
from cybersprite.formats.png import encode_png
from cybersprite.ops import execute


@pytest.fixture
def runner(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CYBERSPRITE_NOW", "2026-11-12T12:00:00+09:00")
    monkeypatch.setenv("APPDATA", str(tmp_path / "settings"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "settings"))
    return CliRunner()


@pytest.fixture
def project(runner, tmp_path):
    root = tmp_path / "work" / "q.csprite"
    execute("new_project", root, {"width": 8, "height": 8, "frames": 2})
    execute(
        "set_pixel", root, {"layer": "L1", "frame": 0, "x": 1, "y": 1, "color": 1}, preview="none"
    )
    design = tmp_path / "design.png"
    design.write_bytes(encode_png(np.full((4, 4, 4), (10, 20, 30, 255), dtype=np.uint8)))
    execute("add_source", root, {"files": str(design), "provenance": {"license": "unknown"}})
    return root


def digest_tree(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(Path(root).rglob("*"))
        if path.is_file() and ".cybersprite/lock" not in path.as_posix()
    }


def run(runner, *args):
    result = runner.invoke(cli, list(map(str, args)))
    return result.exit_code, json.loads(result.stdout)


PROTECTED = [
    "work/q.csprite/source/SRC1/original_0000.png",
    "work/q.csprite/source/manifest.json",
    "work/q.csprite/.cybersprite/history/journal.jsonl",
    "work/q.csprite/project.json",
    "work/q.csprite/SOURCE/SRC1/original_0000.png",  # case alias
    "work/q.csprite/source/../source/SRC1/original_0000.png",
]


@pytest.mark.parametrize("command", ["render", "preview", "diff"])
@pytest.mark.parametrize("destination", PROTECTED)
def test_project_owned_destinations_are_refused_like_export(runner, project, command, destination):
    before = digest_tree(project)
    code, output = run(runner, "-p", project, command, "--out", destination)
    assert code == 4, output
    assert output["ok"] is False and output["error"]["code"] == "E_PATH_NOT_ALLOWED"
    assert output["error"]["details"]["reason"] == "protected_project_file"
    assert digest_tree(project) == before
    # The same destination through export is refused with the same code and reason.
    code, exported = run(
        runner, "-p", project, "export", "image", "--out", destination, "--overwrite"
    )
    assert code == 4 and exported["error"]["code"] == "E_PATH_NOT_ALLOWED"
    assert exported["error"]["details"]["reason"] == "protected_project_file"
    assert digest_tree(project) == before
    # The project stays editable: the journal and manifest were not replaced.
    code, edited = run(
        runner, "-p", project, "op", "set_pixel", "layer=L1", "frame=0", "x=2", "y=2", "color=1"
    )
    assert code == 0 and edited["ok"], edited


@pytest.mark.parametrize("command", ["render", "preview", "diff"])
def test_destinations_outside_the_working_directory_are_refused(runner, project, command):
    code, output = run(runner, "-p", project, command, "--out", "../outside_cwd.png")
    assert code == 4 and output["error"]["code"] == "E_PATH_NOT_ALLOWED"
    assert not (Path.cwd().parent / "outside_cwd.png").exists()


def test_directory_outputs_are_checked_before_any_write(runner, project):
    before = digest_tree(project)
    for args in (
        ("-p", project, "preview", "--frames", "all", "--out", "work/q.csprite/source"),
        ("-p", project, "diff", "--out", "work/q.csprite/.cybersprite"),
        ("schema", "all", "--out", "work/q.csprite/source"),
        ("schema", "all", "--out", "work/q.csprite/.cybersprite/history"),
    ):
        code, output = run(runner, *args)
        assert code == 4 and output["error"]["code"] == "E_PATH_NOT_ALLOWED", (args, output)
    assert digest_tree(project) == before
    assert not list((project / "source").glob("*.schema.json"))


def test_hard_link_to_a_registered_source_is_refused(runner, project):
    original = project / "source/SRC1/original_0000.png"
    os.link(original, "alias.png")
    before = digest_tree(project)
    for command in ("render", "preview", "diff"):
        code, output = run(runner, "-p", project, command, "--out", "alias.png")
        assert code == 4 and output["error"]["code"] == "E_PATH_NOT_ALLOWED"
    assert digest_tree(project) == before


def test_convert_refuses_protected_outputs_reports_and_stages(runner, project, tmp_path):
    source = tmp_path / "in.png"
    source.write_bytes(encode_png(np.full((8, 8, 4), (200, 10, 10, 255), dtype=np.uint8)))
    before = digest_tree(project)
    for args in (
        ("convert", "in.png", "work/q.csprite/source/SRC1/original_0000.png"),
        ("convert", "in.png", "work/q.csprite/.cybersprite/history/x.png"),
        ("convert", "in.png", "out.png", "--stages", "work/q.csprite/source/stages"),
        ("convert", "in.png", "../outside_cwd.png"),
    ):
        code, output = run(runner, *args)
        assert code == 4 and output["error"]["code"] == "E_PATH_NOT_ALLOWED", (args, output)
    assert digest_tree(project) == before
    assert not Path("out.png").exists() and not Path("out.png.report.json").exists()


def test_ordinary_outputs_still_work_and_may_replace_plain_files(runner, project):
    Path("render.png").write_bytes(b"old")
    for args in (
        ("-p", project, "render", "--out", "render.png"),
        ("-p", project, "preview", "--out", "previews/p.png"),
        ("-p", project, "diff", "--out", "diffs"),
        ("schema", "sources", "--out", "schemas"),
        # A project directory itself is not reserved; only its owned paths are.
        ("-p", project, "render", "--out", "work/q.csprite/render.png"),
    ):
        code, output = run(runner, *args)
        assert code == 0 and output["ok"], (args, output)
    assert Path("render.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert Path("schemas/sources.schema.json").is_file()
