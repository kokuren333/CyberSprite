"""Read-only classification of golden differences for the M11 review."""

import json
from pathlib import Path

from golden_cases import execute_case


def diff(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        return [
            item
            for key in sorted(a.keys() | b.keys())
            for item in diff(a.get(key), b.get(key), path + "/" + key)
        ]
    if a != b:
        return [{"path": path, "before": a, "after": b}]
    return []


def main():
    results = {}
    for case in sorted(Path("tests/golden").iterdir()):
        if not (case / "case.json").is_file():
            continue
        changed = {}
        for name, data in sorted(execute_case(case).items()):
            path = case / "expected" / name
            before = path.read_bytes() if path.exists() else None
            if before != data:
                changed[name] = (
                    diff(json.loads(before), json.loads(data))
                    if before and name.endswith(".json")
                    else [
                        {"path": "/", "before_bytes": len(before or b""), "after_bytes": len(data)}
                    ]
                )
        if changed:
            results[case.name] = changed
            print(case.name, list(changed), flush=True)
    root = Path("build/r1-e1-review")
    root.mkdir(parents=True, exist_ok=True)
    (root / "golden-differences.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
