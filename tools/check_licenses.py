"""Fail closed on unapproved installed runtime dependency licenses (SPEC 2.1)."""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import re
import tomllib
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ALLOWED = {
    "MIT",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "Apache-2.0",
    "ISC",
    "Zlib",
    "HPND",
    "MIT-CMU",  # Explicitly included as HPND (MIT-CMU) in SPEC §2.1.
    "PSF-2.0",
    "Unlicense",
    "CC0-1.0",
}
# (normalized distribution name, exact version): (SPDX, reason). No silent unknown exemptions.
REVIEWED_EXCEPTIONS: dict[tuple[str, str], tuple[str, str]] = {}
# Build-time-only tools: never imported at runtime, never bundled into the wheel/sdist.
# Allowed ONLY when auditing build-system requirements (decision I-010 in docs/DECISIONS.md).
BUILD_ONLY_EXCEPTIONS: dict[str, tuple[str, str]] = {
    "pathspec": (
        "MPL-2.0",
        "hatchling build dependency; runs only at build time and is not distributed (I-010)",
    ),
}


def allowed_expression(expression: str) -> bool:
    """Small fail-closed SPDX parser: AND binds tighter than OR; WITH is unapproved."""
    tokens = re.findall(r"\(|\)|[A-Za-z0-9.+-]+", expression)
    if "".join(tokens) != re.sub(r"\s", "", expression):
        return False
    pos = 0

    def atom():
        nonlocal pos
        if pos >= len(tokens):
            raise ValueError("Missing operand")
        token = tokens[pos]
        pos += 1
        if token == "(":
            value = disjunction()
            if pos >= len(tokens) or tokens[pos] != ")":
                raise ValueError("Missing parenthesis")
            pos += 1
            return value
        return token in ALLOWED

    def conjunction():
        nonlocal pos
        value = atom()
        while pos < len(tokens) and tokens[pos] == "AND":
            pos += 1
            other = atom()
            value = value and other
        return value

    def disjunction():
        nonlocal pos
        value = conjunction()
        while pos < len(tokens) and tokens[pos] == "OR":
            pos += 1
            other = conjunction()
            value = value or other
        return value

    try:
        result = disjunction()
        return result and pos == len(tokens)
    except ValueError:
        return False


def license_files(dist) -> list[tuple[str, str]]:
    result = []
    for file in sorted(dist.files or [], key=str):
        name = str(file).replace("\\", "/")
        if ".dist-info/" in name and re.match(r"(?i)(license|licence|copying)", file.name):
            path = Path(dist.locate_file(file))
            if path.is_file():
                result.append((name, path.read_text(encoding="utf-8", errors="replace")))
    return result


def identify_license(dist) -> tuple[str, str]:
    name = canonicalize_name(dist.metadata["Name"])
    if (name, dist.version) in REVIEWED_EXCEPTIONS:
        return REVIEWED_EXCEPTIONS[name, dist.version]
    expression = dist.metadata.get("License-Expression", "")
    if expression:
        return expression, "License-Expression"
    declared = dist.metadata.get("License", "").strip()
    if declared in ALLOWED:
        return declared, "License"
    classifiers = dist.metadata.get_all("Classifier") or []
    mapping = {
        "MIT License": "MIT",
        "Apache Software License": "Apache-2.0",
        "ISC License (ISCL)": "ISC",
        "Python Software Foundation License": "PSF-2.0",
        "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
        "GNU General Public License v3 (GPLv3)": "GPL-3.0-only",
        "GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0-only",
        "GNU Affero General Public License v3": "AGPL-3.0-only",
    }
    for suffix, spdx in sorted(mapping.items(), key=lambda item: item[1] in ALLOWED):
        if any(item.endswith(" :: " + suffix) for item in classifiers):
            return spdx, "License classifier"
    texts = license_files(dist)
    # Recognize complete standard grants, never an arbitrary mention of a license name.
    for path, text in texts:
        if text.lstrip().startswith("Mozilla Public License Version 2.0"):
            return "MPL-2.0", path
        if "Redistribution and use in source and binary forms" in text and "THIS SOFTWARE" in text:
            spdx = "BSD-3-Clause" if "Neither the name" in text else "BSD-2-Clause"
            return spdx, path
        if (
            "Permission is hereby granted, free of charge" in text
            and "THE SOFTWARE IS PROVIDED" in text
        ):
            return "MIT", path
        if "Apache License" in text and "Version 2.0, January 2004" in text:
            return "Apache-2.0", path
        if "PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2" in text:
            return "PSF-2.0", path
    return "UNKNOWN", "No recognized SPDX expression, classifier, or complete license grant"


def runtime_closure(roots: list[str], distribution=metadata.distribution) -> list:
    environment = default_environment()
    environment["extra"] = ""
    queue = [(Requirement(root), "") for root in roots]
    visited = set()
    found = {}
    while queue:
        requirement, extra = queue.pop(0)
        env = {**environment, "extra": extra}
        if requirement.marker and not requirement.marker.evaluate(env):
            continue
        name = canonicalize_name(requirement.name)
        dist = distribution(name)
        if dist.version not in requirement.specifier:
            raise ValueError(f"Installed {name} {dist.version} does not satisfy {requirement}.")
        found[name] = dist
        for requested_extra in sorted(requirement.extras | {""}):
            key = (name, requested_extra)
            if key in visited:
                continue
            visited.add(key)
            queue.extend((Requirement(child), requested_extra) for child in dist.requires or [])
    return [found[name] for name in sorted(found)]


def audit(roots: list[str], build_only: bool = False) -> tuple[list[str], bool]:
    rows = []
    failed = False
    for dist in runtime_closure(roots):
        expression, source = identify_license(dist)
        valid = allowed_expression(expression)
        status = "OK" if valid else "FAIL"
        name = canonicalize_name(dist.metadata["Name"])
        if not valid and build_only and name in BUILD_ONLY_EXCEPTIONS:
            spdx, reason = BUILD_ONLY_EXCEPTIONS[name]
            if expression == spdx:
                valid, status, source = True, "OK(build-only)", reason
        rows.append(f"{status} {dist.metadata['Name']} {dist.version}: {expression} ({source})")
        failed |= not valid
    return rows, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-dev", action="store_true")
    parser.add_argument("--include-build", action="store_true")
    args = parser.parse_args()
    project = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )
    roots = list(project["project"]["dependencies"])
    if args.include_dev:
        roots.extend(project["dependency-groups"]["dev"])
    build_roots = list(project["build-system"]["requires"]) if args.include_build else []
    try:
        rows, failed = audit(roots)
        if build_roots:
            build_rows, build_failed = audit(build_roots, build_only=True)
            rows += build_rows
            failed |= build_failed
    except (metadata.PackageNotFoundError, ValueError) as error:
        print(f"FAIL: {error}. Run uv sync --locked before checking licenses.")
        return 1
    print("\n".join(rows))
    print(
        "Scope: installed distribution metadata; bundled native-library notices require M0 review."
    )
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
