"""All mutation persistence passes through a registered, copy-on-write transaction."""

import os
from contextlib import nullcontext
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import numpy as np
from pydantic import ValidationError

from . import history
from .canonical import dumps_project, json_bytes, load_project, project_path
from .errors import CyberSpriteError, invalid
from .journal_clock import now
from .normalize import normalize_cels
from .quality import bbox, report, validation_delta
from .raster import RasterError
from .references import walk_layers
from .registry import OpContext
from .render import frame_signature, render
from .validation import check_structure


def changes(before, after, ctx):
    oldlayers = {node.id: node for node, _ in walk_layers(before.layers)}
    newlayers = {node.id: node for node, _ in walk_layers(after.layers)}
    layers = sorted(
        k for k in set(oldlayers) | set(newlayers) if oldlayers.get(k) != newlayers.get(k)
    )
    frame_changes = []
    for f in range(max(len(before.frames), len(after.frames))):
        if f < min(len(before.frames), len(after.frames)) and frame_signature(
            before, f
        ) == frame_signature(after, f):
            continue
        w = max(before.canvas.width, after.canvas.width)
        h = max(before.canvas.height, after.canvas.height)
        old = np.zeros((h, w, 4), dtype=np.uint8)
        new = old.copy()
        if f < len(before.frames):
            data = render(before, f)
            old[: data.shape[0], : data.shape[1]] = data
        if f < len(after.frames):
            data = render(after, f)
            new[: data.shape[0], : data.shape[1]] = data
        mask = np.any(old != new, axis=2)
        count = int(np.count_nonzero(mask))
        if count:
            frame_changes.append({"frame": f, "pixels_changed": count, "bbox": bbox(mask)})
    return {
        "data": before != after,
        "frames": frame_changes,
        "layers": layers,
        "linked_frames": sorted(ctx.linked_frames),
        "link_groups": [list(group) for group in sorted(ctx.link_groups)],
        "clipped_pixels": ctx.clipped_pixels,
    }


def _entry(p, kind, actor, ops, changed, validation, label=None, key=None, result=None):
    return history.compact_entry(
        {
            "revision": p.revision,
            "kind": kind,
            "actor": actor,
            "label": label,
            "time": now(),
            "idempotency_key": key,
            "ops": ops,
            "changed": changed,
            "validation_ok": validation,
            "result": result,
        }
    )


def baseline(root, p, state, entries, actor, raw):
    digest = sha256(raw).hexdigest()
    external = state["last_saved_sha256"] is not None and state["last_saved_sha256"] != digest
    writes = []
    if state["last_saved_sha256"] is None or external:
        state = {"undo_stack": [], "redo_stack": [], "last_saved_sha256": digest}
        writes.append((history.snapshot_path(root, p.revision), history.snapshot_bytes(p)))
        kind = "external" if external else "create"
        entries = entries + [_entry(p, kind, actor, [], {}, report(p, root=root)["ok"])]
    return state, entries, writes


def synchronize(root, p, *, actor=None):
    """Queries detect external edits too, without rewriting the project."""
    root = Path(root)
    actor = os.environ.get("CYBERSPRITE_ACTOR", "cli") if actor is None else actor
    with history.ProjectLock(root, actor):
        current = load_project(root)
        if current != p:
            return current
        raw = project_path(root).read_bytes()
        state, entries, writes = baseline(
            root, p, history.read_state(root), history.read_journal(root), actor, raw
        )
        if writes:
            writes.extend(
                [
                    (history.paths(root) / "journal.jsonl", history.journal_bytes(entries)),
                    (history.paths(root) / "state.json", json_bytes(state)),
                ]
            )
            history.save_files(writes)
    return p


