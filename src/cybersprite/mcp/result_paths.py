"""File-path annotations for untyped sections of shared response contracts."""

from copy import deepcopy

from cybersprite.core.models import Sources

PATH = {"type": "string", "format": "path"}
PATHS = {"type": "array", "items": PATH}
PROJECT_PATH = {**PATH, "x-cybersprite-base": "root"}


def response_schema(op):
    """Use typed result metadata, adding paths only at documented response locations."""
    result = deepcopy(op.result.model_json_schema(by_alias=True))
    definitions = result.pop("$defs", {})
    properties = result.setdefault("properties", {})
    if op.name in {"render_preview", "diff_preview"}:
        properties["paths"] = PATHS
    if op.name == "import_image":
        properties.update(report_path=PATH, stage_paths=PATHS)
    if op.name in {"generate_image", "add_source"}:
        properties["files"] = PATHS
    if op.name == "get_info":
        sources = Sources.model_json_schema(by_alias=True)
        definitions.update(sources.pop("$defs", {}))
        properties["sources"] = sources
    if "SourceFile" in definitions:
        definitions["SourceFile"]["properties"]["path"] = PATH
    if "SourcePipeline" in definitions:
        definitions["SourcePipeline"]["properties"]["report"] = {
            "type": "object",
            "properties": {"path": PATH},
        }
    preview = {"type": "object", "properties": {"paths": PATHS}}
    return {
        "type": "object",
        "properties": {"project": PROJECT_PATH, "result": result, "preview": preview},
        "$defs": definitions,
    }


def error_schema(code):
    """Layer-reference `path` candidates are deliberately absent from this schema."""
    details = {}
    if code in {"E_IO", "E_PATH_NOT_ALLOWED", "E_EXISTS"}:
        details = {"path": PATH, "project": PATH, "allowed": PATHS, "allowed_dirs": PATHS}
    return {
        "properties": {
            "project": PROJECT_PATH,
            "error": {"properties": {"details": {"properties": details}}},
        }
    }
