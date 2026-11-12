"""Valid compact unions and retained full parsing after the R1 branch integration."""

import pytest

pytest.importorskip("mcp.server")
from jsonschema import Draft202012Validator  # noqa: E402

from cybersprite.mcp.server import MCPService  # noqa: E402


def test_compact_region_accepts_each_documented_shape(tmp_path):
    service = MCPService(root=tmp_path)
    validator = Draft202012Validator(service.contracts["outline"]["inputSchema"])
    for region in (
        {"type": "all"},
        {"type": "rect", "x": 0, "y": 0, "w": 2, "h": 2},
        {"type": "ellipse", "x": 0, "y": 0, "w": 2, "h": 2},
        {"type": "not", "of": [{"type": "all"}]},
    ):
        validator.validate(
            {"project": "p", "layer": "L1", "frame": 0, "color": 1, "region": region}
        )


def test_compact_nullable_constraints_and_full_validation(tmp_path):
    service = MCPService(root=tmp_path)
    schema = service.contracts["set_pixel"]["inputSchema"]
    validator = Draft202012Validator(schema)
    values = {"project": "p", "layer": "L1", "frame": 0, "x": 0, "y": 0, "color": 1}
    validator.validate({**values, "expect_revision": None, "idempotency_key": None})
    assert not validator.is_valid({**values, "expect_revision": -1})
    assert not validator.is_valid({**values, "idempotency_key": "x" * 65})
    assert not service.call("new_project", {"project": "p", "width": 2, "height": 2}).is_error
    response = service.call("set_pixel", {**values, "mask": {"only_on": ["@missing"]}})
    assert response.is_error
    assert response.structured_content["error"]["code"] == "E_INVALID_ARGS"
    response = service.call("set_pixel", {**values, "mask": {"unknown": True}})
    assert response.is_error
    assert response.structured_content["error"]["code"] == "E_INVALID_ARGS"


def test_shared_local_definitions_resolve_offline(tmp_path):
    service = MCPService(root=tmp_path)
    schema = service.contracts["export_sheet"]["inputSchema"]
    assert schema["$defs"]
    validator = Draft202012Validator(schema)
    values = {"project": "p", "out": "sheet.png", "columns": None, "trim": False}
    validator.validate(values)
    assert not validator.is_valid({**values, "columns": 0})
    assert not validator.is_valid({**values, "trim": "false"})
