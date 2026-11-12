"""Scenario 4: replay alternating real CLI processes and GUI WebSocket calls."""

import base64
import json
import subprocess
import sys

import numpy as np

from cybersprite.core.canonical import json_bytes, load_project
from cybersprite.core.hashing import pixel_sha256
from cybersprite.core.render import render
from tools.gui_test_support import connect_gui, rpc, running_gui


def replay_mixed(directory, root):
    calls = [
        json.loads(line) for line in (directory / "calls.jsonl").read_text("utf-8").splitlines()
    ]
    project = root / "shared.csprite"
    transcript = []
    notifications = []

    def revision(value):
        rev = value["revision"]
        return rev["after"] if isinstance(rev, dict) else rev

    def cli(arguments, expected=0):
        process = subprocess.run(
            [sys.executable, "-m", "cybersprite", *arguments],
            cwd=root,
            capture_output=True,
            encoding="utf-8",
            timeout=30,
        )
        assert process.returncode == expected, process.stderr + process.stdout
        return json.loads(process.stdout)

    created = cli(calls.pop(0)["arguments"])
    assert created["ok"]
    with running_gui(root, project) as (origin, token), connect_gui(origin, token) as connection:
        for call in calls:
            if call["surface"] == "cli":
                value = cli(call["arguments"], call.get("exit", 0))
                if call.get("notify"):
                    event = json.loads(connection.recv(timeout=3))
                    assert event["method"] == "project.changed", event
                    assert event["params"]["actor"] == "cli", event
                    assert event["params"]["revision"] == revision(value), event
                    notifications.append(event["params"]["revision"])
            else:
                raw_before = (project / "project.json").read_bytes()
                response, events = rpc(connection, call["method"], call.get("arguments"))
                notifications.extend(
                    e["params"]["revision"] for e in events if e["method"] == "project.changed"
                )
                if "error" in call:
                    assert response["error"]["data"]["code"] == call["error"], response
                    assert response["error"]["data"]["details"]["current_revision"] == 2
                    assert response["error"]["data"]["hint"]
                    assert (project / "project.json").read_bytes() == raw_before
                    transcript.append({"surface": "gui", "error": call["error"]})
                    continue
                assert "error" not in response, response
                value = response["result"]
                if call["method"] == "render.frame":
                    actual = np.frombuffer(
                        base64.b64decode(value["frames"][0]["rgba"]), dtype=np.uint8
                    ).reshape(8, 8, 4)
                    np.testing.assert_array_equal(actual, render(load_project(project)))
            assert value.get("ok", True), value
            if "validation" in value:
                assert value["validation"]["ok"], value
            if call.get("method") == "validate.run":
                assert value["result"]["ok"], value
                assert value["result"]["counts"]["error"] == 0
                assert value["result"]["counts"]["warning"] == 0
            if "revision" in call:
                assert revision(value) == call["revision"], value
            if value.get("op") == "export_image":
                assert value["result"]["verified"] and value["result"]["validation_ok"]
            transcript.append({"surface": call["surface"], "revision": revision(value)})
    from PIL import Image

    with Image.open(root / "shared.png") as image:
        actual = np.asarray(image.convert("RGBA"))
    np.testing.assert_array_equal(actual, render(load_project(project)))
    return {
        "project.json": (project / "project.json").read_bytes(),
        "pixels.json": json_bytes({"frames": [pixel_sha256(actual)]}),
        "exports.json": json_bytes({"shared.png": [pixel_sha256(actual)]}),
        "transcript.json": json_bytes(transcript),
    }, notifications
