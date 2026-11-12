"""Run the R1 export and import-dry-run review reproductions on isolated projects."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from click.testing import CliRunner

from cybersprite import ops
from cybersprite.cli import cli
from cybersprite.core.errors import CyberSpriteError
from cybersprite.formats.png import decode_png, encode_png
from cybersprite.mcp.server import MCPService
from cybersprite.server.app import Service


def saved_bytes(project):
    return {
        path.relative_to(project).as_posix(): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }


def main():
    output = Path("build/r1-a1-review")
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    with TemporaryDirectory(dir=Path.cwd()) as directory:
        root = Path(directory).resolve()
        for surface in ("cli", "mcp", "gui-template"):
            project = root / surface
            ops.execute("new_project", project, {"width": 2, "height": 2, "name": "project"})
            before = saved_bytes(project)
            if surface == "cli":
                response = CliRunner().invoke(
                    cli,
                    ["-p", str(project), "export", "image", "--out", str(project / "project.json")],
                )
                assert response.exit_code != 0
                code = json.loads(response.output)["error"]["code"]
            elif surface == "mcp":
                response = (
                    MCPService(root=root)
                    .call(
                        "export_image",
                        {"project": str(project), "out": str(project / "project.json")},
                    )
                    .structured_content
                )
                assert not response["ok"]
                code = response["error"]["code"]
            else:
                try:
                    Service(root).run_op(
                        "export_image", project, {"out": str(project / "{name}.json")}
                    )
                except CyberSpriteError as error:
                    code = error.code
                else:
                    raise AssertionError("GUI template export must be rejected.")
            assert code == "E_PATH_NOT_ALLOWED" and before == saved_bytes(project)
            checks.append(
                {
                    "surface": surface,
                    "error": code,
                    "first_bytes_hex": (project / "project.json").read_bytes()[:8].hex(),
                    "canonical_and_history_unchanged": True,
                }
            )
        image = root / "input.png"
        image.write_bytes(encode_png(np.full((2, 2, 4), 255, dtype=np.uint8)))
        ops.execute("update_layer", project, {"layer": "L1", "locked": True}, preview="none")
        args = {
            "files": str(image),
            "preset": "exact",
            "provenance": {"license": "unknown"},
            "target": {"mode": "layer", "layer": "L1"},
        }
        for dry in (True, False):
            try:
                ops.execute("import_image", project, args, dry_run=dry, preview="none")
            except CyberSpriteError as error:
                assert error.code == "E_LAYER_LOCKED"
                checks.append({"import_dry_run": dry, "error": error.code})
            else:
                raise AssertionError("Locked placement must be rejected.")
    with TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        assert not root.is_relative_to(Path.cwd())
        project = root / "sprite"
        ops.execute("new_project", project, {"width": 2, "height": 2})
        result = Service(root).run_op("export_image", project, {"out": str(root / "ok.png")})
        assert result["result"]["verified"]
        actual = (root / "ok.png").read_bytes()
        assert decode_png(actual).pixels.shape == (2, 2)
        (output / "gui-outside-cwd.png").write_bytes(actual)
        checks.append(
            {
                "gui_root_outside_cwd": True,
                "validation_ok": result["result"]["validation_ok"],
                "verified": True,
            }
        )
    report = json.dumps(checks, indent=2, ensure_ascii=False) + "\n"
    (output / "acceptance.json").write_text(report, encoding="utf-8", newline="\n")
    print(report, end="")


if __name__ == "__main__":
    main()
