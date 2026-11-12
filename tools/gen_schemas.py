"""Generate committed schemas, or check drift without writing."""

import argparse
from pathlib import Path

from cybersprite.core.schemas import generate_schemas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "schemas")
    args = parser.parse_args()
    failed = False
    for name, data in generate_schemas().items():
        path = args.out / f"{name}.schema.json"
        if args.check:
            if not path.exists() or path.read_bytes() != data:
                print(f"Schema drift: {path}. Run uv run python tools/gen_schemas.py.")
                failed = True
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            print(f"Wrote {path}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
