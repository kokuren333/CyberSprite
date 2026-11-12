"""Evaluate generated-corpus grid recovery with a user-installed xprite, without GT.

This diagnostic preserves upstream RGBA output. CyberSprite gates and palette locking
are deliberately not inferred from an upstream classification or confidence score.
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np

from cybersprite.formats.png import encode_png

if __package__:
    from .pixelize_bench import CORPUS, ROOT, XpriteClient, digest, read_rgba
else:
    from pixelize_bench import CORPUS, ROOT, XpriteClient, digest, read_rgba


def evaluate(package, output, *, names=None):
    metadata = json.loads((package / "package.json").read_text(encoding="utf-8"))
    if metadata["name"] != "@xprite/pixelate" or metadata["version"] != "0.1.2":
        raise ValueError("This evaluation requires the audited @xprite/pixelate 0.1.2 package.")
    output.mkdir(parents=True, exist_ok=True)
    corpus = CORPUS / "generated"
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    client = XpriteClient(package)
    try:
        for entry in manifest["images"]:
            if names and entry["id"] not in names:
                continue
            image = read_rgba(corpus / entry["file"])
            start = time.perf_counter_ns()
            row = {
                "source": entry["file"],
                "category": entry["category"],
                "method": "xprite",
                "accepted": None,
                "raw_only": True,
            }
            try:
                data = client.run(
                    {
                        "width": image.shape[1],
                        "height": image.shape[0],
                        "data": image.reshape(-1).tolist(),
                    }
                )
                result = np.asarray(data["data"], dtype=np.uint8).reshape(
                    data["height"], data["width"], 4
                )
                directory = output / entry["id"]
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "raw.png").write_bytes(encode_png(result))
                row.update(
                    {
                        "size": [data["width"], data["height"]],
                        "grid": data["metrics"]["grid"],
                        "classification": data["metrics"]["classification"],
                        "confidence": data["metrics"]["confidence"],
                        "output_sha256": digest(result),
                    }
                )
            except Exception as error:
                row["error"] = f"{type(error).__name__}: {error}"
            row["elapsed_ms"] = (time.perf_counter_ns() - start) / 1_000_000
            rows.append(row)
            (output / "results.json").write_text(
                json.dumps({"version": 1, "generated": rows}, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            print(entry["id"], row.get("size"), row.get("error", ""), flush=True)
    finally:
        client.close()
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xprite-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "build/pixelize-generated")
    parser.add_argument("--names", nargs="+", help="Optional named corpus inputs.")
    args = parser.parse_args()
    evaluate(args.xprite_root, args.output, names=args.names)
