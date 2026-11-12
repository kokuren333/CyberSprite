"""Authenticated same-origin HTTP shell and JSON-RPC WebSocket transport."""

import asyncio
import base64
import json
import secrets
from collections import OrderedDict
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocketDisconnect

from cybersprite import ops
from cybersprite.core import history
from cybersprite.core.canonical import load_project, loads_project, project_path
from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.models import Rect
from cybersprite.core.quality import cached_frame_rgba
from cybersprite.core.render import RenderOptions, render
from cybersprite.mcp.contracts import with_path_metadata
from cybersprite.mcp.paths import PathPolicy

BOOTSTRAP = """<!doctype html><html><meta charset="utf-8"><title>CyberSprite</title>
<body><p id="message">Connecting to CyberSprite…</p><script>
const token=location.hash.slice(1);
fetch('/auth',{method:'POST',headers:{Authorization:'Bearer '+token}}).then(r=>{
 if(!r.ok)throw Error('Open the complete server URL including its fragment token.');
 location.replace('/app#'+token);
}).catch(e=>document.getElementById('message').textContent=e.message);
</script></body></html>"""


class RpcFault(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


class Session:
    def __init__(self, socket, project):
        self.socket, self.project = socket, project
        self.send_lock = asyncio.Lock()

    async def send(self, value):
        async with self.send_lock:
            await self.socket.send_json(value)


class Service:
    def __init__(self, root, project=None, allow_dir=()):
        self.policy = PathPolicy(root, allow_dir)
        self.initial = self.path(project) if project else None
        self.sessions = set()
        self.watched = {}
        self.models = OrderedDict()
        self.lock = asyncio.Lock()
        self.prefs = {"language": "auto", "zoom": 8, "grid": False, "onion": False}

    def read_project(self, project):
        # Read the actual bytes every time. A same-size external edit (even with
        # a restored timestamp) must never reuse a stale parsed model.
        try:
            data = (project / "project.json").read_bytes()
        except OSError:
            # Preserve the core's specific missing-project and IO errors.
            return load_project(project)
        cached = self.models.get(project)
        if cached is not None and data == cached[0]:
            return cached[1]
        model = loads_project(data)
        if len(data) <= 4 * 1024 * 1024:
            self.models[project] = (data, model)
            self.models.move_to_end(project)
            while (
                len(self.models) > 8
                or sum(len(item[0]) for item in self.models.values()) > 16 * 1024 * 1024
            ):
                self.models.popitem(last=False)
        return model

    def path(self, value):
        path = self.policy.resolve(value)
        self.policy.check_project(path)
        return project_path(path).parent

    def run_op(self, name, project, arguments):
        definition = with_path_metadata(ops.registry().get(name))
        schema = definition.args.model_json_schema()
        arguments = self.policy.arguments(arguments, schema)
        self.check_outputs(arguments, schema, project)
        if name == "apply_ops":
            parsed = definition.parse({k: v for k, v in arguments.items() if k in {"ops", "label"}})
            for call in parsed.ops:
                child = with_path_metadata(ops.registry().get(call.op))
                schema = child.args.model_json_schema()
                call.args = self.policy.arguments(call.args, schema)
                self.check_outputs(call.args, schema, project)
            arguments["ops"] = [call.model_dump() for call in parsed.ops]
        self.policy.check_project(project)
        value = ops.execute(name, project, arguments, actor="gui")
        return self.policy.result(value, project)

    def check_outputs(self, value, schema, project, definitions=None):
        definitions = definitions or schema.get("$defs", {})
        if "$ref" in schema:
            return self.check_outputs(
                value, definitions[schema["$ref"].split("/")[-1]], project, definitions
            )
        if schema.get("x-cybersprite-path") == "output":
            for item in value if isinstance(value, list) else [value]:
                if not isinstance(item, str):
                    continue
                target = self.policy.resolve(item)
                canonical = project / "project.json"
                if target.name == "project.json" or (
                    target.exists() and canonical.exists() and target.samefile(canonical)
                ):
                    raise invalid(
                        "An output path cannot overwrite project.json; choose another file."
                    )
        for variant in schema.get("anyOf", schema.get("oneOf", [])):
            self.check_outputs(value, variant, project, definitions)
        if isinstance(value, dict):
            for key, item in value.items():
                self.check_outputs(
                    item, schema.get("properties", {}).get(key, {}), project, definitions
                )
        if isinstance(value, list):
            for item in value:
                self.check_outputs(item, schema.get("items", {}), project, definitions)

    def scan(self, project):
        self.policy.check_project(project)
        stat = (project / "project.json").stat()
        stamp = (stat.st_mtime_ns, stat.st_size)
        previous = self.watched.get(project)
        if previous and stamp == previous[0]:
            return []
        revision = self.read_project(project).revision
        self.watched[project] = (stamp, revision)
        if previous is None or revision == previous[1]:
            return []
        entries = [
            e
            for e in history.read_journal(project, after_revision=previous[1])
            if e["revision"] <= revision
        ]
        if not entries:
            entries = [{"revision": revision, "actor": "external", "changed": {}}]
        return [
            {
                "project": self.policy.relative(project),
                **{k: e[k] for k in ("revision", "actor", "changed")},
            }
            for e in entries
        ]

    async def changes(self):
        for project in sorted({s.project for s in self.sessions if s.project}, key=str):
            try:
                events = await asyncio.to_thread(self.scan, project)
            except (OSError, CyberSpriteError):
                continue  # An atomic external replacement may be temporarily unreadable.
            for event in events:
                for session in list(self.sessions):
                    if session.project == project:
                        with suppress(WebSocketDisconnect, RuntimeError, OSError):
                            await session.send(
                                {"jsonrpc": "2.0", "method": "project.changed", "params": event}
                            )

    async def poll(self):
        while True:
            await asyncio.sleep(0.25)
            async with self.lock:
                await self.changes()

    def dispatch(self, session, method, values):
        values = dict(values)
        if method not in {
            "project.open",
            "project.close",
            "project.get",
            "op.list",
            "op.apply",
            "render.frame",
            "history.list",
            "history.undo",
            "history.redo",
            "validate.run",
            "pipeline.preview",
            "import.commit",
            "export.run",
            "sources.list",
            "sources.get",
            "prefs.get",
            "prefs.set",
        }:
            raise RpcFault(-32601, f"Unknown method {method!r}; see docs/GUI.md.")
        if method == "op.list":
            return [with_path_metadata(op).describe() for op in ops.registry().all()]
        if method == "prefs.get":
            return self.prefs
        if method == "prefs.set":
            if set(values) - set(self.prefs):
                raise invalid("Unknown GUI preference; use prefs.get to list supported keys.")
            for key, value in values.items():
                if key == "language" and value not in ("auto", "ja", "en"):
                    raise invalid("language must be auto, ja, or en.")
                if key == "zoom" and (type(value) is not int or not 1 <= value <= 64):
                    raise invalid("zoom must be an integer from 1 to 64.")
                if key in {"grid", "onion"} and type(value) is not bool:
                    raise invalid(f"{key} must be a boolean.")
            self.prefs = {**self.prefs, **values}
            return self.prefs
        if method == "project.close":
            session.project = None
            return {"closed": True}
        path = values.pop("project", None)
        project = self.path(path) if path else session.project
        if project is None:
            raise CyberSpriteError(
                "E_PROJECT_NOT_FOUND",
                "No project is open.",
                "Call project.open with a project path first.",
            )
        self.policy.check_project(project)
        if method == "project.open":
            result = self.run_op(
                "get_info", project, {"include": ["summary", "layers", "frames", "tags", "palette"]}
            )
            session.project = project
            if project not in self.watched:
                self.scan(project)
            return result
        if method == "project.get":
            values.setdefault(
                "include",
                [
                    "summary",
                    "layers",
                    "frames",
                    "tags",
                    "slices",
                    "palette",
                    "sources",
                    "validation",
                    "history",
                ],
            )
            return self.run_op("get_info", project, values)
        if method == "render.frame":
            p = self.read_project(project)
            frames = values.pop("frames", [values.pop("frame", 0)])
            region = values.pop("region", None)
            if values or not isinstance(frames, list) or not 1 <= len(frames) <= 17:
                raise invalid("Use frame or a frames list of 1 to 17 indices, and optional region.")
            if region is not None:
                region = Rect.model_validate(region).model_dump()
            images = []
            for frame in frames:
                # Validate the requested index through render on a miss, including
                # invalid indices; cached signatures use the same core checks.
                image = cached_frame_rgba(p, frame) if region is None else None
                if image is None:
                    image = render(p, frame, RenderOptions(crop=region))
                images.append(
                    {
                        "frame": frame,
                        "width": image.shape[1],
                        "height": image.shape[0],
                        "rgba": base64.b64encode(image.tobytes()).decode("ascii"),
                    }
                )
            return {
                "project": self.policy.relative(project),
                "revision": p.revision,
                "encoding": "rgba8-base64",
                "frames": images,
            }
        if method == "op.apply":
            name = values.pop("op", "apply_ops")
            args = values.pop("args", None)
            if args is not None:
                if values:
                    raise invalid(
                        "Put transaction options inside args when using the op/args form."
                    )
                values = args
            result = self.run_op(name, project, values)
            if name == "new_project" and not values.get("dry_run"):
                session.project = project
                self.scan(project)
            return result
        aliases = {
            "history.list": "get_history",
            "history.undo": "undo",
            "history.redo": "redo",
            "validate.run": "validate",
            "pipeline.preview": "import_image",
            "import.commit": "import_image",
            "sources.list": "list_sources",
            "sources.get": "get_source",
        }
        if method == "pipeline.preview":
            values["dry_run"] = True
        if method == "history.undo" and "to_revision" in values:
            revision = values.pop("to_revision")
            current = self.run_op("get_history", project, {})["revision"]
            stack = history.read_state(project)["undo_stack"]
            if type(revision) is not int or revision not in stack:
                raise CyberSpriteError(
                    "E_HISTORY_UNAVAILABLE",
                    "The selected revision is not on the current undo path.",
                    "Choose an earlier reachable revision or undo one step at a time.",
                )
            values["steps"] = len(stack) - stack.index(revision)
            values.setdefault("expect_revision", current)
        if method == "export.run":
            name = values.pop("op", "export_image")
            if not name.startswith("export_") or ops.registry().get(name).kind != "export":
                raise invalid("export.run requires a registered export operation from op.list.")
        elif method in aliases:
            name = aliases[method]
            if name in {"import_image", "list_sources", "get_source"} and name not in {
                op.name for op in ops.registry().all()
            }:
                # Sources are already available via the query registry before M5/M6 land.
                if method.startswith("sources."):
                    sources = self.run_op("get_info", project, {"include": ["sources"]})["result"][
                        "sources"
                    ]
                    if method == "sources.list":
                        return sources
                    found = next(
                        (s for s in sources["sources"] if s["id"] == values.get("id")), None
                    )
                    if found:
                        return found
                    raise CyberSpriteError(
                        "E_SOURCE_NOT_FOUND",
                        "Source ID is not present.",
                        "Choose an ID returned by sources.list.",
                    )
                raise CyberSpriteError(
                    "E_UNSUPPORTED",
                    "The import pipeline is not installed in this build.",
                    "Integrate M6 and retry; op.list lists available operations.",
                )
        else:
            raise RpcFault(-32601, f"Unknown method {method!r}; see docs/GUI.md.")
        return self.run_op(name, project, values)

    async def request(self, session, request, *, send=True):
        request_id = request.get("id") if isinstance(request, dict) else None
        notify = isinstance(request, dict) and "id" not in request
        try:
            if (
                not isinstance(request, dict)
                or request.get("jsonrpc") != "2.0"
                or not isinstance(request.get("method"), str)
                or (
                    "id" in request
                    and (
                        isinstance(request_id, bool)
                        or not isinstance(request_id, (str, int, type(None)))
                    )
                )
            ):
                notify = False
                raise RpcFault(-32600, "Expected one JSON-RPC 2.0 request object.")
            params = request.get("params", {})
            if not isinstance(params, dict):
                raise RpcFault(-32602, "params must be an object with named arguments.")
            method = request["method"]
            long_job = method in {"pipeline.preview", "import.commit", "export.run"}
            if long_job:
                await session.send(
                    {
                        "jsonrpc": "2.0",
                        "method": "job.progress",
                        "params": {"id": request_id, "method": method, "percent": 0},
                    }
                )
            async with self.lock:
                result = await asyncio.to_thread(self.dispatch, session, method, params)
                await self.changes()
            if long_job:
                await session.send(
                    {
                        "jsonrpc": "2.0",
                        "method": "job.progress",
                        "params": {"id": request_id, "method": method, "percent": 100},
                    }
                )
            response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        except RpcFault as error:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": error.code, "message": error.message},
            }
        except Exception as error:
            if not isinstance(error, CyberSpriteError):
                from pydantic import ValidationError

                if isinstance(error, (ValidationError, TypeError, ValueError, KeyError)):
                    error = invalid("Invalid RPC arguments.", reason=str(error))
                elif isinstance(error, OSError):
                    error = CyberSpriteError(
                        "E_IO",
                        "Cannot read a requested file.",
                        "Check the path and file permissions.",
                    )
                else:
                    error = CyberSpriteError(
                        "E_INTERNAL",
                        "Unexpected GUI server failure.",
                        "Report the method and arguments to the maintainer.",
                    )
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": error.message, "data": error.as_dict()},
            }
        if not notify and send:
            await session.send(response)
        return None if notify else response


