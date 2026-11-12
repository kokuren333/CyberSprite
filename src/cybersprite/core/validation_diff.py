"""Validation deltas, retaining complete pixel sets outside serialized reports."""

from typing import Any


def identity(issue):
    where = issue["where"]
    return issue["rule"], tuple(where.get("frames", [])), where.get("layer")


class Issue(dict):
    """A bounded public sample plus transient full points for exact transaction diffs."""

    def __init__(self, value, points=None, count=None):
        super().__init__(value)
        self.full_points = (
            frozenset(tuple(pt) for pt in (points or []))
            if value["rule"] in {"Q-PIX-01", "Q-PIX-02"}
            else None
        )
        self.count = (
            count
            if count is not None
            else (len(self.full_points) if self.full_points is not None else 1)
        )


def _points(issues):
    result: set[tuple[str, int, str | None, int, int]] = set()
    for issue in issues:
        if issue["rule"] not in {"Q-PIX-01", "Q-PIX-02"}:
            continue
        where = issue["where"]
        points = getattr(issue, "full_points", None)
        if points is None:
            points = where.get("points", [])
        for frame in where.get("frames", []):
            result.update((issue["rule"], frame, where.get("layer"), x, y) for x, y in points)
    return result


def _count(issue):
    return getattr(issue, "count", max(1, len(issue["where"].get("points", []))))


def validation_delta(before, after):
    old = {identity(i): i for i in before["issues"]}
    new = {identity(i): i for i in after["issues"]}
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
                aa = {"sum": sum(av), "max": max(av, default=0)}
                bb = {"sum": sum(bv), "max": max(bv, default=0)}
                if aa != bb:
                    changes[name] = {"before": aa, "after": bb}

    compare(before["metrics"], after["metrics"])
    result = {
        "ok": after["ok"],
        "errors": after["counts"]["error"],
        "warnings": after["counts"]["warning"],
        "new_issues": [i for i in after["issues"] if identity(i) not in old],
        "resolved_issues": [i for i in before["issues"] if identity(i) not in new],
        "metrics_delta": changes,
    }
    updated = []
    for issue in after["issues"]:
        previous = old.get(identity(issue))
        if previous is None:
            continue
        if (
            previous != issue
            or _count(previous) != _count(issue)
            or getattr(previous, "full_points", None) != getattr(issue, "full_points", None)
        ):
            update = {
                "rule": issue["rule"],
                "where": issue["where"],
                "before": {"count": _count(previous), "level": previous["level"]},
                "after": {"count": _count(issue), "level": issue["level"]},
            }
            if previous["message"] != issue["message"]:
                update["before"]["message"] = previous["message"]
                update["after"]["message"] = issue["message"]
            updated.append(update)
    if updated:
        result["updated_issues"] = updated
    old_points, new_points = _points(before["issues"]), _points(after["issues"])
    for key, points in (
        ("new_points", new_points - old_points),
        ("resolved_points", old_points - new_points),
    ):
        if points:
            ordered = sorted(points, key=lambda p: (p[0], p[1], p[2] or "", p[4], p[3]))
            result[key] = [
                {"rule": rule, "frame": frame, "layer": layer, "x": x, "y": y}
                for rule, frame, layer, x, y in ordered[:64]
            ]
            result[key + "_count"] = len(ordered)
    return result
