"""Python and GUI consume the same export sequence and duration vectors."""

import json
from pathlib import Path

import pytest

from cybersprite.core.models import Tag
from cybersprite.core.projects import new_project
from cybersprite.formats.common import animation_sequence
from tools.gen_playback_vectors import build_vectors

VECTORS = Path(__file__).resolve().parents[1] / "vectors/playback/sequences.json"
CASES = json.loads(VECTORS.read_bytes())["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_playback_sequence_and_durations(case):
    inputs, expected = case["input"], case["expected"]
    project = new_project(width=1, height=1, frames=len(inputs["durations_ms"]))
    for frame, duration in zip(project.frames, inputs["durations_ms"], strict=True):
        frame.duration_ms = duration
    project.tags = [Tag(**inputs["tag"])]
    sequence = animation_sequence(project, tag="T1", loop=inputs["loop"])
    assert sequence == expected["sequence"]
    assert [project.frames[i].duration_ms for i in sequence] == expected["durations_ms"]
    observed = sequence * inputs["cycles"]
    assert observed == expected["observed_sequence"]
    assert [project.frames[i].duration_ms for i in observed] == expected["observed_durations_ms"]


def test_playback_vectors_are_reproducible_and_cover_matrix():
    assert VECTORS.read_bytes() == build_vectors()
    matrix = {
        (
            case["input"]["tag"]["direction"],
            case["input"]["tag"]["to"] - case["input"]["tag"]["from"] + 1,
            case["input"]["tag"]["repeat"],
        )
        for case in CASES
    }
    assert matrix == {
        (direction, length, repeat)
        for direction in ("forward", "reverse", "pingpong", "pingpong_reverse")
        for length in (1, 2, 3, 4)
        for repeat in (0, 1, 2, 3)
    }