def transact(
    registry,
    path,
    calls,
    options,
    *,
    op="apply_ops",
    label=None,
    actor=None,
    previewer=None,
    initial_project=None,
    prepared=None,
    held_lock=None,
):
    target = project_path(path)
    root = target.parent
    actor = os.environ.get("CYBERSPRITE_ACTOR", "cli") if actor is None else actor
    active_lock = held_lock
    if active_lock is None and not options.dry_run:
        active_lock = history.ProjectLock(root, actor)
    lock = nullcontext() if options.dry_run or held_lock is not None else active_lock
    with lock:
        before = load_project(target) if initial_project is None else initial_project
        raw = target.read_bytes() if initial_project is None else dumps_project(before)
        if options.expect_revision is not None and options.expect_revision != before.revision:
            raise CyberSpriteError(
                "E_REVISION_CONFLICT",
                "Project revision does not match expect_revision.",
                "Read get_info and rebase the operation on the current revision.",
                {"expected_revision": options.expect_revision, "current_revision": before.revision},
            )
        entries = history.read_journal(root)
        if options.idempotency_key:
            for entry in reversed(entries[-1000:]):
                if entry.get("idempotency_key") == options.idempotency_key and entry.get("result"):
                    result = deepcopy(entry["result"])
                    result["replayed"] = True
                    return result
        state = history.read_state(root)
        state, entries, writes = baseline(root, before, state, entries, actor, raw)
        after = deepcopy(before)
        ctx = OpContext(after, root, prepared=prepared)
        results = []
        kind = op if op in ("undo", "redo") else "tx"
        restored = None
        if kind in ("undo", "redo"):
            steps = calls[0]["args"].get("steps", 1)
            source, dest = (
                ("undo_stack", "redo_stack") if kind == "undo" else ("redo_stack", "undo_stack")
            )
            for _ in range(steps):
                if not state[source]:
                    raise CyberSpriteError(
                        "E_NOTHING_TO_UNDO" if kind == "undo" else "E_NOTHING_TO_REDO",
                        f"Nothing to {kind}.",
                        "Read get_history to inspect available history.",
                    )
                restored = state[source].pop()
                state[dest].append(after.revision)
                after = history.restore(root, restored)
            after.revision = before.revision
            ctx.project = after
            results = [{"restored_revision": restored}]
        else:
            if not 1 <= len(calls) <= 1000:
                raise invalid("A transaction must contain 1..1000 mutate operations.")
            for index, call in enumerate(calls):
                try:
                    definition = registry.get(call["op"])
                    ingest = (
                        definition.kind == "ingest"
                        and op == call["op"]
                        and prepared is not None
                        and len(calls) == 1
                    )
                    if (definition.kind != "mutate" and not ingest) or call["op"] in (
                        "undo",
                        "redo",
                        "apply_ops",
                    ):
                        raise invalid(
                            "Only ordinary mutate operations can appear inside apply_ops.",
                            op=call["op"],
                        )
                    result = definition.apply(ctx, definition.parse(call["args"]))
                    results.append(
                        definition.result.model_validate(result).model_dump(by_alias=True)
                    )
                except (CyberSpriteError, RasterError, ValidationError) as error:
                    if isinstance(error, RasterError):
                        error = CyberSpriteError(error.code, str(error), error.hint)
                    elif isinstance(error, ValidationError):
                        error = invalid(
                            "Operation arguments produce invalid data.", reason=str(error)
                        )
                    error.op_index = index
                    raise error
        try:
            after = normalize_cels(after)
        except (CyberSpriteError, ValueError, KeyError, AttributeError) as error:
            raise CyberSpriteError(
                "E_INVARIANT",
                f"Operation produced unnormalizable cels: {error}",
                "Report the operation sequence to the plugin or core maintainer.",
            ) from error
        structural = check_structure(after)
        if structural:
            raise CyberSpriteError(
                "E_INVARIANT",
                "Operation broke structural invariants.",
                "Report the operation sequence to its implementer.",
                {"issues": [i.as_dict() for i in structural]},
            )
        no_op = before == after and kind == "tx" and not ctx.side_writes and initial_project is None
        if not no_op:
            after.revision = before.revision + 1
        previous_report = report(before, root=root, source_manifest=ctx.previous_source_manifest)
        next_report = report(after, root=root, source_manifest=ctx.source_manifest)
        changed = changes(before, after, ctx)
        result = {
            "ok": True,
            "op": op,
            "project": root.as_posix(),
            "revision": {"before": before.revision, "after": after.revision},
            "no_op": no_op,
            "replayed": False,
            "dry_run": options.dry_run,
            "result": {"results": results} if op == "apply_ops" else results[0],
            "changed": changed,
            "validation": validation_delta(previous_report, next_report),
            "preview": {"paths": [], "scale": 1, "omitted_frames": []},
            "warnings": ctx.warnings,
        }
        if options.dry_run:
            result["would_commit"] = not no_op
            if previewer and options.preview != "none":
                result["preview"] = previewer(after, changed, root, options.preview, True)
            return result
        assert active_lock is not None
        active_lock.require_owned()
        if no_op:
            # Baseline/external bookkeeping is staged until all operations succeed.
            if writes:
                writes.extend(
                    [
                        (history.paths(root) / "journal.jsonl", history.journal_bytes(entries)),
                        (history.paths(root) / "state.json", json_bytes(state)),
                    ]
                )
                history.save_files(writes)
            return result
        if kind == "tx":
            state["undo_stack"].append(before.revision)
            state["redo_stack"] = []
        data = dumps_project(after)
        state["last_saved_sha256"] = sha256(data).hexdigest()
        entry = _entry(
            after,
            kind,
            actor,
            calls,
            changed,
            next_report["ok"],
            label,
            options.idempotency_key,
            result,
        )
        entries.append(entry)
        writes.extend(
            [
                (history.snapshot_path(root, after.revision), history.snapshot_bytes(after)),
                (history.paths(root) / "journal.jsonl", history.journal_bytes(entries)),
                (history.paths(root) / "state.json", json_bytes(state)),
                (target, data),
            ]
        )
        writes.extend(ctx.side_writes)
        backups = history.save_files(writes)
        preview_folder = root / ".cybersprite/previews"
        pattern = f"r{after.revision:06d}_f*.png"
        previous_previews = {path: path.read_bytes() for path in preview_folder.glob(pattern)}
        if previewer and options.preview != "none":
            try:
                result["preview"] = previewer(after, changed, root, options.preview, False)
            except (OSError, CyberSpriteError) as error:
                result["warnings"].append({"code": "W_PREVIEW_UNAVAILABLE", "message": str(error)})
        # Save the exact returned envelope for idempotent replay, including preview paths.
        entries[-1]["result"] = result
        try:
            history.atomic_write(
                history.paths(root) / "journal.jsonl", history.journal_bytes(entries)
            )
        except CyberSpriteError:
            history.restore_files(backups)
            for path in preview_folder.glob(pattern):
                if path in previous_previews:
                    history.atomic_write(path, previous_previews[path])
                else:
                    path.unlink(missing_ok=True)
            raise
        try:
            history.retain(root)
            history.retain_previews(root)
        except (OSError, CyberSpriteError):
            # Derived retention must not turn an authoritative commit into a reported failure.
            pass
        return result
