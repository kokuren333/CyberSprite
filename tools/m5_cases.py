"""Authored engineering fixtures for format interoperability; no external artwork."""

from cybersprite.core.models import (
    GroupLayer,
    ImageCel,
    ImageLayer,
    LinkCel,
    Slice,
    SliceKey,
    Tag,
    Tile,
    TileCel,
    TilemapLayer,
    Tileset,
    UserData,
)
from cybersprite.core.normalize import normalize_cels
from cybersprite.core.projects import new_project


def animated_project():
    p = new_project(
        width=8,
        height=6,
        frames=3,
        name="M5 fixture",
        palette=["#00000000", "#102030ff", "#abcdefff", "#f04020ff"],
    )
    p.frames[0].duration_ms = 35
    p.frames[1].duration_ms = 60
    p.frames[2].duration_ms = 100
    p.palette.names = {"0": "Clear", "1": "Dark", "2": "Light"}
    ud = UserData(
        text="Authored format fixture",
        color="#12345678",
        properties={
            "bool": True,
            "count": 9,
            "large": 1 << 40,
            "null": None,
            "mixed": [1, "two", False, {"nested": {"$type": "uint16", "value": 65535}}],
            "$ext": {"test.extension": {"value": {"$type": "int8", "value": -4}}},
            "point": {"$type": "point", "value": {"x": -2, "y": 3}},
            "rect": {"$type": "rect", "value": [1, 2, 3, 4]},
            "size": {"$type": "size", "value": [3, 4]},
            "uuid": {"$type": "uuid", "value": "01234567-89ab-cdef-0123-456789abcdef"},
            **{
                kind: {"$type": kind, "value": value}
                for kind, value in (
                    ("int8", -12),
                    ("uint8", 250),
                    ("int16", -300),
                    ("uint16", 60000),
                    ("int32", -70000),
                    ("uint32", 1 << 31),
                    ("int64", -(1 << 40)),
                    ("uint64", 1 << 63),
                    ("fixed", 65536),
                    ("float", 2),
                    ("double", 3),
                )
            },
        },
    )
    p.user_data = ud
    p.palette.frozen = True
    layer = ImageLayer(
        id="L2",
        name="Cells",
        locked=True,
        continuous=True,
        user_data=UserData(properties={"$ase": {"lock_movement": True}}),
        cels=[
            ImageCel(frame=0, x=1, y=1, w=2, h=2, pixels=["0102", "0201"], user_data=ud),
            ImageCel(frame=1, x=3, y=2, w=2, h=2, z_index=-1, pixels=["0302", "0203"]),
            LinkCel(frame=2, link=0, z_index=1),
        ],
    )
    p.layers = [
        GroupLayer(id="L1", name="Group", collapsed=True, user_data=ud, children=[layer]),
        ImageLayer(id="L3", name="Empty", visible=False),
    ]
    p.tags = [
        Tag(
            id="T1",
            name="Motion",
            **{"from": 0},
            to=2,
            direction="pingpong",
            repeat=3,
            color="#112233",
            user_data=ud,
        )
    ]
    p.slices = [
        Slice(
            id="S1",
            name="Region",
            color="#66778899",
            user_data=ud,
            keys=[
                SliceKey(
                    frame=0,
                    x=0,
                    y=0,
                    w=6,
                    h=5,
                    center=dict(x=1, y=1, w=2, h=2),
                    pivot=dict(x=-1, y=2),
                ),
                SliceKey(frame=2, x=1, y=0, w=6, h=5),
            ],
        )
    ]
    p.id_counters.layer, p.id_counters.tag, p.id_counters.slice = 3, 1, 1
    return normalize_cels(p)


def tile_project():
    p = new_project(
        width=16,
        height=2,
        name="M5 tile flips",
        palette=["#00000000", "#102030ff", "#abcdefff", "#f04020ff"],
    )
    ud = UserData(
        text="Eight flip combinations", properties={"id": {"$type": "uint32", "value": 7}}
    )
    p.tilesets = [
        Tileset(
            id="TS1",
            name="Two tiles",
            tile_w=2,
            tile_h=2,
            base_index=-2,
            match_flips=dict(x=True, y=True, d=True),
            user_data=ud,
            tiles=[Tile(pixels=["0000", "0000"]), Tile(pixels=["0102", "0300"], user_data=ud)],
        )
    ]
    p.layers = [
        TilemapLayer(
            id="L1",
            name="All flips",
            tileset="TS1",
            continuous=True,
            user_data=ud,
            cels=[
                TileCel(
                    frame=0, x=0, y=0, w=8, h=1, tiles=["1 1x 1y 1xy 1d 1xd 1yd 1xyd"], user_data=ud
                )
            ],
        )
    ]
    p.id_counters.tileset = 1
    return normalize_cels(p)
