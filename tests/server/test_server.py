"""Real loopback HTTP/WebSocket integration; no optional HTTP test client needed."""

# ruff: noqa: E402 -- optional extras must skip before their imports.

import base64
import json
import socket
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

uvicorn = pytest.importorskip("uvicorn")
pytest.importorskip("websockets")
from websockets.exceptions import InvalidStatus
from websockets.sync.client import connect

from cybersprite import ops
from cybersprite.core.canonical import load_project
from cybersprite.core.history import read_journal
from cybersprite.server.app import create_app


@pytest.fixture
def live(tmp_path):
    project = tmp_path / "test.csprite"
    ops.execute("new_project", project, {"width": 8, "height": 8, "frames": 3})
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<title>Test app</title>", encoding="utf-8")
    app = create_app(
        root=tmp_path, project=project, token="test-token", origin=origin, static=static
    )
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="on"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started:
        assert time.monotonic() < deadline
        time.sleep(0.01)
    yield origin, app.state.service, project
    server.should_exit = True
    thread.join(5)
    sock.close()
    assert not thread.is_alive()


def ws(live, token="test-token", origin=None):
    return connect(
        live[0].replace("http:", "ws:") + "/ws",
        origin=origin or live[0],
        subprotocols=["cybersprite", token],
        proxy=None,
    )


def call(connection, method, params=None, request_id=1):
    connection.send(
        json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
    )
    events = []
    while True:
        value = json.loads(connection.recv(timeout=3))
        if "method" in value:
            events.append(value)
        else:
            return value, events


def result(connection, method, params=None):
    response, _ = call(connection, method, params)
    assert "error" not in response, response
    return response["result"]


def http(live, path, headers=None, method="GET"):
    return urlopen(Request(live[0] + path, headers=headers or {}, method=method), timeout=3)


def test_http_token_origin_host_and_static(live):
    assert http(live, "/").status == 200  # Only the data-free bootstrap is public.
    for path in ("/app", "/files/test.csprite/project.json", "/auth"):
        with pytest.raises(HTTPError) as error:
            http(live, path, method="POST" if path == "/auth" else "GET")
        assert error.value.code == 403
    for headers in ({"Origin": "https://foreign.example"}, {"Host": "foreign.example"}):
        with pytest.raises(HTTPError) as error:
            http(live, "/", headers)
        assert error.value.code == 403
    headers = {"Origin": live[0], "Authorization": "Bearer test-token"}
    auth = http(live, "/auth", headers, "POST")
    cookie = auth.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert b"Test app" in http(live, "/app", {"Cookie": cookie}).read()


@pytest.mark.parametrize(
    "token,origin", [("wrong", None), ("test-token", "https://foreign.example")]
)
def test_websocket_rejection(live, token, origin):
    with pytest.raises(InvalidStatus):
        ws(live, token, origin)


def test_websocket_requires_origin_and_token(live):
    url = live[0].replace("http:", "ws:") + "/ws"
    for kwargs in ({"origin": live[0]}, {"subprotocols": ["cybersprite", "test-token"]}):
        with pytest.raises(InvalidStatus):
            connect(url, proxy=None, **kwargs)


def test_rpc_read_render_prefs_and_lifecycle(live):
    with ws(live) as c:
        assert result(c, "project.get")["result"]["summary"]["width"] == 8
        schemas = result(c, "op.list")
        assert {op["name"] for op in schemas} == {op.name for op in ops.registry().all()}
        assert all("inputSchema" in op for op in schemas)
        frames = result(
            c, "render.frame", {"frames": [0, 1, 2], "region": {"x": 1, "y": 2, "w": 3, "h": 4}}
        )
        assert frames["encoding"] == "rgba8-base64"
        assert len(frames["frames"]) == 3
        assert len(base64.b64decode(frames["frames"][0]["rgba"])) == 3 * 4 * 4
        assert result(c, "validate.run")["result"]["ok"]
        assert result(c, "history.list")["result"]["entries"]
        assert result(c, "sources.list") == {"sources": []}
        assert (
            call(c, "sources.get", {"id": "S1"})[0]["error"]["data"]["code"] == "E_SOURCE_NOT_FOUND"
        )
        assert result(c, "prefs.get")["zoom"] == 8
        assert result(c, "prefs.set", {"zoom": 4, "language": "ja"})["zoom"] == 4
        assert "error" in call(c, "prefs.set", {"zoom": 1.5})[0]
        assert result(c, "project.close")["closed"]
        assert call(c, "project.get")[0]["error"]["data"]["code"] == "E_PROJECT_NOT_FOUND"
        assert result(c, "project.open", {"project": "test.csprite"})["revision"] == 0
        assert (
            call(c, "project.open", {"project": "../outside"})[0]["error"]["data"]["code"]
            == "E_PATH_NOT_ALLOWED"
        )


