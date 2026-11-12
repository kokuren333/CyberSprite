"""Tilemap binary round trips retain flags, resource metadata, and nonzero transparency."""

from copy import deepcopy

import numpy as np
import pytest

from cybersprite.core.models import MatchFlips, Tile, TileCel, TilemapLayer, Tileset, UserData
from cybersprite.core.render import render
from cybersprite.formats.aseprite_io import decode_aseprite, encode_aseprite, equivalent
from tools.m7_cases import tile_project


@pytest.mark.parametrize("base_index", [-1, 0, 7])
@pytest.mark.parametrize("square", [False, True])
@pytest.mark.parametrize("transparent", [0, 2])
def test_all_flags_multiple_tilesets_linked_metadata_roundtrip(base_index, square, transparent):
    p = tile_project(square=square)
    if transparent:
        p.palette.transparent_index = transparent
        for tile in p.tilesets[0].tiles:
            tile.pixels = [row.replace("00", "02") for row in tile.pixels]
    ts = p.tilesets[0]
    ud = UserData(
        text="tile metadata", color="#12345678", properties={"kind": "test", "solid": True}
    )
    ts.base_index = base_index
    ts.match_flips = MatchFlips(x=True, y=True, d=True)
    ts.user_data = deepcopy(ud)
    ts.tiles[0].user_data = deepcopy(ud)
    ts.tiles[1].user_data = deepcopy(ud)
    p.layers[0].user_data = deepcopy(ud)
    p.layers[0].cels[0].user_data = deepcopy(ud)
    p.tilesets.append(
        Tileset(
            id="TS2",
            name="Other dimensions",
            tile_w=1,
            tile_h=2,
            tiles=[Tile(pixels=[f"{transparent:02x}"] * 2), Tile(pixels=["01", "03"])],
            base_index=base_index + 1,
            match_flips=MatchFlips(y=True),
        )
    )
    p.id_counters.tileset = 2
    p.layers.append(
        TilemapLayer(
            id="L2",
            name="Other map",
            tileset="TS2",
            cels=[TileCel(frame=0, x=0, y=0, w=1, h=1, tiles=["1yd"])],
            user_data=deepcopy(ud),
        )
    )
    p.id_counters.layer = 2
    raw = encode_aseprite(p)
    q, dropped = decode_aseprite(raw)
    assert not dropped
    assert equivalent(p, q)
    assert q.tilesets == p.tilesets
    assert q.layers == p.layers
    assert encode_aseprite(q) == raw
    for frame in range(2):
        np.testing.assert_array_equal(render(p, frame), render(q, frame))
