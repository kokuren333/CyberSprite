"""Install a release wheel in a temporary venv outside the repository and exercise it."""

import argparse
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "build/release-verification.json")
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "VIRTUAL_ENV"}}
    with TemporaryDirectory(prefix="cybersprite-release-") as temporary:
        root = Path(temporary)
        assert not root.resolve().is_relative_to(ROOT)
        venv = root / "venv"
        subprocess.run(["uv", "venv", "--python", "3.12", str(venv)], check=True, env=env)
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(
            ["uv", "pip", "install", "--python", str(python), str(wheel) + "[mcp,gui]"],
            check=True,
            env=env,
        )
        env["CYBERSPRITE_CONFIG_DIR"] = str(root / "config")
        subprocess.run(
            [
                str(python),
                str(ROOT / "tools/release_probe.py"),
                "--repo",
                str(ROOT),
                "--out",
                str(args.out.resolve()),
            ],
            cwd=root,
            check=True,
            env=env,
        )


if __name__ == "__main__":
    main()