def test_mutations_actor_undo_redo_and_notifications(live, monkeypatch):
    monkeypatch.setenv("CYBERSPRITE_ACTOR", "agent:must-not-override-gui")
    with ws(live) as c:
        value, events = call(
            c,
            "op.apply",
            {
                "ops": [
                    {
                        "op": "line",
                        "args": {
                            "layer": "L1",
                            "frame": 0,
                            "x0": 1,
                            "y0": 2,
                            "x1": 5,
                            "y1": 2,
                            "color": 1,
                        },
                    }
                ],
                "label": "GUI test",
                "preview": "inline",
            },
        )
        assert value["result"]["ok"], value
        assert value["result"]["validation"]
        assert events[0]["method"] == "project.changed"
        assert events[0]["params"]["actor"] == "gui"
        assert events[0]["params"]["revision"] == 1
        assert read_journal(live[2])[-1]["actor"] == "gui"
        assert read_journal(live[2])[-1]["ops"][0]["op"] == "line"
        assert result(c, "history.undo")["ok"]
        assert result(c, "history.redo")["ok"]
        assert all(e["actor"] == "gui" for e in read_journal(live[2])[1:])


def test_external_cli_commit_notifies_within_one_second(live):
    with ws(live) as c:
        result(c, "project.get")
        command = [
            sys.executable,
            "-m",
            "cybersprite",
            "op",
            "set_pixel",
            "--args",
            '{"layer":"L1","frame":0,"x":3,"y":3,"color":1}',
            "-p",
            str(live[2]),
            "--actor",
            "agent:test",
        ]
        subprocess.run(command, check=True, capture_output=True)
        started = time.monotonic()
        event = json.loads(c.recv(timeout=1))
        assert time.monotonic() - started < 1
        assert event["method"] == "project.changed"
        assert event["params"]["actor"] == "agent:test"
        assert event["params"]["revision"] == 1


def test_pipeline_and_export_registry_forwarding(live, monkeypatch):
    original = ops.execute
    seen = []

    def execute(name, project, args, *, actor):
        if name in {"import_image", "export_image"}:
            seen.append((name, args, actor))
            return {
                "ok": True,
                "project": str(project),
                "revision": 0,
                "result": {"verified": True},
            }
        return original(name, project, args, actor=actor)

    from cybersprite.core.registry import EmptyResult, Op
    from cybersprite.ops.args import ARGS

    registry = ops.registry()
    monkeypatch.setattr(ops, "execute", execute)
    for name, kind in (("import_image", "ingest"), ("export_image", "export")):
        monkeypatch.setitem(
            registry._ops, name, Op(name, ARGS["get_palette"], lambda *_: {}, EmptyResult, kind)
        )
    with ws(live) as c:
        for method in ("pipeline.preview", "import.commit", "export.run"):
            response, events = call(c, method)
            assert response["result"]["ok"]
            assert [e["params"]["percent"] for e in events if e["method"] == "job.progress"] == [
                0,
                100,
            ]
        assert seen == [
            ("import_image", {"dry_run": True}, "gui"),
            ("import_image", {}, "gui"),
            ("export_image", {}, "gui"),
        ]


def test_nested_path_restrictions_new_project_and_conflicts(live):
    with ws(live) as c:
        response, _ = call(
            c, "op.apply", {"ops": [{"op": "load_palette", "args": {"source": "../outside.hex"}}]}
        )
        assert response["error"]["data"]["code"] == "E_PATH_NOT_ALLOWED"
        assert load_project(live[2]).revision == 0
        response, _ = call(
            c,
            "op.apply",
            {"ops": [{"op": "delete_frames", "args": {"frames": [1]}}], "expect_revision": 99},
        )
        assert response["error"]["data"]["code"] == "E_REVISION_CONFLICT"
        created = result(
            c,
            "op.apply",
            {"project": "new.csprite", "op": "new_project", "args": {"width": 4, "height": 4}},
        )
        assert created["ok"]
        assert result(c, "project.get")["result"]["summary"]["width"] == 4


def test_json_rpc_errors_and_notification(live):
    with ws(live) as c:
        c.send("{bad")
        assert json.loads(c.recv(timeout=1))["error"]["code"] == -32700
        c.send("[]")
        assert json.loads(c.recv(timeout=1))["error"]["code"] == -32600
        assert call(c, "missing")[0]["error"]["code"] == -32601
        c.send(json.dumps({"jsonrpc": "2.0", "method": "prefs.set", "params": {"zoom": 3}}))
        assert result(c, "prefs.get")["zoom"] == 3
        c.send(
            json.dumps(
                [
                    {"jsonrpc": "2.0", "id": 2, "method": "prefs.get"},
                    {"jsonrpc": "2.0", "method": "prefs.set", "params": {"zoom": 2}},
                ]
            )
        )
        replies = json.loads(c.recv(timeout=1))
        assert len(replies) == 1 and replies[0]["id"] == 2


def test_shared_watch_and_undo_to_revision(live):
    with ws(live) as first, ws(live) as second:
        for x in (1, 2):
            result(
                first,
                "op.apply",
                {
                    "op": "set_pixel",
                    "args": {
                        "layer": "L1",
                        "frame": 0,
                        "x": x,
                        "y": 1,
                        "color": 1,
                    },
                },
            )
            assert json.loads(second.recv(timeout=1))["params"]["revision"] == x
        result(first, "history.undo", {"to_revision": 0})
        assert load_project(live[2]).layers[0].cels == []
        assert json.loads(second.recv(timeout=1))["params"]["actor"] == "gui"
