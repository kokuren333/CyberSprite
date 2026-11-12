import json
import random
import re
from pathlib import Path

import pytest

from cybersprite.core.canonical import dumps_project, loads_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.models import UserData


def test_appendix_a_is_exact(appendix):
    spec = (Path(__file__).resolve().parents[2] / "docs/SPEC.md").read_text(encoding="utf-8")
    source = re.search(r"```json\n(.*?)\n```", spec[spec.index("## 付録 A.") :], re.S)[1] + "\n"
    assert dumps_project(appendix) == source.encode()


def test_key_order_lowercase_and_omission(project):
    project.palette.colors += ["#FF0022FF"] * 10
    project.palette.names = {"10": "ten", "2": "two", "1": "one"}
    project.extensions = {"z.z": {"b": 1, "A": 2}, "a.a": {}}
    project.user_data = UserData()
    raw = dumps_project(project)
    assert b"user_data" not in raw
    assert b"#ff0022ff" in raw
    result = json.loads(raw)
    assert list(result["palette"]["names"]) == ["1", "2", "10"]
    assert list(result["extensions"]) == ["a.a", "z.z"]
    assert list(result["extensions"]["z.z"]) == ["A", "b"]
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n") and b"\r" not in raw


def test_controls_float_repr_and_non_ascii(project):
    project.name = "日本語"
    project.user_data = UserData(text='\n\t\b\r\f\x01\\n"', properties={"x": 1.25, "y": 1e-20})
    raw = dumps_project(project)
    assert "日本語".encode() in raw
    assert b"\\u000a\\u0009\\u0008\\u000d\\u000c\\u0001" in raw
    assert b"1.25" in raw and b"1e-20" in raw
    assert loads_project(raw).user_data == project.user_data


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_rejected(project, value):
    project.user_data = UserData(properties={"bad": value})
    with pytest.raises(CyberSpriteError, match="structural"):
        dumps_project(project)


def test_float_only_user_properties(project):
    project.extensions = {"test.data": {"user_data": {"properties": {"not_allowed": 1.25}}}}
    with pytest.raises(CyberSpriteError):
        dumps_project(project)


def test_noncanonical_json_is_accepted(project):
    raw = project.model_dump(by_alias=True)
    raw = dict(reversed(list(raw.items())))
    assert dumps_project(loads_project(json.dumps(raw, indent=7))) == dumps_project(project)


def test_random_canonical_roundtrip(project):
    rng = random.Random(101)

    def scramble(value):
        if isinstance(value, dict):
            keys = list(value)
            rng.shuffle(keys)
            return {key: scramble(value[key]) for key in keys}
        if isinstance(value, list):
            return [scramble(item) for item in value]
        return value

    for i in range(100):
        project.name = f"case {i} 日本"
        project.user_data = UserData(
            properties={"z": [rng.randrange(100), {"é": i}], "A": rng.random()}
        )
        expected = dumps_project(project)
        assert dumps_project(loads_project(json.dumps(scramble(json.loads(expected))))) == expected


@pytest.mark.parametrize("raw", [b"[]", b"{broken", b"\xff", b'{"schema_version":0}', b"null"])
def test_invalid_json(raw):
    with pytest.raises(CyberSpriteError) as caught:
        loads_project(raw)
    assert caught.value.code == "E_INVALID_PROJECT"


def test_newer_schema_is_actionable(project):
    raw = project.model_dump(by_alias=True)
    raw["schema_version"] = 2
    with pytest.raises(CyberSpriteError) as caught:
        loads_project(json.dumps(raw))
    assert caught.value.code == "E_SCHEMA_TOO_NEW"
    assert caught.value.details == {"schema_version": 2, "supported_version": 1}
