"""Real-path confinement driven by JSON Schema field metadata."""

import os
from pathlib import Path

from cybersprite.core.errors import CyberSpriteError
from cybersprite.formats.palette_files import presets


class PathPolicy:
    def __init__(self, root, allow_dir=()):
        self.root = Path(root).resolve()
        self.allowed = (self.root, *((self.root / Path(p)).resolve() for p in allow_dir))

    def resolve(self, value):
        path = Path(value)
        try:
            path = (path if path.is_absolute() else self.root / path).resolve()
            candidate = os.path.normcase(str(path))
            for parent in self.allowed:
                base = os.path.normcase(str(parent))
                try:
                    if os.path.commonpath([candidate, base]) == base:
                        return path
                except ValueError:  # Distinct Windows volumes cannot share a parent.
                    continue
        except (OSError, ValueError, RuntimeError):
            pass
        raise CyberSpriteError(
            "E_PATH_NOT_ALLOWED",
            "Path resolves outside the allowed directories.",
            "Use a path under root or restart the server with an explicit allow-dir.",
            {"allowed_dirs": [p.as_posix() for p in self.allowed]},
        )

    def relative(self, path):
        try:
            return Path(os.path.relpath(self.resolve(path), self.root)).as_posix()
        except ValueError as error:
            raise CyberSpriteError(
                "E_PATH_NOT_ALLOWED",
                "Path cannot be represented relative to root across volumes.",
                "Restart the server with root on the same volume as the requested path.",
            ) from error

    def check_project(self, project, check=lambda: None):
        """Check derived history/source paths too, without following directory links."""
        root = project.parent if project.name == "project.json" else project
        self.resolve(root / "project.json")
        if root.is_dir():
            for folder, dirs, files in os.walk(root, followlinks=False):
                check()
                for name in sorted(dirs + files):
                    check()
                    self.resolve(Path(folder) / name)

    def arguments(self, value, schema, definitions=None):
        definitions = definitions or schema.get("$defs", {})
        if "$ref" in schema:
            return self.arguments(value, definitions[schema["$ref"].split("/")[-1]], definitions)
        if isinstance(value, dict) and "all" in schema.get("discriminator", {}).get("mapping", {}):
            # Bound region trees before jsonschema recursively checks union variants.
            from cybersprite.core.raster import RasterError, check_region_tree

            try:
                check_region_tree(value)
            except RasterError as error:
                raise CyberSpriteError(error.code, error.message, error.hint) from error
        kind = schema.get("x-cybersprite-path")
        if kind and isinstance(value, str):
            if kind == "palette" and value in {p["name"] for p in presets()}:
                return value
            return str(self.resolve(value))
        variants = schema.get("anyOf", schema.get("oneOf", []))
        if variants:
            from jsonschema import Draft202012Validator

            for variant in variants:
                if Draft202012Validator({**variant, "$defs": definitions}).is_valid(value):
                    return self.arguments(
                        value,
                        {
                            **{k: v for k, v in schema.items() if k not in {"anyOf", "oneOf"}},
                            **variant,
                        },
                        definitions,
                    )
            return value  # The Op's parser will report malformed arguments.
        if isinstance(value, dict):
            properties = schema.get("properties", {})
            return {
                k: self.arguments(v, properties.get(k, {}), definitions) for k, v in value.items()
            }
        if isinstance(value, list) and "items" in schema:
            items = schema["items"]
            if kind and kind != "palette":
                items = {**items, "x-cybersprite-path": kind}
            return [self.arguments(v, items, definitions) for v in value]
        return value

    def result(self, value, project_root, *, key=""):
        """Core preview paths are project-relative; other returned paths are absolute."""
        if isinstance(value, dict):
            return {k: self.result(v, project_root, key=k) for k, v in value.items()}
        if isinstance(value, list):
            return [self.result(v, project_root, key=key) for v in value]
        if isinstance(value, str):
            if key in {
                "project",
                "allowed_dirs",
                "paths",
                "path",
                "report_path",
                "stage_paths",
                "files",
                "file",
                "out",
                "data_out",
            }:
                if Path(value).is_absolute():
                    return self.relative(value)
                if key == "project":
                    return value
                return self.relative(project_root / value)
        return value
