"""Replay the same calls in-process or over a real stdio MCP connection."""

import asyncio
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from mcp import Client, StdioServerParameters
from mcp.types import Implementation

from cybersprite.core.canonical import json_bytes, load_project
from cybersprite.core.hashing import pixel_sha256
from cybersprite.core.render import render
from cybersprite.mcp.server import create_server

SCENARIOS = Path(__file__).parent / "scenarios"


async def replay(directory, root, *, stdio=False, exports=False):
    case = json.loads((directory / "case.json").read_bytes())
    for destination, original in case.get("inputs", {}).items():
        path = root / destination
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((Path(__file__).resolve().parents[2] / original).read_bytes())
    server = (
        StdioServerParameters(
            command=sys.executable,
            args=["-m", "cybersprite.mcp", "--root", str(root)],
        )
        if stdio
        else create_server(root=root)
    )
    transcript = []
    async with Client(
        server, client_info=Implementation(name="scenario-1", version="1"), mode="2026-07-28"
    ) as client:
        tools = {tool.name for tool in (await client.list_tools()).tools}
        for line in (directory / "calls.jsonl").read_text("utf-8").splitlines():
            call = json.loads(line)
            if call["name"].startswith("export_") and not exports:
                continue
            if call["name"] not in tools:
                raise LookupError(
                    f"{call['name']} is not registered; merge M5 to enable export steps"
                )
            result = await client.call_tool(call["name"], call["arguments"])
            value = result.structured_content
            assert not result.is_error, value
            assert value["ok"], value
            for key, expected in call.get("expect", {}).items():
                assert value["result"][key] == expected, value
            if call["name"] == "validate":
                assert value["result"]["ok"]
            if call["name"].startswith("export_"):
                assert value["result"]["validation_ok"]
                assert value["result"]["verified"]
            transcript.append(
                {
                    "op": call["name"],
                    "revision": value["revision"],
                    "images": sum(item.type == "image" for item in result.content),
                    **(
                        {"accepted": value["result"]["accepted"]}
                        if "accepted" in value["result"]
                        else {}
                    ),
                }
            )
    project_dir = root / case["project"]
    project = load_project(project_dir)
    frames = [render(project, frame) for frame in range(len(project.frames))]
    result = {
        "project.json": (project_dir / "project.json").read_bytes(),
        "pixels.json": json_bytes(
            {
                "frames": [pixel_sha256(frame) for frame in frames],
                "sheet": pixel_sha256(np.concatenate(frames, axis=1)),
            }
        ),
    }
    if exports:
        # Decode the actual output files, not a pre-export preview.
        from PIL import Image

        hashes = {}
        for filename, kind in case.get(
            "exports", {"walk.png": "sheet", "walk.gif": "animation"}
        ).items():
            with Image.open(root / filename) as image:
                actual = []
                for index in range(getattr(image, "n_frames", 1)):
                    image.seek(index)
                    actual.append(pixel_sha256(np.asarray(image.convert("RGBA"))))
                expected = (
                    [case["pixel_hashes"][filename]]
                    if kind == "tileset"
                    else [pixel_sha256(np.concatenate(frames, axis=1))]
                    if kind == "sheet"
                    else [pixel_sha256(frame) for frame in frames]
                )
                assert actual == expected, (filename, actual, expected)
                hashes[filename] = actual
        result["exports.json"] = json_bytes(hashes)
    return result, transcript


def execute_case(directory):
    with TemporaryDirectory() as temporary:
        result, _ = asyncio.run(replay(directory, Path(temporary), exports=True))
        return result


if __name__ == "__main__":
    # All golden writes still pass through the repository's sole updater.
    from tools import update_goldens

    update_goldens.ROOT = SCENARIOS
    update_goldens.execute_case = execute_case
    update_goldens.main()
