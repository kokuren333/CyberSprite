"""Check clean-room tracked paths and core import boundaries."""

import ast
import subprocess
import sys
from importlib.util import resolve_name
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def imported_names(node, path):
    if isinstance(node, ast.Import):
        return [item.name for item in node.names]
    if not isinstance(node, ast.ImportFrom):
        return []
    module = node.module or ""
    if node.level:
        package = ".".join(path.parent.relative_to(ROOT / "src").parts)
        try:
            module = resolve_name("." * node.level + module, package)
        except ImportError:
            return ["<invalid relative import>"]
    if module == "cybersprite":
        return [
            module if item.name == "__version__" else module + "." + item.name
            for item in node.names
        ]
    return [module]


def violations() -> list[str]:
    errors = []
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8")
    for path in tracked.split("\0"):
        if {"_private", "_handoff"} & set(path.split("/")):
            errors.append(f"Forbidden tracked path: {path}")
    for path in sorted((ROOT / "src/cybersprite/core").glob("**/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            for name in imported_names(node, path):
                root = name.split(".")[0]
                if root not in sys.stdlib_module_names | {"numpy", "pydantic"} and not (
                    name in {"cybersprite", "cybersprite.core"}
                    or name.startswith("cybersprite.core.")
                ):
                    errors.append(
                        f"Forbidden core import {name}: {path.relative_to(ROOT)}:{node.lineno}"
                    )
    return errors


if __name__ == "__main__":
    errors = violations()
    print("\n".join(errors) if errors else "Clean-room paths and core imports: OK")
    raise SystemExit(bool(errors))
