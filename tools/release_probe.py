"""Run from a fresh wheel-only environment, without repository imports or Node."""

import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def lines(process, stream=None):
    pending = queue.Queue()

    def reader():
        for line in stream if stream is not None else process.stdout:
            pending.put(line)
        pending.put(None)

    threading.Thread(target=reader, daemon=True).start()
    return pending


def stop(process):
    process.terminate()
    try:
        process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=5)


def handshake(command, version):
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    )
    pending = lines(process)

    def send(value):
        process.stdin.write(json.dumps(value) + "\n")
        process.stdin.flush()

    def response(request_id):
        deadline = time.monotonic() + 20
        while True:
            raw = pending.get(timeout=max(0.01, deadline - time.monotonic()))
            assert raw is not None, "MCP closed stdout before replying."
            value = json.loads(raw)
            if value.get("id") == request_id:
                assert "error" not in value, value
                return value["result"]

    try:
        meta = {
            "io.modelcontextprotocol/protocolVersion": version,
            "io.modelcontextprotocol/clientCapabilities": {},
            "io.modelcontextprotocol/clientInfo": {"name": "release-probe", "version": "1"},
        }
        if version == "2026-07-28":
            send(
                {"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {"_meta": meta}}
            )
            discovered = response(1)
            assert version in json.dumps(discovered)
        else:
            send(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": version,
                        "capabilities": {},
                        "clientInfo": {"name": "release-probe", "version": "1"},
                    },
                }
            )
            initialized = response(1)
            assert initialized["protocolVersion"] == version, initialized
            send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {"_meta": meta} if version == "2026-07-28" else {},
            }
        )
        listing = response(2)
        names = {tool["name"] for tool in listing["tools"]}
        assert {"new_project", "set_pixel", "validate", "export_image"} <= names
        return {"protocol": version, "tools": len(names)}
    finally:
        stop(process)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    import cybersprite

    installed = Path(cybersprite.__file__).resolve()
    assert not installed.is_relative_to(args.repo.resolve()), installed
    assert not os.environ.get("PYTHONPATH")
    executable = Path(sys.executable).parent / (
        "cybersprite.exe" if os.name == "nt" else "cybersprite"
    )
    results = {"installed": str(installed), "python": sys.version.split()[0]}

    def run(*arguments):
        completed = subprocess.run(
            [str(executable), *arguments],
            check=True,
            capture_output=True,
            encoding="utf-8",
            timeout=60,
        )
        return completed.stdout

    def cli(*arguments):
        value = json.loads(run(*arguments))
        assert value["ok"], value
        return value

    results["version"] = run("--version").strip()
    cli("new", "release.csprite", "--size", "8x8", "--palette", "gray-4", "--frames", "2")
    changed = cli(
        "-p",
        "release.csprite",
        "op",
        "rect",
        "--args",
        json.dumps(
            {"layer": "L1", "frame": 0, "x": 2, "y": 2, "w": 4, "h": 4, "color": 1, "filled": True}
        ),
    )
    assert changed["validation"]["ok"]
    assert changed["preview"]["paths"]
    validated = cli("-p", "release.csprite", "validate")
    assert validated["result"]["ok"]
    cli(
        "-p",
        "release.csprite",
        "preview",
        "--frames",
        "all",
        "--layout",
        "strip",
        "--out",
        "preview.png",
    )
    exported = cli(
        "-p", "release.csprite", "export", "image", "--out", "final.png", "--frames", "0"
    )
    assert exported["result"]["verified"] and exported["result"]["validation_ok"]
    import numpy as np
    from PIL import Image

    from cybersprite.core.canonical import load_project
    from cybersprite.core.render import render

    with Image.open("final.png") as image:
        np.testing.assert_array_equal(
            np.asarray(image.convert("RGBA")), render(load_project("release.csprite"))
        )
    cli("convert", "final.png", "converted.png", "--preset", "exact")
    cli("schema", "all", "--out", "schemas")
    results["cli"] = {"validation_ok": True, "verified": True, "pipeline_and_schemas": True}
    help_result = subprocess.run(
        [sys.executable, "-m", "cybersprite.mcp", "--help"],
        capture_output=True,
        check=True,
        text=True,
        timeout=20,
    )
    assert "--root" in help_result.stdout
    results["mcp"] = [
        {"entry": entry, **handshake(command, protocol)}
        for entry, command in [
            ("module", [sys.executable, "-m", "cybersprite.mcp", "--root", str(Path.cwd())]),
            ("cli", [str(executable), "mcp", "serve", "--root", str(Path.cwd())]),
        ]
        for protocol in ("2025-06-18", "2026-07-28")
    ]
    server = subprocess.Popen(
        [str(executable), "gui", "release.csprite", "--no-browser"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        url = lines(server, server.stderr).get(timeout=20).strip()
        address = urlsplit(url)
        origin = f"{address.scheme}://{address.netloc}"

        def get(path, cookie=None):
            return urlopen(
                Request(origin + path, headers={"Cookie": cookie} if cookie else {}), timeout=5
            )

        deadline = time.monotonic() + 10
        while True:
            try:
                get("/").close()
                break
            except OSError:
                assert time.monotonic() < deadline
                time.sleep(0.05)
        try:
            get("/app")
            raise AssertionError("GUI index was served without authentication.")
        except HTTPError as error:
            assert error.code == 403
        with urlopen(
            Request(
                origin + "/auth",
                method="POST",
                headers={"Origin": origin, "Authorization": "Bearer " + address.fragment},
            ),
            timeout=5,
        ) as auth:
            cookie = auth.headers["Set-Cookie"].split(";", 1)[0]
        with get("/app", cookie) as index:
            html = index.read().decode("utf-8")
        static = installed.parent / "server/static"
        assert html == (static / "index.html").read_text("utf-8")
        assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html)
        assert any(p.endswith(".js") for p in assets) and any(p.endswith(".css") for p in assets)
        for asset in [*assets, "/icons/settings.png"]:
            with get(asset, cookie) as response:
                assert response.status == 200
                actual = response.read()
                assert actual and actual == (static / asset.lstrip("/")).read_bytes()
        results["gui"] = {
            "authenticated_index": True,
            "assets": assets,
            "asset_bytes_verified": True,
            "icon": True,
        }
    finally:
        stop(server)
    args.out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(results))


if __name__ == "__main__":
    main()
