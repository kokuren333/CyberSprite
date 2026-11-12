"""Launch without depending on the optional CLI wiring."""

import argparse

from .server import serve


def main():
    parser = argparse.ArgumentParser(description="Serve CyberSprite registry tools over MCP.")
    parser.add_argument("--root")
    parser.add_argument("--allow-dir", action="append", default=[])
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--profile", choices=["standard", "minimal"], default="standard")
    parser.add_argument("--enable-generation", action="store_true")
    parser.add_argument("--allow-plugin-op", action="append", default=[])
    parser.add_argument("--read-only", action="store_true")
    serve(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()
