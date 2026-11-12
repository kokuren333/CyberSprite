"""Stable reference resolution and cel ownership helpers."""

from collections.abc import Iterator
from typing import Any

from .errors import CyberSpriteError
from .models import GroupLayer, Layer, LinkCel, Project, Tag


def walk_layers(
    layers: list[Layer], ancestors: tuple[GroupLayer, ...] = ()
) -> Iterator[tuple[Layer, tuple[GroupLayer, ...]]]:
    for layer in layers:
        yield layer, ancestors
        if isinstance(layer, GroupLayer):
            yield from walk_layers(layer.children, (*ancestors, layer))


def resolve_layer(project: Project, reference: str) -> Layer:
    entries = [
        (layer, "/".join(a.name for a in (*ancestors, layer)))
        for layer, ancestors in walk_layers(project.layers)
    ]
    for layer, _path in entries:
        if layer.id == reference:
            return layer
    for by_path in (False, True):
        matches = [
            (layer, path)
            for layer, path in entries
            if (path if by_path else layer.name) == reference
        ]
        if len(matches) == 1:
            return matches[0][0]
        if matches:
            raise CyberSpriteError(
                "E_AMBIGUOUS_REF",
                f"Layer reference {reference!r} matches multiple layers.",
                "Specify a layer ID from candidates.",
                {
                    "reference": reference,
                    "candidates": [{"id": layer.id, "path": path} for layer, path in matches],
                },
            )
    raise CyberSpriteError(
        "E_LAYER_NOT_FOUND",
        f"Layer {reference!r} was not found.",
        "Use get_info to list layer IDs and retry with an exact ID.",
        {
            "reference": reference,
            "candidates": [{"id": layer.id, "path": path} for layer, path in entries],
        },
    )


def resolve_tag(project: Project, reference: str) -> Tag:
    for tag in project.tags:
        if tag.id == reference:
            return tag
    matches = [tag for tag in project.tags if tag.name == reference]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise CyberSpriteError(
            "E_AMBIGUOUS_REF",
            f"Tag {reference!r} matches multiple tags.",
            "Specify an exact tag ID.",
            {"candidates": [{"id": t.id, "name": t.name} for t in matches]},
        )
    raise CyberSpriteError(
        "E_TAG_NOT_FOUND",
        f"Tag {reference!r} was not found.",
        "Use get_info to list tag IDs.",
        {"reference": reference, "candidates": [t.id for t in project.tags]},
    )


def cel_at(layer: Any, frame: int) -> Any:
    return next((cel for cel in layer.cels if cel.frame == frame), None)


def cel_owner(layer: Any, cel: Any) -> Any:
    if isinstance(cel, LinkCel):
        return cel_at(layer, cel.link)
    return cel
