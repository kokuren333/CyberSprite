"""Measure tools/list definitions with the review's JSON serialization, three times."""

import json
from statistics import median

from cybersprite.mcp.server import MCPService


def main():
    for profile in ("standard", "minimal"):
        runs = []
        wire = []
        count = 0
        for _ in range(3):
            tools = [
                tool.model_dump(by_alias=True, exclude_none=True)
                for tool in MCPService(profile=profile).tools()
            ]
            count = len(tools)
            runs.append(len(json.dumps(tools).encode("utf-8")))
            wire.append(len(json.dumps(tools, separators=(",", ":")).encode("utf-8")))
        print(
            json.dumps(
                dict(
                    profile=profile,
                    tools=count,
                    bytes=runs,
                    median=median(runs),
                    compact_bytes=wire,
                )
            )
        )


if __name__ == "__main__":
    main()
