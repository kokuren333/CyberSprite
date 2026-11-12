"""Build the GUI and release archives, then fail if wheel payloads are missing."""

import argparse
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/cybersprite/server/static"


def inspect_wheel(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        required = {
            f"cybersprite/{p.relative_to(ROOT / 'src/cybersprite').as_posix()}"
            for p in (ROOT / "src/cybersprite/data").rglob("*")
            if p.is_file() and p.name != ".gitkeep"
        }
        required.add("cybersprite/server/static/index.html")
        required.update(
            f"cybersprite/server/static/icons/{p.stem}.png"
            for p in (ROOT / "assets/ui/icons").glob("*.csprite")
        )
        missing = sorted(required - names)
        if missing:
            raise RuntimeError(f"Wheel payload is incomplete: {missing}")
        if not any(n.startswith("cybersprite/server/static/assets/") for n in names):
            raise RuntimeError("Wheel contains no built GUI assets; run the release builder.")
        for license_path in [
            ROOT / "LICENSE",
            ROOT / "NOTICE",
            *sorted((ROOT / "third_party/licenses").glob("*.txt")),
        ]:
            candidates = [
                n
                for n in names
                if ".dist-info/licenses/" in n
                and n.endswith("/" + license_path.relative_to(ROOT).as_posix())
            ]
            if len(candidates) != 1 or archive.read(candidates[0]) != license_path.read_bytes():
                raise RuntimeError(f"Wheel is missing the original license text: {license_path}")
        return {"wheel": path.name, "entries": len(names), "required_data": len(required)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    npm = shutil.which("npm")
    uv = shutil.which("uv")
    if npm is None or uv is None:
        parser.error("Install Node.js/npm and uv, then rerun tools/build_release.py.")
    subprocess.run([npm, "ci"], cwd=ROOT / "gui", check=True)
    subprocess.run(["node", "tools/check_js_licenses.mjs", "--check"], cwd=ROOT, check=True)
    # Remove only generated children under the verified static directory. Vite's
    # emptyOutDir=false preserves .gitkeep but otherwise leaves obsolete bundles.
    assert STATIC.resolve() == ROOT.resolve() / "src/cybersprite/server/static"
    for child in STATIC.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_symlink() or not child.is_dir():
            child.unlink()
        else:
            shutil.rmtree(child)
    subprocess.run([npm, "run", "build"], cwd=ROOT / "gui", check=True)
    subprocess.run([uv, "build", "--out-dir", str(args.out_dir.resolve())], cwd=ROOT, check=True)
    wheels = sorted(args.out_dir.glob("*.whl"))
    if not wheels:
        raise RuntimeError("uv build produced no wheel.")
    for wheel in wheels:
        print(json.dumps(inspect_wheel(wheel)))


if __name__ == "__main__":
    main()
