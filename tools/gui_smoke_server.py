"""Isolated Playwright fixture server; never used by the production CLI."""

import json
import tempfile
from pathlib import Path

import uvicorn

from cybersprite import ops
from cybersprite.server.app import create_app

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / ".gui-check"
    folder.mkdir(exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="smoke-", dir=folder)) / "test.csprite"
    ops.execute("new_project", project, {"width": 16, "height": 16}, actor="test")
    (folder / "session.json").write_text(
        json.dumps({"project": project.as_posix()}), encoding="utf-8", newline="\n"
    )
    app = create_app(
        root=ROOT,
        project=project,
        token="playwright-fixture-token",
        origin="http://127.0.0.1:8766",
    )
    uvicorn.run(app, host="127.0.0.1", port=8766, access_log=False)


if __name__ == "__main__":
    main()
