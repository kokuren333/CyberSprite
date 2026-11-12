"""Shared golden execution without any expectation-writing side effects."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from cybersprite.core.canonical import dumps_project, json_bytes, load_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.hashing import pixel_sha256
from cybersprite.core.normalize import normalize_cels
from cybersprite.core.render import indexed_result, render_result
from cybersprite.formats.png import encode_png


def execute_case(directory: Path) -> dict[str, bytes]:
    case = json.loads((directory / "case.json").read_bytes())
    if "new_project" in case:
        from cybersprite.ops import registry
        from cybersprite.ops.queries import construct

        with (
            tempfile.TemporaryDirectory() as settings,
            patch.dict(os.environ, {"CYBERSPRITE_CONFIG_DIR": settings}),
            patch("cybersprite.platforms.plugin_definitions", return_value={}),
        ):
            project = construct(
                registry().get("new_project").parse(case["new_project"]), Path("golden.csprite")
            )
    else:
        project = load_project(directory / "project.json")
    output = {}
    if case.get("canonical"):
        output["canonical.project.json"] = dumps_project(project)
    if case.get("normalize"):
        project = normalize_cels(project)
        output["normalized.project.json"] = dumps_project(project)
    if "issue_ids" in case:
        ids = [project.id_counters.issue(kind) for kind in case["issue_ids"]]
        output["ids.json"] = json_bytes(ids)
        output["after.project.json"] = dumps_project(project)
    if case.get("raster_vectors"):
        import hashlib

        if __package__:
            from tools.gen_raster_vectors import build_vectors
        else:
            from gen_raster_vectors import build_vectors

        output["raster.vectors.sha256.json"] = json_bytes(
            {
                name: hashlib.sha256(data).hexdigest()
                for name, data in sorted(build_vectors().items())
            }
        )
    if "transactions" in case:
        from cybersprite.ops import execute

        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.dict(
                os.environ,
                {"CYBERSPRITE_NOW": "2026-11-12T00:00:00Z", "CYBERSPRITE_ACTOR": "agent:golden"},
            ),
        ):
            root = Path(temporary) / "golden.csprite"
            root.mkdir()
            (root / "project.json").write_bytes(dumps_project(project))
            for index, action in enumerate(case["transactions"]):
                try:
                    envelope = execute(
                        action["op"],
                        root,
                        action.get("args", {}),
                        preview="none",
                        **action.get("options", {}),
                    )
                    envelope["project"] = "golden.csprite"
                    output[f"tx{index}.json"] = json_bytes(envelope)
                except CyberSpriteError as error:
                    if error.code != action.get("error"):
                        raise
                    output[f"tx{index}.error.json"] = json_bytes(
                        {
                            **error.as_dict(),
                            **({"op_index": error.op_index} if hasattr(error, "op_index") else {}),
                        }
                    )
                else:
                    if "error" in action:
                        raise AssertionError(f"Expected {action['error']}")
                output[f"tx{index}.project.json"] = (root / "project.json").read_bytes()
            project = load_project(root)
            output["after.project.json"] = dumps_project(project)
    if "exports" in case:
        from cybersprite.formats.common import export_policy
        from cybersprite.formats.export import EXPORTERS
        from cybersprite.formats.export_args import EXPORT_ARGS
        from cybersprite.formats.png import decode_png

        with tempfile.TemporaryDirectory() as temporary, export_policy(temporary):
            for action in case["exports"]:
                name = action["op"]
                args = EXPORT_ARGS[name].model_validate(action["args"])
                result = EXPORTERS[name](project, args)
                for entry in result["files"]:
                    path = Path(temporary) / entry["path"]
                    if action.get("pixel_only"):
                        decoded = decode_png(path.read_bytes())
                        output[path.name + ".pixhash"] = (
                            pixel_sha256(decoded.pixels) + "\n"
                        ).encode()
                    else:
                        output[path.name] = path.read_bytes()
                output[action["name"] + ".result.json"] = json_bytes(
                    {
                        key: value
                        for key, value in result.items()
                        if key != "fingerprint" and (key != "files" or not action.get("pixel_only"))
                    }
                )
    for i, action in enumerate(case.get("renders", [])):
        name = action.get("name", f"f{i}")
        try:
            render_fn = indexed_result if action.get("indexed") else render_result
            result = render_fn(project, action.get("frame", 0), action.get("options"))
            output[f"{name}.pixhash"] = (pixel_sha256(result.pixels) + "\n").encode()
            output[f"{name}.stored.png"] = encode_png(
                result.pixels, result.palette, compression="stored"
            )
            output[f"{name}.pixels.json"] = json_bytes(result.pixels.tolist())
            output[f"{name}.warnings.json"] = json_bytes(result.warnings)
        except CyberSpriteError as error:
            if error.code != action.get("error"):
                raise
            output[f"{name}.error.json"] = json_bytes(error.as_dict())
        else:
            if "error" in action:
                raise AssertionError(f"{directory.name}/{name} expected {action['error']}")
    return output