def create_app(*, root, token, origin, project=None, allow_dir=(), static=None):
    service = Service(root, project, allow_dir)
    static = Path(static or Path(__file__).parent / "static").resolve()

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(service.poll())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    def same_origin(request, required=False):
        supplied = request.headers.get("origin")
        return request.headers.get("host") == origin.removeprefix("http://") and (
            supplied == origin or (not required and supplied is None)
        )

    def matches(value):
        return isinstance(value, str) and secrets.compare_digest(value, token)

    async def http(request):
        if not same_origin(request):
            return Response("Foreign origin or host rejected.", status_code=403)
        if request.url.path == "/":
            return HTMLResponse(
                BOOTSTRAP, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
            )
        if request.url.path == "/auth":
            if not same_origin(request, True) or not matches(
                request.headers.get("authorization", "").removeprefix("Bearer ")
            ):
                return Response("Missing or invalid token.", status_code=403)
            response = JSONResponse({"ok": True})
            response.set_cookie("cs_session", token, httponly=True, samesite="strict", path="/")
            return response
        if not matches(request.cookies.get("cs_session")):
            return Response("Missing or invalid token.", status_code=403)
        if request.url.path.startswith("/files/"):
            try:
                path = service.policy.resolve(request.path_params["path"])
            except CyberSpriteError:
                return Response("Path resolves outside the allowed directories.", status_code=403)
            if path.name == "project.json" or not path.is_file():
                return Response("File not found.", status_code=404)
            return FileResponse(
                path, headers={"Cache-Control": "no-store", "Content-Security-Policy": "sandbox"}
            )
        relative = (
            "index.html" if request.url.path == "/app" else request.path_params.get("path", "")
        )
        path = (static / relative).resolve()
        if not path.is_relative_to(static) or not path.is_file():
            return Response(
                "GUI build missing. Run npm ci and npm run build in gui/.", status_code=404
            )
        return FileResponse(
            path,
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )

    async def websocket(socket):
        protocols = socket.scope.get("subprotocols", [])
        if (
            not same_origin(socket, True)
            or len(protocols) != 2
            or protocols[0] != "cybersprite"
            or not matches(protocols[1])
        ):
            await socket.close(code=1008)
            return
        await socket.accept(subprotocol="cybersprite")
        session = Session(socket, service.initial)
        async with service.lock:
            if session.project:
                if session.project not in service.watched:
                    with suppress(OSError, CyberSpriteError):
                        await asyncio.to_thread(service.scan, session.project)
            service.sessions.add(session)
        try:
            while True:
                raw = await socket.receive_text()
                if len(raw) > 8 * 1024 * 1024:
                    await socket.close(code=1009)
                    break
                try:
                    request = json.loads(raw)
                except ValueError:
                    await session.send(
                        {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {
                                "code": -32700,
                                "message": "Invalid JSON; send one request object.",
                            },
                        }
                    )
                    continue
                if isinstance(request, list) and request:
                    replies = []
                    for item in request:
                        reply = await service.request(session, item, send=False)
                        if reply is not None:
                            replies.append(reply)
                    if replies:
                        await session.send(replies)
                else:
                    await service.request(session, request)
        except WebSocketDisconnect:
            pass
        finally:
            service.sessions.discard(session)

    app = Starlette(
        routes=[
            Route("/", http),
            Route("/auth", http, methods=["POST"]),
            WebSocketRoute("/ws", websocket),
            Route("/files/{path:path}", http),
            Route("/{path:path}", http),
        ],
        lifespan=lifespan,
    )
    app.state.service = service
    return app
