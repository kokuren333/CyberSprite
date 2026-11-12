"""A misleading distribution classifier must not hide actual bundled grants."""

from types import SimpleNamespace

import pytest

from tools import check_licenses


@pytest.mark.parametrize(
    "text,expected",
    [
        ("GNU LESSER GENERAL PUBLIC LICENSE\nVersion 2.1, February 1999", "LGPL-2.1-only"),
        ("MIT No Attribution\nPermission is hereby granted, free of charge", "MIT-0"),
    ],
)
def test_actual_grant_precedes_package_metadata(monkeypatch, text, expected):
    dist = SimpleNamespace(metadata={"Name": "example", "License-Expression": "MIT"}, version="1")
    monkeypatch.setattr(check_licenses, "license_files", lambda _: [("bundled/LICENSE", text)])
    expression, source = check_licenses.identify_license(dist)
    assert expression == expected
    assert not check_licenses.allowed_expression(expression)
    assert "bundled/LICENSE" in source
