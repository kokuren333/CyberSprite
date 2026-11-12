"""Check clean-room tracked paths and core import boundaries."""

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def violations() -> list[str]:
    errors = []
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8")
    for path in tracked.split("\0"):
        if {"_private", "_handoff"} & set(path.split("/")):
            errors.append(f"Forbidden tracked path: {path}")
    for path in sorted((ROOT / "src/cybersprite/core").glob("**/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                names = [node.module or ""]
            for name in names:
                root = name.split(".")[0]
                if root not in sys.stdlib_module_names | {"numpy", "pydantic"} and not (
                    name == "cybersprite" or name.startswith("cybersprite.core")
                ):
                    errors.append(
                        f"Forbidden core import {name}: {path.relative_to(ROOT)}:{node.lineno}"
                    )
    return errors


if __name__ == "__main__":
    errors = violations()
    print("\n".join(errors) if errors else "Clean-room paths and core imports: OK")
    raise SystemExit(bool(errors))
