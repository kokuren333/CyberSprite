"""Generate initial shared playback vectors from the export core, or check their bytes.

Existing vectors with different bytes are never overwritten. Review a mismatch
before updating expectations through tools/update_goldens.py.
"""

import argparse
import json
from pathlib import Path

from cybersprite.core.models import Tag
from cybersprite.core.projects import new_project
from cybersprite.formats.common import animation_sequence

DESTINATION = Path(__file__).resolve().parents[1] / "tests/vectors/playback/sequences.json"
DIRECTIONS = ("forward", "reverse", "pingpong", "pingpong_reverse")
DURATIONS = (37, 83, 127, 211, 307, 419, 523, 631)
INFINITE_CYCLES = 3


def build_vectors() -> bytes:
    """Keep nonzero tag bounds, unequal durations, and the cycle seam explicit."""
    project = new_project(width=1, height=1, frames=len(DURATIONS))
    for frame, duration in zip(project.frames, DURATIONS, strict=True):
        frame.duration_ms = duration
    cases = []
    for direction in DIRECTIONS:
        for length in (1, 2, 3, 4):
            for repeat in (0, 1, 2, 3):
                tag = Tag(
                    id="T1",
                    name="playback",
                    **{"from": 2, "to": length + 1},
                    direction=direction,
                    repeat=repeat,
                )
                project.tags = [tag]
                loop = 0 if repeat == 0 else 1
                sequence = animation_sequence(project, tag=tag.id, loop=loop)
                observed = sequence * (INFINITE_CYCLES if repeat == 0 else 1)
                cases.append(
                    {
                        "name": f"{direction}_length_{length}_repeat_{repeat}",
                        "input": {
                            "tag": tag.model_dump(
                                by_alias=True,
                                include={"id", "name", "from_", "to", "direction", "repeat"},
                            ),
                            "durations_ms": list(DURATIONS),
                            "loop": loop,
                            "cycles": INFINITE_CYCLES if repeat == 0 else 1,
                        },
                        "expected": {
                            "sequence": sequence,
                            "durations_ms": [project.frames[i].duration_ms for i in sequence],
                            "observed_sequence": observed,
                            "observed_durations_ms": [
                                project.frames[i].duration_ms for i in observed
                            ],
                        },
                    }
                )
    return (json.dumps({"cases": cases}, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check bytes without writing files.")
    args = parser.parse_args()
    data = build_vectors()
    if DESTINATION.exists():
        if DESTINATION.read_bytes() != data:
            parser.exit(1, "Playback vectors differ; review before updating expectations.\n")
    elif args.check:
        parser.exit(1, "Playback vectors are missing; run tools/gen_playback_vectors.py.\n")
    else:
        DESTINATION.parent.mkdir(parents=True, exist_ok=True)
        DESTINATION.write_bytes(data)
    print(f"{'Checked' if args.check else 'Generated'} 64 playback cases.")


if __name__ == "__main__":
    main()
