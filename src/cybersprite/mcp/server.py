"""Stateless MCP 2026-07-28 server generated from the shared Op registry."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from pydantic import ValidationError

from cybersprite import ops
from cybersprite.core.canonical import load_project
from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.formats.common import export_policy

from .contracts import FORBIDDEN, GENERATION, MINIMAL, ORDER, describe, with_path_metadata
from .execution import DeadlineExpired, Execution
from .paths import PathPolicy
from .result_paths import error_schema, response_schema

TEXT_LIMIT = 256 * 1024
TIMEOUTS = {"import_image": 300, "generate_image": 1800}


def _sdk():
    try:
        from mcp import types
        from mcp.server import Server
    except ImportError as error:
        raise RuntimeError(
            "MCP support is not installed. Run uv sync --extra mcp or install cybersprite[mcp]."
        ) from error
    return types, Server


class MCPService:
    def __init__(
        self,
        *,
        root=None,
        allow_dir=(),
        profile="standard",
        enable_generation=False,
        allow_plugin_op=(),
        read_only=False,
        registry=None,
    ):
        if profile not in {"standard", "minimal"}:
            raise ValueError("profile must be standard or minimal")
        _sdk()  # Initialize protocol models before starting any request deadline.
        self.policy = PathPolicy(root or Path.cwd(), allow_dir)
        self.registry = registry or ops.registry()
        self.profile, self.read_only = profile, read_only
        self.allow_plugin_op = frozenset(allow_plugin_op)
        self.enable_generation = enable_generation
        self.definitions = {op.name: with_path_metadata(op) for op in self.registry.all()}
        self.exposed = {
            name: op for name, op in self.definitions.items() if self._allowed(op, listed=True)
        }
        self.contracts = {name: describe(op) for name, op in self.exposed.items()}
        self.response_schemas = {name: response_schema(op) for name, op in self.exposed.items()}

    def _allowed(self, op, *, listed):
        if op.name in FORBIDDEN or op.kind not in {"query", "mutate", "ingest", "export"}:
            return False
        if op.provider != "builtin" and op.name not in self.allow_plugin_op:
            return False
        if (op.name in GENERATION or op.idempotency == "G") and not self.enable_generation:
            return False
        if self.read_only and op.kind != "query":
            return False
        if listed and self.profile == "minimal" and op.name not in MINIMAL:
            return op.name in GENERATION and self.enable_generation
        return True

    def tools(self):
        types, _ = _sdk()
        rank = {name: index for index, name in enumerate(ORDER)}
        return [
            types.Tool(
                **{
                    key: self.contracts[name][key]
                    for key in (
                        "name",
                        "title",
                        "description",
                        "inputSchema",
                        "outputSchema",
                        "annotations",
                    )
                }
            )
            for name in sorted(self.exposed, key=lambda n: (rank.get(n, len(rank)), n))
        ]

    def _arguments(self, op, values):
        schema = self.contracts[op.name]["argumentSchema"]
        allowed = set(schema["properties"])
        if not isinstance(values, dict):
            raise invalid("Tool arguments must be an object containing only declared fields.")
        unknown = sorted(set(values) - allowed)
        if unknown:
            raise invalid(
                "Undeclared tool arguments: " + ", ".join(unknown) + ".",
                arguments=unknown,
                candidates=sorted(allowed),
            )
        if not isinstance(values.get("project"), str):
            raise invalid("project is required and must be a path string.")
        values = self.policy.arguments(deepcopy(values), schema)
        if op.name == "apply_ops":
            parsed = op.parse({k: v for k, v in values.items() if k in {"ops", "label"}})
            for index, call in enumerate(parsed.ops):
                child = self.definitions.get(call.op)
                if child is None or not self._allowed(child, listed=False):
                    error = invalid(
                        "Batch operation is not permitted by the server policy.", op=call.op
                    )
                    error.op_index = index
                    raise error
                call.args = self.policy.arguments(call.args, child.args.model_json_schema())
            values["ops"] = [call.model_dump() for call in parsed.ops]
        return values

    def _pack(self, value, root):
        types, _ = _sdk()
        images = []
        for section in (value.get("result", {}), value.get("preview", {})):
            images.extend(section.pop("images", []))
        schema = (
            self.response_schemas[value["op"]]
            if value["ok"]
            else error_schema(value["error"]["code"])
        )
        value = self.policy.result(value, root, schema)
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        if len(text.encode("utf-8")) > TEXT_LIMIT:
            raise CyberSpriteError(
                "E_LIMIT_EXCEEDED",
                "Tool result exceeds the 256 KiB text limit.",
                "Reduce frames, get_pixels rect, history limit, or get_info include sections.",
                {"limit_bytes": TEXT_LIMIT},
            )
        return types.CallToolResult(
            structured_content=value,
            content=[
                types.TextContent(type="text", text=text),
                *(
                    types.ImageContent(type="image", data=data, mime_type="image/png")
                    for data in images
                ),
            ],
            is_error=not value["ok"],
        )

    def call(self, name, arguments, *, actor="agent:unknown"):
        if name not in self.exposed:
            from mcp.shared.exceptions import MCPError

            raise MCPError(-32602, f"Unknown or unavailable tool {name!r}.")
        project = arguments.get("project", "") if isinstance(arguments, dict) else ""
        revision = 0
        root = self.policy.root
        try:
            if not isinstance(project, str) or not project:
                raise invalid("project is required and must be a nonempty path string.")
            project_path = self.policy.resolve(project)
            project = self.policy.relative(project_path)
            root = project_path.parent if project_path.name == "project.json" else project_path
            scope = Execution(
                self.policy,
                root,
                actor,
                TIMEOUTS.get(name, 60),
                writable=self.exposed[name].kind != "query"
                and not (isinstance(arguments, dict) and arguments.get("dry_run") is True),
            )
            self.policy.check_project(project_path, scope.check)

            def execute():
                nonlocal revision
                if (root / "project.json").exists():
                    revision = load_project(root).revision
                values = self._arguments(self.exposed[name], arguments)
                values.pop("project")
                # Registry execution is the sole mutation path. The boundary also
                # rolls back if response serialization or the deadline fails.
                with export_policy(self.policy.root, self.policy.allowed):
                    value = ops.execute(name, project_path, values, actor=actor)
                return self._pack(
                    value, self.policy.root if self.exposed[name].kind == "export" else root
                )

            return scope.run(execute)
        except DeadlineExpired:
            error = CyberSpriteError(
                "E_TIMEOUT",
                "Tool execution exceeded its deadline; no project changes were committed.",
                "Split apply_ops into smaller transactions or reduce the requested frame range.",
            )
        except CyberSpriteError as caught:
            error = caught
        except ValidationError as caught:
            error = invalid(
                "Invalid tool arguments.",
                issues=caught.errors(include_input=False, include_context=False),
            )
        except OSError as caught:
            error = CyberSpriteError(
                "E_IO",
                "Cannot access a requested file.",
                "Check file existence and permissions.",
                {"os_error": str(caught)},
            )
        except Exception as caught:
            error = CyberSpriteError(
                "E_INTERNAL",
                "Unexpected operation failure.",
                "Report the operation and arguments to the maintainer.",
                {"exception_type": type(caught).__name__},
            )
        # Do not echo an untrusted absolute path or an arbitrarily large argument.
        if not isinstance(project, str) or len(project) > 1024 or Path(project).is_absolute():
            project = ""
        if project:
            try:
                self.policy.resolve(project)
            except CyberSpriteError:
                project = ""
        info = error.as_dict()
        if hasattr(error, "op_index"):
            info["op_index"] = error.op_index
        value = {
            "ok": False,
            "op": name,
            "project": project,
            "revision": {"before": revision, "after": revision},
            "error": info,
        }
        try:
            return self._pack(value, root)
        except CyberSpriteError:
            value["error"]["details"] = {}
            value["project"] = ""
            return self._pack(value, root)


def create_server(**options):
    types, Server = _sdk()
    service = MCPService(**options)

    async def list_tools(ctx, params):
        return types.ListToolsResult(tools=service.tools())

    async def call_tool(ctx, params):
        meta = ctx.meta or {}
        if hasattr(meta, "model_dump"):
            meta = meta.model_dump(by_alias=True)
        info = meta.get("io.modelcontextprotocol/clientInfo")
        if not info and ctx.session.client_params:
            info = ctx.session.client_params.client_info.model_dump()
        actor = "agent:" + (info or {}).get("name", "unknown")
        import anyio

        # Never abandon a mutating worker: finish rollback before replying or
        # propagating cancellation. The worker checks deadlines at core boundaries.
        async with anyio.create_task_group() as group:

            async def progress():
                count = 0
                while True:
                    await ctx.session.report_progress(count, message="Executing registry operation")
                    count += 1
                    await anyio.sleep(1)

            group.start_soon(progress)
            failure = None
            try:
                result = await anyio.to_thread.run_sync(
                    lambda: service.call(params.name, params.arguments or {}, actor=actor)
                )
            except Exception as error:
                failure = error
            finally:
                group.cancel_scope.cancel()
        if failure is not None:
            raise failure
        return result

    async def argument_errors(ctx, call_next):
        # The SDK rejects non-object `arguments` at the protocol layer by default.
        # SPEC 10.3 requires these valid-JSON mistakes to be repairable tool errors.
        if ctx.method == "tools/call" and isinstance(ctx.params, dict):
            name = ctx.params.get("name")
            arguments = ctx.params.get("arguments")
            if isinstance(name, str) and arguments is not None and not isinstance(arguments, dict):
                return await call_tool(ctx, SimpleNamespace(name=name, arguments=arguments))
        return await call_next(ctx)

    server = Server(
        "cybersprite", version="0.1.0", on_list_tools=list_tools, on_call_tool=call_tool
    )
    server.middleware.append(argument_errors)
    return server


def serve(
    *,
    root=None,
    allow_dir=(),
    transport="stdio",
    port=8765,
    profile="standard",
    enable_generation=False,
    allow_plugin_op=(),
    read_only=False,
):
    """Entry point shared by the M3 CLI and python -m cybersprite.mcp."""
    if transport not in {"stdio", "http"}:
        raise ValueError("transport must be stdio or http")
    if allow_plugin_op:
        ops.registry().load_plugins(enabled=True)
    server = create_server(
        root=root,
        allow_dir=allow_dir,
        profile=profile,
        enable_generation=enable_generation,
        allow_plugin_op=allow_plugin_op,
        read_only=read_only,
    )
    if transport == "http":
        import uvicorn

        uvicorn.run(
            server.streamable_http_app(stateless_http=True, host="127.0.0.1"),
            host="127.0.0.1",
            port=port,
        )
    else:
        from mcp.server.stdio import stdio_server

        async def run():
            async with stdio_server() as (read, write):
                await server.run(read, write, server.create_initialization_options())

        asyncio.run(run())
