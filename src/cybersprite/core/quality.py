"""Deterministic quality rules and full-recomputation validation deltas."""

from collections import Counter, OrderedDict, deque
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np

from .errors import CyberSpriteError
from .models import GroupLayer, ImageLayer, LinkCel, Sources
from .pixels import rgba, tiles_from_rows
from .references import cel_owner, walk_layers
from .render import frame_signature, indexed_result, render
from .validation import check_structure

DEFAULT_LEVELS = {
    "Q-PAL-01": "error",
    "Q-PAL-02": "info",
    "Q-PAL-03": "info",
    "Q-PAL-04": "warning",
    "Q-PAL-05": "warning",
    "Q-PIX-01": "warning",
    "Q-PIX-02": "info",
    "Q-PIX-03": "warning",
    "Q-LYR-01": "warning",
    "Q-LYR-02": "warning",
    "Q-LYR-03": "info",
    "Q-ANI-01": "warning",
    "Q-ANI-02": "off",
    "Q-ANI-03": "info",
    "Q-ANI-04": "off",
    "Q-ANI-05": "info",
    "Q-TIL-01": "info",
    "Q-TIL-02": "warning",
    "Q-SLC-01": "warning",
    "Q-SRC-01": "warning",
    "Q-SRC-02": "warning",
    "Q-SRC-03": "error",
}

# Derived data only: at most 64 frames / 262144 pixels (including component points).
_FRAME_CACHE: OrderedDict[bytes, Any] = OrderedDict()
_FRAME_CACHE_LOCK = Lock()
_FRAME_CACHE_PIXELS = 262144


@lru_cache(maxsize=256)
def _pixel_counts(rows):
    return tuple(sorted(Counter(bytes.fromhex("".join(rows))).items()))


def _usage(rows, use_cache):
    rows = tuple(rows)
    counts = (
        _pixel_counts if use_cache and sum(map(len, rows)) <= 65536 else _pixel_counts.__wrapped__
    )
    return dict(counts(rows))


def _frame_analysis(p, f, signature, use_cache):
    # Includes all visible leaf contributions, ancestors' effective opacities, order,
    # z-index, bounds, palette/transparent index, and full referenced tilesets.
    key = sha256(repr(signature).encode("utf-8")).digest()
    if use_cache:
        with _FRAME_CACHE_LOCK:
            if key in _FRAME_CACHE:
                value = _FRAME_CACHE.pop(key)
                _FRAME_CACHE[key] = value
                return value
    closed = True
    try:
        indexed = indexed_result(p, f)
    except CyberSpriteError as error:
        if error.code != "E_NOT_PALETTE_CLOSED":
            raise
        indexed = indexed_result(p, f, {"flatten": "nearest"})
        closed = False
    rgba_image = render(p, f)
    transparent = p.palette.transparent_index
    assert indexed.palette is not None
    if rgba(indexed.palette[transparent])[3] != 0:
        transparent = -1
    components = tuple(
        tuple(tuple(pt) for pt in part) for part in clusters(indexed.pixels, transparent)
    )
    indexed.pixels.flags.writeable = False
    rgba_image.flags.writeable = False
    value = indexed, rgba_image, components, closed
    area = p.canvas.width * p.canvas.height
    if use_cache and area <= _FRAME_CACHE_PIXELS:
        with _FRAME_CACHE_LOCK:
            _FRAME_CACHE[key] = value
            while (
                len(_FRAME_CACHE) > 64
                or sum(item[1].shape[0] * item[1].shape[1] for item in _FRAME_CACHE.values())
                > _FRAME_CACHE_PIXELS
            ):
                _FRAME_CACHE.popitem(last=False)
    return value


def cached_frame_rgba(project, frame, signature=None):
    """Reuse a validated frame's immutable RGBA; callers must not mutate the result."""
    if type(frame) is not int or not 0 <= frame < len(project.frames):
        return None
    if signature is None:
        signature = frame_signature(project, frame)
    key = sha256(repr(signature).encode("utf-8")).digest()
    with _FRAME_CACHE_LOCK:
        value = _FRAME_CACHE.get(key)
        return value[1] if value is not None else None


