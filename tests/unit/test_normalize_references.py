import random

import numpy as np
import pytest

from cybersprite.core.canonical import dumps_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.models import (
    GroupLayer,
    ImageCel,
    ImageLayer,
    LinkCel,
    Tag,
    TileCel,
    TilemapLayer,
    Tileset,
)
from cybersprite.core.normalize import normalize_cels
from cybersprite.core.pixels import pixels_to_rows, resolve_color, tiles_from_rows, tiles_to_rows
from cybersprite.core.references import resolve_layer, resolve_tag


def test_trim_links_and_keep_offcanvas(project):
    project.layers[0].cels = [
        ImageCel(frame=0, x=-4, y=-3, w=3, h=3, pixels=["000000", "000100", "000000"]),
        LinkCel(frame=1, link=0, z_index=7),
    ]
    result = normalize_cels(project)
    owner = result.layers[0].cels[0]
    assert (owner.x, owner.y, owner.w, owner.h, owner.pixels) == (-3, -2, 1, 1, ["01"])
    assert result.layers[0].cels[1].link == 0
    assert result.layers[0].cels[1].z_index == 7
    assert project.layers[0].cels[0].w == 3


@pytest.mark.parametrize("in_place", [False, True])
def test_reassign_owner_and_chain(project, in_place):
    project.frames *= 2
    project.layers[0].cels = [
        LinkCel(frame=0, link=2, z_index=3),
        LinkCel(frame=1, link=0, z_index=7),
        ImageCel(frame=2, x=0, y=0, w=1, h=1, pixels=["01"], z_index=-1),
    ]
    result = normalize_cels(project, in_place=in_place)
    cels = result.layers[0].cels
    assert cels[0].frame == 0 and cels[0].pixels == ["01"] and cels[0].z_index == 3
    assert [(c.frame, c.link, c.z_index) for c in cels[1:]] == [(1, 0, 7), (2, 0, -1)]


def test_remove_empty_link_group(project):
    project.layers[0].cels = [
        ImageCel(frame=0, x=0, y=0, w=1, h=1, pixels=["00"]),
        LinkCel(frame=1, link=0),
    ]
    assert normalize_cels(project).layers[0].cels == []


def test_background_is_never_trimmed(project):
    project.layers[0].background = True
    project.layers[0].cels = [ImageCel(frame=0, x=0, y=0, w=4, h=3, pixels=["00" * 4] * 3)]
    assert normalize_cels(project) == project


def test_tile_normalization_moves_in_pixel_units(project):
    project.tilesets = [
        Tileset(
            id="TS1",
            name="tiles",
            tile_w=2,
            tile_h=3,
            tiles=[{"pixels": ["0000"] * 3}, {"pixels": ["0101"] * 3}],
        )
    ]
    project.layers = [
        TilemapLayer(
            id="L1",
            name="tiles",
            tileset="TS1",
            cels=[TileCel(frame=0, x=-4, y=-6, w=3, h=3, tiles=["0 0 0", "0 1xy 0", "0 0 0"])],
        )
    ]
    owner = normalize_cels(project).layers[0].cels[0]
    assert (owner.x, owner.y, owner.w, owner.h, owner.tiles) == (-2, -3, 1, 1, ["1xy"])


def test_random_normalization_idempotent(project):
    rng = random.Random(102)
    for _ in range(120):
        w, h = rng.randrange(1, 10), rng.randrange(1, 10)
        pixels = np.array(
            [[rng.choice([0, 0, 0, 1, 2]) for _ in range(w)] for _ in range(h)], dtype=np.uint8
        )
        project.layers[0].cels = [
            ImageCel(
                frame=0,
                x=rng.randrange(-10, 10),
                y=rng.randrange(-10, 10),
                w=w,
                h=h,
                pixels=pixels_to_rows(pixels),
            ),
            LinkCel(frame=1, link=0, z_index=rng.randrange(-5, 6)),
        ]
        once = normalize_cels(project)
        assert dumps_project(normalize_cels(once)) == dumps_project(once)


def test_layer_id_name_path_ambiguity(project):
    arm1 = ImageLayer(id="L2", name="Arm")
    arm2 = ImageLayer(id="L4", name="Arm")
    project.layers += [GroupLayer(id="L3", name="Body", children=[arm1]), arm2]
    assert resolve_layer(project, "L2") is arm1
    assert resolve_layer(project, "Body/Arm") is arm1
    with pytest.raises(CyberSpriteError) as caught:
        resolve_layer(project, "Arm")
    assert caught.value.code == "E_AMBIGUOUS_REF"
    assert caught.value.details["candidates"] == [
        {"id": "L2", "path": "Body/Arm"},
        {"id": "L4", "path": "Arm"},
    ]
    with pytest.raises(CyberSpriteError) as caught:
        resolve_layer(project, "Missing")
    assert caught.value.code == "E_LAYER_NOT_FOUND"


def test_tag_resolution_and_ids(project):
    a = Tag(id="T1", name="run", from_=0, to=1)
    b = Tag(id="T2", name="run", from_=0, to=0)
    project.tags = [a]
    assert resolve_tag(project, "run") is a
    project.tags.append(b)
    assert resolve_tag(project, "T2") is b
    with pytest.raises(CyberSpriteError) as caught:
        resolve_tag(project, "run")
    assert caught.value.code == "E_AMBIGUOUS_REF"
    project.id_counters.layer = 100
    assert [project.id_counters.issue("layer") for _ in range(3)] == ["L101", "L102", "L103"]


def test_color_resolution_never_quantizes(project):
    assert resolve_color(project.palette, 1) == 1
    assert resolve_color(project.palette, "#FFFFFF") == 2
    assert resolve_color(project.palette, "#00000000") == 0
    before = list(project.palette.colors)
    with pytest.raises(CyberSpriteError) as caught:
        resolve_color(project.palette, "#808080")
    assert caught.value.code == "E_COLOR_NOT_IN_PALETTE"
    # Appendix B makes mid-gray closer to white; alpha-zero is not a candidate.
    assert [entry["index"] for entry in caught.value.details["nearest"]] == [2, 1]
    assert project.palette.colors == before
    with pytest.raises(CyberSpriteError) as caught:
        resolve_color(project.palette, True)
    assert caught.value.code == "E_INVALID_ARGS"


def test_tile_roundtrip():
    rows = ["0 12 12x 5xy 7d 3xyd"]
    assert tiles_to_rows(tiles_from_rows(rows, 6, 1)) == rows
