"""The only expectation writer. Review the printed summary and git diff after each update."""

import argparse
import hashlib
from pathlib import Path

if __package__:
    from tools.golden_cases import execute_case
else:
    from golden_cases import execute_case

ROOT = Path(__file__).resolve().parents[1] / "tests/golden"


def update(case: Path) -> int:
    outputs = execute_case(case)
    destination = case / "expected"
    destination.mkdir(exist_ok=True)
    changed = 0
    for name, data in sorted(outputs.items()):
        path = destination / name
        before = path.read_bytes() if path.exists() else None
        if before != data:
            old_hash = hashlib.sha256(before).hexdigest()[:12] if before is not None else "NEW"
            print(
                f"{case.name}/{name}: {len(before or b'')} -> {len(data)} bytes; "
                f"{old_hash} -> {hashlib.sha256(data).hexdigest()[:12]}"
            )
            path.write_bytes(data)
            changed += 1
    for path in sorted(destination.iterdir()):
        if path.name not in outputs:
            print(f"{case.name}/{path.name}: REMOVED stale expectation")
            path.unlink()
            changed += 1
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", help="Update only named cases (repeatable).")
    args = parser.parse_args()
    count = 0
    for case in sorted(ROOT.iterdir()):
        if (case / "case.json").is_file() and (not args.case or case.name in args.case):
            count += update(case)
    print(
        f"Changed {count} expectation files. "
        "Inspect pixels, hashes, and canonical JSON before committing."
    )


if __name__ == "__main__":
    main()