def bbox(mask):
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return {
        "x": int(xs.min()),
        "y": int(ys.min()),
        "w": int(xs.max() - xs.min() + 1),
        "h": int(ys.max() - ys.min() + 1),
    }


def clusters(image, ti):
    # Python integers/bytearrays avoid a NumPy scalar operation per neighbour.
    # Keep the original row seed order and breadth-first neighbour order.
    values = image.tolist()
    h, w = image.shape
    seen = [bytearray(w) for _ in range(h)]
    result = []
    for y in range(h):
        for x in range(w):
            if seen[y][x] or values[y][x] == ti:
                continue
            value = values[y][x]
            seen[y][x] = 1
            queue = deque([(x, y)])
            points = []
            while queue:
                px, py = queue.popleft()
                points.append([px, py])
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        nx, ny = px + dx, py + dy
                        if (
                            0 <= nx < w
                            and 0 <= ny < h
                            and not seen[ny][nx]
                            and values[ny][nx] == value
                        ):
                            seen[ny][nx] = 1
                            queue.append((nx, ny))
            result.append(points)
    return result


def report(
    p,
    *,
    root=None,
    selected_frames=None,
    rules=None,
    source_manifest=None,
    use_cache=True,
    _structural=None,
):
    structural = check_structure(p) if _structural is None else _structural
    issues = [issue.as_dict() for issue in structural]
    settings = p.validation

    def add(rule, message, *, fs=None, layer=None, box=None, points=None, level=None):
        severity = settings.severity.get(rule, level or DEFAULT_LEVELS[rule])
        if severity == "off":
            return
        issues.append(
            {
                "rule": rule,
                "level": severity,
                "message": message,
                "where": {
                    "frames": fs or [],
                    "layer": layer,
                    "bbox": box,
                    "points": [list(pt) for pt in (points or [])[:64]],
                },
            }
        )

    if structural:
        return {
            "ok": False,
            "revision": p.revision,
            "counts": {"error": len(structural), "warning": 0, "info": 0},
            "issues": issues,
            "metrics": {},
            "settings": settings.model_dump(),
            "scope": "full",
        }
    nodes = list(walk_layers(p.layers))
    cels = [c for node, _ in nodes if not isinstance(node, GroupLayer) for c in node.cels]
    usage: Counter[int] = Counter()
    tile_usage: dict[str, Counter[int]] = {ts.id: Counter() for ts in p.tilesets}
    for node, _ in nodes:
        if node.blend_mode != "normal":
            add("Q-LYR-02", "Non-normal blend mode is rendered as normal in v1.", layer=node.id)
        if isinstance(node, GroupLayer):
            continue
        if not node.cels:
            add("Q-LYR-03", "Layer has no cels.", layer=node.id)
        previous = None
        previous_owner = None
        previous_frame = -2
        for cel in node.cels:
            owner = cel_owner(node, cel)
            if isinstance(node, ImageLayer):
                usage.update(_usage(owner.pixels, use_cache))
                w, h = owner.w, owner.h
            else:
                ts = next(ts for ts in p.tilesets if ts.id == node.tileset)
                w, h = owner.w * ts.tile_w, owner.h * ts.tile_h
                diagonal: list[list[int]] = []
                for row_index, row in enumerate(tiles_from_rows(owner.tiles, owner.w, owner.h)):
                    for col_index, ref in enumerate(row):
                        tile_usage[ts.id][ref.index] += 1
                        if ref.d and ts.tile_w != ts.tile_h:
                            if len(diagonal) < 64:
                                diagonal.append(
                                    [
                                        owner.x + col_index * ts.tile_w,
                                        owner.y + row_index * ts.tile_h,
                                    ]
                                )
                if diagonal:
                    add(
                        "Q-TIL-02",
                        "Non-square tiles have diagonal flags; transpose is ignored.",
                        fs=[cel.frame],
                        layer=node.id,
                        points=diagonal,
                    )
            outside = (
                owner.x < 0
                or owner.y < 0
                or owner.x + w > p.canvas.width
                or owner.y + h > p.canvas.height
            )
            fully = (
                owner.x + w <= 0
                or owner.y + h <= 0
                or owner.x >= p.canvas.width
                or owner.y >= p.canvas.height
            )
            if outside:
                add(
                    "Q-PIX-03",
                    "Cel is outside the canvas." if fully else "Cel extends beyond the canvas.",
                    fs=[cel.frame],
                    layer=node.id,
                    box={"x": owner.x, "y": owner.y, "w": w, "h": h},
                    level="warning" if fully else "info",
                )
            value = owner.model_dump(exclude={"frame", "z_index"})
            if (
                previous_frame + 1 == cel.frame
                and previous == value
                and previous_owner != owner.frame
            ):
                add(
                    "Q-ANI-05",
                    "Consecutive equal cels can share a link.",
                    fs=[cel.frame - 1, cel.frame],
                    layer=node.id,
                )
            previous, previous_owner, previous_frame = value, owner.frame, cel.frame
    tile_findings = []
    for ts in p.tilesets:
        seen: dict[bytes, int] = {}
        duplicates: list[list[int]] = []
        for index, tile in enumerate(ts.tiles):
            value = bytes.fromhex("".join(tile.pixels))
            if value in seen:
                duplicates.append([seen[value], index])
            else:
                seen[value] = index
        unused = [i for i in range(1, len(ts.tiles)) if not tile_usage[ts.id][i]]
        if duplicates or unused:
            tile_findings.append(f"{ts.id}: unused {unused}; duplicate pairs {duplicates}")
        for tile in ts.tiles[1:]:
            usage.update(_usage(tile.pixels, use_cache))
    if tile_findings:
        add("Q-TIL-01", "Tileset findings: " + "; ".join(tile_findings) + ".")
    if len(p.palette.colors) > settings.palette_max:
        add("Q-PAL-01", "Palette exceeds the configured color budget.")
    unused = [i for i in range(len(p.palette.colors)) if not usage[i]]
    if unused:
        add("Q-PAL-02", f"Unused palette indices: {unused}.")
    if len(set(c.lower() for c in p.palette.colors)) < len(p.palette.colors):
        add("Q-PAL-03", "Palette contains duplicate colors.")
    if any(usage[i] and 0 < rgba(c)[3] < 255 for i, c in enumerate(p.palette.colors)):
        add("Q-PAL-04", "Used palette entries contain partial alpha.")
    colors_per_frame, orphans, opaque_counts, boxes = [], [], [], []
    small_total, nonclosed = 0, 0
    previous_signature = None
    cached = None
    for f in range(len(p.frames)):
        signature = frame_signature(p, f)
        if not use_cache or signature != previous_signature or cached is None:
            cached = _frame_analysis(p, f, signature, use_cache)
            previous_signature = signature
        indexed, rgba_image, components, closed = cached
        if not closed:
            nonclosed += 1
            add("Q-LYR-01", "Frame is not palette closed.", fs=[f])
        image = indexed.pixels
        color_count = len(np.unique(image))
        colors_per_frame.append(color_count)
        if (
            settings.colors_per_frame_max is not None
            and color_count > settings.colors_per_frame_max
        ):
            add("Q-PAL-05", "Frame exceeds the configured color count.", fs=[f])
        # Cluster metrics require an indexed frame; nearest is the explicit diagnostic fallback.
        orphan_points = [part[0] for part in components if len(part) == 1]
        small = [part for part in components if len(part) < settings.min_cluster]
        orphans.append(len(orphan_points))
        small_total += len(small)

        def pixel_layer(points, frame=f):
            # Composite clusters can span several layers or blended contributions.
            # Attribute only when all reported pixels have one unambiguous contributor.
            contributors = []
            for node, _ in nodes:
                if isinstance(node, GroupLayer):
                    continue
                pixels = render(p, frame, {"layers": [node.id]})
                if any(pixels[y, x, 3] for x, y in points):
                    contributors.append(node.id)
            return contributors[0] if len(contributors) == 1 else None

        if (
            settings.orphan_pixels_max is not None
            and len(orphan_points) > settings.orphan_pixels_max
        ):
            add(
                "Q-PIX-01",
                "Frame exceeds the orphan pixel budget.",
                fs=[f],
                layer=pixel_layer(orphan_points),
                points=orphan_points,
            )
        if small:
            small_points = [pt for part in small for pt in part]
            add(
                "Q-PIX-02",
                "Frame has clusters below min_cluster.",
                fs=[f],
                layer=pixel_layer(small_points),
                points=small_points,
            )
        opaque = rgba_image[:, :, 3] != 0
        opaque_counts.append(int(np.count_nonzero(opaque)))
        boxes.append(bbox(opaque))
        if p.frames[f].duration_ms % 10:
            add("Q-ANI-03", "Frame duration is not a multiple of 10 ms.", fs=[f])
    names = Counter(tag.name for tag in p.tags)
    for name in sorted(names):
        if names[name] > 1:
            add("Q-ANI-01", f"Tag name {name!r} is duplicated.")
    if p.tags:
        missing = [f for f in range(len(p.frames)) if not any(t.from_ <= f <= t.to for t in p.tags)]
        if missing:
            add(
                "Q-ANI-02",
                "Some frames are outside every tag.",
                fs=missing,
                level="warning" if settings.require_tag_coverage else "off",
            )
    if settings.silhouette_jitter_max is not None:
        for tag in p.tags:
            for f in range(tag.from_ + 1, tag.to + 1):
                before, after = boxes[f - 1], boxes[f]
                delta = (
                    max(abs(before[k] - after[k]) for k in ("x", "y", "w", "h"))
                    if before and after
                    else (max(p.canvas.width, p.canvas.height) if before != after else 0)
                )
                if delta > settings.silhouette_jitter_max:
                    add(
                        "Q-ANI-04",
                        "Adjacent silhouettes exceed the configured bounding-box jitter.",
                        fs=[f - 1, f],
                        level="warning",
                    )
    for slc in p.slices:
        bad = [
            k.frame
            for k in slc.keys
            if k.w
            and (k.x < 0 or k.y < 0 or k.x + k.w > p.canvas.width or k.y + k.h > p.canvas.height)
        ]
        if bad:
            add("Q-SLC-01", f"Slice {slc.id} extends beyond the canvas.", fs=bad)
    sources: dict[str, Any] = {"total": 0, "accepted": 0, "overridden": 0, "grid_scores": {}}
    if root is not None:
        path = Path(root) / "source/manifest.json"
        if path.is_file():
            manifest = (
                source_manifest
                if source_manifest is not None
                else Sources.model_validate_json(path.read_bytes())
            )
            sources["total"] = len(manifest.sources)
            for source in manifest.sources:
                pipeline = source.pipeline
                sources["accepted"] += int(bool(pipeline and pipeline.accepted))
                sources["overridden"] += int(bool(pipeline and pipeline.gates_overridden))
                if pipeline and type(pipeline.report.get("grid_score")) is int:
                    sources["grid_scores"][source.id] = pipeline.report["grid_score"]
                if not source.placements:
                    continue
                fs = sorted({f for place in source.placements for f in place.frames})
                if pipeline and (pipeline.gates_overridden or pipeline.report.get("warnings")):
                    reason = (
                        "overridden gates" if pipeline.gates_overridden else "pipeline warnings"
                    )
                    add("Q-SRC-01", f"Source {source.id} was placed with {reason}.", fs=fs)
                if source.license == "unknown":
                    add("Q-SRC-02", f"Source {source.id} has unknown usage terms.", fs=fs)
                for file in source.files:
                    relative = Path(file.path)
                    target = (
                        Path(root) / relative
                        if relative.parts and relative.parts[0] == "source"
                        else path.parent / relative
                    )
                    try:
                        safe = target.resolve().is_relative_to(Path(root).resolve())
                        valid = (
                            safe
                            and target.is_file()
                            and sha256(target.read_bytes()).hexdigest() == file.sha256
                        )
                    except OSError:
                        valid = False
                    if not valid:
                        add(
                            "Q-SRC-03",
                            f"Source {source.id} file is missing or has a changed SHA-256.",
                            fs=fs,
                        )
                        break
    if rules is not None:
        issues = [i for i in issues if i["rule"] in rules or i["rule"].startswith("S-")]
    if selected_frames is not None:
        selected = set(selected_frames)
        issues = [
            i
            for i in issues
            if not i["where"].get("frames") or selected.intersection(i["where"]["frames"])
        ]
    # Coalesce by the identity used by the delta contract.
    unique = {}
    for issue in issues:
        key = identity(issue)
        if key not in unique:
            unique[key] = issue
        elif issue["message"] != unique[key]["message"]:
            unique[key]["message"] += " " + issue["message"]
    issues = sorted(
        unique.values(),
        key=lambda i: (
            {"error": 0, "warning": 1, "info": 2}[i["level"]],
            i["rule"],
            i["where"].get("frames", []),
            i["where"].get("layer") or "",
        ),
    )
    counts = {
        level: sum(i["level"] == level for i in issues) for level in ("error", "warning", "info")
    }
    metrics = {
        "palette_size": len(p.palette.colors),
        "colors_used": len(usage),
        "unused_palette": len(unused),
        "off_palette": 0,
        "colors_per_frame": colors_per_frame,
        "colors_per_frame_max": max(colors_per_frame),
        "orphan_pixels": orphans,
        "orphan_pixels_total": sum(orphans),
        "small_clusters_total": small_total,
        "opaque_pixels": opaque_counts,
        "opaque_bbox": boxes,
        "frames": len(p.frames),
        "layers": len(nodes),
        "cels": len(cels),
        "linked_cels": sum(isinstance(c, LinkCel) for c in cels),
        "tags": len(p.tags),
        "slices": len(p.slices),
        "tilesets": len(p.tilesets),
        "non_closed_frames": nonclosed,
        "sources": sources,
    }
    return {
        "ok": counts["error"] == 0,
        "revision": p.revision,
        "counts": counts,
        "issues": issues,
        "metrics": metrics,
        "settings": settings.model_dump(),
        "scope": "full",
    }


