import json
import subprocess
import sys
from email.message import Message
from pathlib import Path
from types import SimpleNamespace

import pytest

from cybersprite.core.schemas import generate_schemas
from tools.check_licenses import allowed_expression, identify_license, runtime_closure
from tools.check_repository import violations

ROOT = Path(__file__).resolve().parents[2]


def test_schema_drift():
    for name, generated in generate_schemas().items():
        committed = ROOT / "schemas" / f"{name}.schema.json"
        assert committed.read_bytes() == generated
        assert json.loads(generated)["additionalProperties"] is False


def test_cleanroom_and_core_import_boundary():
    assert violations() == []


@pytest.mark.parametrize(
    "expression",
    [
        "MIT",
        "MIT-CMU",
        "MIT AND BSD-3-Clause",
        "MIT OR GPL-3.0-only",
        "Apache-2.0 OR BSD-2-Clause",
        "(MIT OR ISC) AND Zlib",
    ],
)
def test_license_expressions_allowed(expression):
    assert allowed_expression(expression)


@pytest.mark.parametrize(
    "expression",
    [
        "",
        "UNKNOWN",
        "GPL-3.0",
        "LGPL-3.0",
        "AGPL-3.0",
        "MPL-2.0",
        "MIT AND GPL-3.0",
        "MIT rubbish",
        "MIT OR",
        "(MIT",
        "MIT AND",
        "MIT; rm",
        "MIT WITH Unknown-exception",
    ],
)
def test_license_expressions_fail_closed(expression):
    assert not allowed_expression(expression)


def dist(name, *, requires=(), license=None, version="1.0"):
    meta = Message()
    meta["Name"] = name
    if license:
        meta["License-Expression"] = license
    return SimpleNamespace(metadata=meta, version=version, files=[], requires=requires)


def test_license_unknown_and_disallowed_are_not_silently_exempted():
    assert identify_license(dist("unreviewed"))[0] == "UNKNOWN"
    assert identify_license(dist("unreviewed", license="MPL-2.0"))[0] == "MPL-2.0"


def test_runtime_closure_respects_markers_extras_and_cycles():
    items = {
        "a": dist(
            "a", requires=["b[x]>=1", "absent; python_version<'3'", "a[hidden]; extra=='hidden'"]
        ),
        "b": dist("b", requires=["a", "c; extra=='x'", "absent; extra=='other'"]),
        "c": dist("c"),
    }
    assert [d.metadata["Name"] for d in runtime_closure(["a"], items.__getitem__)] == [
        "a",
        "b",
        "c",
    ]
    with pytest.raises(ValueError, match="does not satisfy"):
        runtime_closure(["a>=2"], items.__getitem__)


def test_schema_script_can_check_without_writing():
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/gen_schemas.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
