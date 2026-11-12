"""Evaluate stricter grid gates against saved final decisions without changing defaults."""

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rejected(grid, policy):
    if not grid or not grid.get("detected") or grid.get("mode") != "auto":
        return False
    if policy == "alignment-308":
        return grid["alignment"] < 308
    if policy == "short-side-12":
        return min(grid["columns"], grid["rows"]) < 12
    if policy == "small-grid-residual-100":
        return min(grid["columns"], grid["rows"]) < 12 and grid["snap_variance"] > 100
    raise ValueError(policy)


def evaluate(calibration, synthetic):
    rows = [
        dict(r, source=r["name"], group=r["category"])
        for r in calibration["records"]
        if r["category"] in ("d", "e", "d-nonpixel-control")
    ]
    for row in synthetic:
        if row["method"] == "builtin" and "error" not in row:
            rows.append(dict(row, group="synthetic-" + row["family"]))
    result = {}
    for policy in ("alignment-308", "short-side-12", "small-grid-residual-100"):
        counts = {}
        newly_rejected = []
        for row in rows:
            group = row["group"]
            c = counts.setdefault(group, Counter())
            c["n"] += 1
            before = row.get("accepted")
            after = before is True and not rejected(row.get("grid"), policy)
            c["accepted_before"] += before is True
            c["accepted_after"] += after
            if before and not after:
                newly_rejected.append(
                    {
                        "source": row["source"],
                        "group": group,
                        "recipe": row.get("recipe"),
                        "grid": row["grid"],
                    }
                )
        result[policy] = {"counts": counts, "newly_rejected": newly_rejected}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    calibration = json.loads((ROOT / "docs/reference/pixelize_calibration_v5.json").read_text())
    if args.bench.suffix == ".jsonl":
        synthetic = [json.loads(line) for line in args.bench.read_text().splitlines()]
    else:
        synthetic = json.loads(args.bench.read_text())["records"]
    results = evaluate(calibration, synthetic)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v["counts"] for k, v in results.items()}, indent=2))


if __name__ == "__main__":
    main()
