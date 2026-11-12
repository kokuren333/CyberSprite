"""Read actual installed generation dependency licenses without changing the main lock."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tools.check_licenses import (
    allowed_expression,
    identify_license,
    license_files,
    runtime_closure,
)

ROOTS = [
    "torch",
    "diffusers",
    "transformers",
    "accelerate",
    "safetensors",
    "huggingface_hub",
    "peft",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for dist in runtime_closure(ROOTS):
        expression, basis = identify_license(dist)
        texts = license_files(dist)
        files = []
        for path, text in texts:
            raw = Path(dist.locate_file(path)).read_bytes()
            files.append(
                {
                    "path": path,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "text": text,
                }
            )
        # Native DLLs and their notices are not necessarily in dist-info.
        native = [
            str(file).replace("\\", "/")
            for file in sorted(dist.files or [], key=str)
            if str(file).lower().endswith((".dll", ".so", ".dylib", ".pyd"))
        ]
        rows.append(
            {
                "name": dist.metadata["Name"],
                "version": dist.version,
                "expression": expression,
                "basis": basis,
                "metadata_allowed": allowed_expression(expression),
                "license_files": files,
                "native_libraries": native,
            }
        )
        print(
            f"{dist.metadata['Name']} {dist.version}: {expression}; "
            f"{len(texts)} license files, {len(native)} native libraries"
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Metadata classification is provisional: review every bundled grant before acceptance.")


if __name__ == "__main__":
    main()
