"""Profile warmed transaction and GUI dispatch paths without fixture/import costs."""

import argparse
import cProfile
import json
import pstats
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from cybersprite import ops
from cybersprite.core.projects import create_project
from cybersprite.server.app import Service
from tools.bench import fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("build/fix5-profile"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as folder:
        root = Path(folder)
        for mode, size, layers, frames in (("transaction", 64, 10, 32), ("gui", 128, 1, 1)):
            project = root / f"{mode}.csprite"
            create_project(project, fixture(size, layers, frames))
            ops.execute("get_info", project, {"include": ["summary"]})
            service = Service(root)
            session = SimpleNamespace(project=project)
            service.scan(project)
            profiler = cProfile.Profile()
            for i in range(3):
                values = {
                    "layer": f"L{layers}",
                    "frame": 0,
                    "x": 1,
                    "y": 1,
                    "color": 2 if i % 2 == 0 else 1,
                    "preview": "path" if mode == "transaction" else "none",
                }
                profiler.enable()
                if mode == "transaction":
                    ops.execute("set_pixel", project, values)
                else:
                    result = service.dispatch(
                        session, "op.apply", {"op": "set_pixel", "args": values}
                    )
                    json.dumps(result)
                    json.dumps(service.scan(project))
                    json.dumps(service.dispatch(session, "render.frame", {"frame": 0}))
                profiler.disable()
            profiler.dump_stats(args.out / f"{mode}.prof")
            with (args.out / f"{mode}.txt").open("w", encoding="utf-8", newline="\n") as stream:
                pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats(
                    "cumulative"
                ).print_stats(45)
            print((args.out / f"{mode}.txt").read_text("utf-8"))


if __name__ == "__main__":
    main()
