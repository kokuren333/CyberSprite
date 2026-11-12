"""Loopback GUI harness shared by E2E and performance measurements."""

import json
import socket
import threading
import time
from contextlib import contextmanager


@contextmanager
def running_gui(root, project=None, static=None):
    import uvicorn

    from cybersprite.server.app import create_app

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
    token = "local-test-token"
    app = create_app(root=root, project=project, token=token, origin=origin, static=static)
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="on"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    try:
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("GUI server did not start within 10 seconds.")
            time.sleep(0.01)
        yield origin, token
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()
        if thread.is_alive():
            raise RuntimeError("GUI server did not stop within 10 seconds.")


def connect_gui(origin, token):
    from websockets.sync.client import connect

    return connect(
        origin.replace("http:", "ws:") + "/ws",
        origin=origin,
        subprotocols=["cybersprite", token],
        proxy=None,
    )


def rpc(connection, method, params=None):
    connection.send(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})
    )
    events = []
    while True:
        response = json.loads(connection.recv(timeout=10))
        if "method" in response:
            events.append(response)
        else:
            return response, events
