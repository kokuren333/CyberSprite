"""Real GUI server and CLI processes alternate on the same project on every OS."""

from tests.e2e.mixed_replay import replay_mixed
from tests.e2e.replay import SCENARIOS


def test_scenario4(tmp_path):
    directory = SCENARIOS / "scenario4"
    outputs, notifications = replay_mixed(directory, tmp_path)
    assert notifications == [1, 2, 3, 4]
    for name, data in outputs.items():
        assert data == (directory / "expected" / name).read_bytes(), name