def identity(issue):
    where = issue["where"]
    return issue["rule"], tuple(where.get("frames", [])), where.get("layer")


def validation_delta(before, after):
    old = {identity(i) for i in before["issues"]}
    new = {identity(i) for i in after["issues"]}
    changes: dict[str, Any] = {}

    def compare(a, b, prefix=""):
        for key in sorted(set(a) & set(b)):
            av, bv = a[key], b[key]
            name = prefix + key
            if isinstance(av, dict) and isinstance(bv, dict):
                compare(av, bv, name + ".")
            elif type(av) is int and type(bv) is int and av != bv:
                changes[name] = {"before": av, "after": bv}
            elif (
                isinstance(av, list)
                and isinstance(bv, list)
                and all(type(v) is int for v in av + bv)
            ):
                aa, bb = (
                    {"sum": sum(av), "max": max(av, default=0)},
                    {"sum": sum(bv), "max": max(bv, default=0)},
                )
                if aa != bb:
                    changes[name] = {"before": aa, "after": bb}

    compare(before["metrics"], after["metrics"])
    return {
        "ok": after["ok"],
        "errors": after["counts"]["error"],
        "warnings": after["counts"]["warning"],
        "new_issues": [i for i in after["issues"] if identity(i) not in old],
        "resolved_issues": [i for i in before["issues"] if identity(i) not in new],
        "metrics_delta": changes,
    }
