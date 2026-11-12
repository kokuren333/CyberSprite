"""The only expectation writer. Review the printed summary and git diff after each update."""

import argparse
import difflib
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
            if before is not None and name.endswith(".json"):
                print(
                    "".join(
                        difflib.unified_diff(
                            before.decode("utf-8").splitlines(keepends=True),
                            data.decode("utf-8").splitlines(keepends=True),
                            fromfile=f"{case.name}/{name} (before)",
                            tofile=f"{case.name}/{name} (after)",
                        )
                    ),
                    end="",
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
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--case", action="append", help="Update only named cases (repeatable).")
    selection.add_argument(
        "--all", action="store_true", help="Select all cases; requires --confirm-all."
    )
    parser.add_argument(
        "--confirm-all", action="store_true", help="Confirm an intentional full update."
    )
    args = parser.parse_args()
    if args.all != args.confirm_all:
        parser.error("Use --all and --confirm-all together, or select explicit --case names.")
    available = {
        case.name: case for case in sorted(ROOT.iterdir()) if (case / "case.json").is_file()
    }
    unknown = sorted(set(args.case or []) - available.keys())
    if unknown:
        parser.error(f"Unknown cases: {', '.join(unknown)}. Available: {', '.join(available)}")
    count = 0
    for name, case in available.items():
        if args.all or name in args.case:
            count += update(case)
    print(
        f"Changed {count} expectation files. "
        "Inspect pixels, hashes, and canonical JSON before committing."
    )


if __name__ == "__main__":
    main()
