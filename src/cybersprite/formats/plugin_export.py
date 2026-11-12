"""Single-file plugin exports with shared preflight and independent disk verification."""

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from pydantic import BaseModel, ValidationError

from cybersprite.core.errors import invalid
from cybersprite.core.render import render
from cybersprite.plugins import PluginManager, plugin_error

from .common import display_path, gate, preflight
from .export_args import ExportResult


def resolve_exporter(name=None, *, extension=None, manager=None):
    if name == "gb-2bpp":
        from .native import GBExporter

        return GBExporter()
    manager = manager or PluginManager(groups=("cybersprite.exporters",))
    if name is None:
        # Extension lookup is explicit use of the enabled exporter group.
        found = []
        for d in manager.descriptors("cybersprite.exporters"):
            exporter = resolve_exporter(d.name, manager=manager)
            if exporter.extension.lower().lstrip(".") == extension.lower().lstrip("."):
                found.append(exporter)
        if len(found) != 1:
            raise invalid(
                "Exporter extension is missing or ambiguous; specify format.", extension=extension
            )
        return found[0]
    try:
        exporter = manager.load("cybersprite.exporters", name)
        if exporter.name != name or not exporter.extension or not callable(exporter.write):
            raise ValueError("exporter requires matching name, extension and callable write")
        if not isinstance(exporter.options_model, type) or not issubclass(
            exporter.options_model, BaseModel
        ):
            raise ValueError("options_model must be a pydantic model class")
        return exporter
    except Exception as error:
        manager.discard("cybersprite.exporters", name)
        raise plugin_error(name, f"exporter registration failed: {error}") from error


def export_plugin(document, args, root=None):
    result = gate(document, args, root)
    path = preflight([args.out], args.overwrite, project_root=root)[0]
    if root is not None:
        canonical = Path(root).resolve() / "project.json"
        if path == canonical or path.exists() and canonical.exists() and path.samefile(canonical):
            raise invalid("Plugin export cannot replace project.json; choose another output path.")
    exporter = resolve_exporter(args.format, extension=path.suffix)
    try:
        options = exporter.options_model.model_validate(args.options)
    except ValidationError as error:
        raise invalid(
            "Invalid plugin exporter options.", format=exporter.name, reason=str(error)
        ) from error
    prepare = getattr(exporter, "verification_frames", None)
    if callable(prepare):
        if not callable(getattr(exporter, "decode", None)):
            raise plugin_error(exporter.name, "verification_frames requires decode(bytes).")
        expected = prepare(document.model_copy(deep=True), render, options)
    else:
        expected = [render(document, f) for f in range(len(document.frames))]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # A failed writer/decoder cannot replace a previous successful export.
        with TemporaryDirectory(prefix=".cybersprite-export-", dir=path.parent) as directory:
            staged = Path(directory) / path.name
            written = ExportResult.model_validate(
                exporter.write(document.model_copy(deep=True), render, staged, options)
            )
            result["warnings"].extend(written.warnings)
            data = staged.read_bytes()
            decode = getattr(exporter, "decode", None)
            result["verified"] = False
            if callable(decode):
                actual = decode(data)
                if isinstance(actual, np.ndarray):
                    actual = [actual]
                if len(actual) != len(expected) or any(
                    not isinstance(a, np.ndarray) or a.dtype != np.uint8 or not np.array_equal(a, b)
                    for a, b in zip(actual, expected, strict=True)
                ):
                    raise ValueError("decoded export differs from the core renderer")
                result["verified"] = True
            else:
                result["verification_reason"] = "Plugin exporter does not provide decode(bytes)."
            staged.replace(path)
            # Hash the actual destination bytes, after the final replacement.
            actual_bytes = path.read_bytes()
            if actual_bytes != data:
                path.unlink(missing_ok=True)
                raise ValueError("destination bytes changed after replacement")
    except Exception as error:
        raise plugin_error(
            exporter.name, f"export failed: {error}", path=display_path(path)
        ) from error
    result["files"] = [
        dict(
            kind="data",
            path=display_path(path),
            bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )
    ]
    return result
