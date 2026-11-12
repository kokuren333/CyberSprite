"""A misleading distribution classifier must not hide actual bundled grants."""

from types import SimpleNamespace

import pytest

from tools import check_licenses

LGPL_TEXT = "GNU LESSER GENERAL PUBLIC LICENSE\nVersion 2.1, February 1999"
MIT0_TEXT = "MIT No Attribution\nPermission is hereby granted, free of charge"


@pytest.mark.parametrize(
    "text,expected,allowed",
    [
        (LGPL_TEXT, "LGPL-2.1-only", False),
        # MIT-0 is permissive and explicitly allowed (I-012), but must still be identified.
        (MIT0_TEXT, "MIT-0", True),
    ],
)
def test_actual_grant_precedes_package_metadata(monkeypatch, text, expected, allowed):
    dist = SimpleNamespace(metadata={"Name": "example", "License-Expression": "MIT"}, version="1")
    monkeypatch.setattr(check_licenses, "license_files", lambda _: [("bundled/LICENSE", text)])
    expression, source = check_licenses.identify_license(dist)
    assert expression == expected
    assert check_licenses.allowed_expression(expression) is allowed
    assert "bundled/LICENSE" in source


def test_reviewed_exception_is_version_pinned(monkeypatch):
    monkeypatch.setattr(
        check_licenses, "license_files", lambda _: [("adodbapi/license.txt", LGPL_TEXT)]
    )
    pinned = SimpleNamespace(metadata={"Name": "pywin32"}, version="312")
    other = SimpleNamespace(metadata={"Name": "pywin32"}, version="999")
    assert check_licenses.allowed_expression(check_licenses.identify_license(pinned)[0])
    assert not check_licenses.allowed_expression(check_licenses.identify_license(other)[0])
