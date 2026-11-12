"""Keep scenario 4/5 output files for engineering inspection after E2E replay."""

import argparse
import asyncio
import json
from pathlib import Path

from tests.e2e.mixed_replay import replay_mixed
from tests.e2e.replay import SCENARIOS, replay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    summary = {}
    for scenario in ("scenario4", "scenario5"):
        root = args.out.resolve() / scenario
        root.mkdir()
        case = SCENARIOS / scenario
        if scenario == "scenario4":
            outputs, transcript = replay_mixed(case, root)
        else:
            outputs, transcript = asyncio.run(replay(case, root, stdio=True, exports=True))
        for name, data in outputs.items():
            assert data == (case / "expected" / name).read_bytes(), (scenario, name)
        summary[scenario] = transcript
    (args.out / "session.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
