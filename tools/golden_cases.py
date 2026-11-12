"""Shared golden execution without any expectation-writing side effects."""

import json
from pathlib import Path

from cybersprite.core.canonical import dumps_project, json_bytes, load_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.hashing import pixel_sha256
from cybersprite.core.normalize import normalize_cels
from cybersprite.core.render import indexed_result, render_result
from cybersprite.formats.png import encode_png


def execute_case(directory: Path) -> dict[str, bytes]:
    project = load_project(directory / "project.json")
    case = json.loads((directory / "case.json").read_bytes())
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
