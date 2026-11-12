"""Author synthetic engineering fixtures; expectations are written only by update_goldens."""

from pathlib import Path

from cybersprite.core.canonical import dumps_project, json_bytes
from cybersprite.core.models import ImageCel, LinkCel, Tile, TileCel, TilemapLayer, Tileset
from cybersprite.core.projects import new_project

PALETTE = ["#00000000", "#880000ff", "#008800ff", "#000088ff"]
GLYPH = ["010000", "020000", "030302"]
FLAGS = ["", "x", "y", "xy", "d", "xd", "yd", "xyd"]


def tile_project(*, square=True):
    p = new_project(width=27, height=9, frames=2, palette=PALETTE, name="M7 tiles")
    h = 3 if square else 2
    p.tilesets = [
        Tileset(
            id="TS1",
            name="Glyphs",
            tile_w=3,
            tile_h=h,
            tiles=[Tile(pixels=["000000"] * h), Tile(pixels=GLYPH[:h])],
        )
    ]
    p.id_counters.tileset = 1
    p.layers = [
        TilemapLayer(
            id="L1",
            name="Map",
            tileset="TS1",
            cels=[
                TileCel(frame=0, x=1, y=2, w=8, h=1, tiles=[" ".join("1" + f for f in FLAGS)]),
                LinkCel(frame=1, link=0),
            ],
        )
    ]
    return p


def prepare_inputs():
    root = Path(__file__).resolve().parents[1] / "tests/golden"
    cases = {}
    for square in (True, False):
        name = "m7_eight_flips" if square else "m7_rectangular_flips"
        p = tile_project(square=square)
        cases[name] = (
            p,
            {
                "renders": [
                    {
                        "name": "flip_" + (flag or "none"),
                        "indexed": True,
                        "options": {"crop": dict(x=1 + i * 3, y=2, w=3, h=3 if square else 2)},
                    }
                    for i, flag in enumerate(FLAGS)
                ]
            },
        )
    cases["m7_renumber"] = (
        tile_project(),
        {
            "transactions": [
                {
                    "op": "set_tile_pixels",
                    "args": {"tileset": "TS1", "tile": "new", "rows": ["020202"] * 3},
                },
                {
                    "op": "set_tile_pixels",
                    "args": {"tileset": "TS1", "tile": 1, "rows": ["010000", "020000", "030301"]},
                },
                {"op": "move_tiles", "args": {"tileset": "TS1", "from": 2, "to": 2, "before": 1}},
                {"op": "delete_tiles", "args": {"tileset": "TS1", "tiles": [1]}},
            ],
            "renders": [{"frame": 0, "indexed": True}, {"frame": 1, "indexed": True}],
            "exports": [
                {
                    "name": "tiles",
                    "op": "export_tileset",
                    "args": {
                        "tileset": "TS1",
                        "out": "tiles.png",
                        "data_out": "tiles.json",
                        "compression": "stored",
                    },
                }
            ],
        },
    )
    p = new_project(width=9, height=6, frames=2, palette=PALETTE, name="M7 conversion")
    p.layers[0].cels = [
        ImageCel(
            frame=0,
            x=1,
            y=2,
            w=7,
            h=3,
            pixels=["01020102020103", "03000300000300", "01010101010101"],
        ),
        LinkCel(frame=1, link=0),
    ]
    cases["m7_from_layer"] = (
        p,
        {
            "transactions": [
                {
                    "op": "tileset_from_layer",
                    "args": {
                        "layer": "L1",
                        "tile_w": 2,
                        "tile_h": 2,
                        "match_flips": {"x": True, "y": True, "d": True},
                    },
                }
            ],
            "renders": [{"frame": 0, "indexed": True}, {"frame": 1, "indexed": True}],
        },
    )
    for name, (project, case) in cases.items():
        directory = root / name
        directory.mkdir(exist_ok=True)
        (directory / "project.json").write_bytes(dumps_project(project))
        (directory / "case.json").write_bytes(json_bytes(case))


if __name__ == "__main__":
    prepare_inputs()
