"""Build / update the UI icon projects with the CyberSprite CLI only.

For every icon in icon_grids.all_icons():
  1. `cybersprite new <name>.csprite --size 16x16 --palette ui-icons.gpl` (first time only)
  2. read the current pixels with `cybersprite pixels --as sym`; when they differ from the
     design, `cybersprite apply -` one transaction holding a single full-canvas `draw_rows`
  3. `cybersprite validate`
  4. `cybersprite render` at x1 and x4 into the review directory (optional, --renders DIR)

No pixel is written by anything other than the CyberSprite Op registry.

Usage (from anywhere):
  python assets/ui/icons/tools/build_icons.py [--renders DIR] [--only name,name] [--jobs N]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ICONS = HERE.parent
REPO = ICONS.parents[2]
sys.path.insert(0, str(HERE))
import icon_grids  # noqa: E402

PALETTE = ICONS / "ui-icons.gpl"
LAYER = "icon"
PALETTE_NAMES = ["transparent", "ink", "trace-deep", "trace", "trace-soft", "white",
                 "warn", "error", "agent", "ink-soft", "agent-soft"]
# design character -> palette index character used by draw_rows format "sym"
SYM = {".": ".", "#": "1", "d": "2", "c": "3", "s": "4", "w": "5",
       "g": "6", "r": "7", "v": "8", "k": "9", "p": "a"}


def csp(*args: str, stdin: str | None = None) -> dict:
    cmd = ["uv", "run", "--project", str(REPO), "--no-sync", "cybersprite", "--quiet", *args]
    p = subprocess.run(cmd, input=stdin, capture_output=True, text=True, encoding="utf-8")
    try:
        out = json.loads(p.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"{' '.join(args)} -> exit {p.returncode}\n{p.stdout}\n{p.stderr}")
    out["_exit"] = p.returncode
    return out


def build_one(name: str, rows: list[str], renders: Path | None) -> dict:
    proj = ICONS / f"{name}.csprite"
    log = {"name": name, "created": False, "drawn": False}
    if not proj.exists():
        r = csp("new", str(proj), "--size", "16x16", "--palette", str(PALETTE),
                "--name", name, "--layer-name", LAYER)
        if not r["ok"]:
            raise RuntimeError(f"new {name}: {r}")
        log["created"] = True
    # `new --palette x.gpl` keeps the colours but drops the .gpl colour names, so name them
    pal = csp("-p", str(proj), "palette", "show")["result"]["colors"]
    if [c["name"] for c in pal] != PALETTE_NAMES:
        tx = {"label": "name ui palette",
              "ops": [{"op": "set_palette", "args": {
                  "colors": [c["color"][:7] for c in pal],
                  "names": {str(i): n for i, n in enumerate(PALETTE_NAMES)}}}]}
        r = csp("-p", str(proj), "apply", "-", "--preview", "none", stdin=json.dumps(tx))
        if not r["ok"]:
            raise RuntimeError(f"name palette {name}: {r}")
    want = ["".join(SYM[c] for c in row) for row in rows]
    cur = csp("-p", str(proj), "pixels", "--layer", LAYER, "--frame", "0",
              "--rect", "0,0,16,16", "--as", "sym")
    have = cur["result"]["rows"] if cur["ok"] else None
    if have != want:
        tx = {"label": f"draw icon {name}",
              "ops": [{"op": "draw_rows", "args": {"layer": LAYER, "frame": 0, "x": 0, "y": 0,
                                                   "format": "sym", "rows": want}}]}
        r = csp("-p", str(proj), "apply", "-", "--preview", "none", stdin=json.dumps(tx))
        if not r["ok"]:
            raise RuntimeError(f"apply {name}: {r}")
        log["drawn"] = True
        log["delta"] = {k: r["validation"].get(k) for k in ("ok", "errors", "warnings")}
        log["new_issues"] = [i["rule"] for i in r["validation"].get("new_issues", [])]
    v = csp("-p", str(proj), "validate")
    res = v["result"]
    log["validate_ok"] = res["ok"]
    log["counts"] = res["counts"]
    log["issues"] = [(i["rule"], i["level"], i["message"]) for i in res["issues"]
                     if i["level"] != "info" or i["rule"] != "Q-PAL-02"]
    if renders:
        for scale in (1, 4):
            d = renders / f"x{scale}"
            d.mkdir(parents=True, exist_ok=True)
            r = csp("-p", str(proj), "render", "--frame", "0", "--scale", str(scale),
                    "--out", str(d / f"{name}.png"))
            if not r["ok"]:
                raise RuntimeError(f"render {name}: {r}")
    return log


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--renders", type=Path)
    ap.add_argument("--only")
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()
    icons = icon_grids.all_icons()
    if a.only:
        keep = set(a.only.split(","))
        icons = {k: v for k, v in icons.items() if k in keep}
    with ThreadPoolExecutor(a.jobs) as ex:
        logs = list(ex.map(lambda kv: build_one(kv[0], kv[1], a.renders), icons.items()))
    for lg in logs:
        print(json.dumps(lg, ensure_ascii=False))
    return 0 if all(lg["validate_ok"] for lg in logs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
