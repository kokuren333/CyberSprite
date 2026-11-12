import itertools
import json
import random
from pathlib import Path

import numpy as np
import pytest

from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.models import (
    GroupLayer,
    ImageCel,
    ImageLayer,
    LinkCel,
    TileCel,
    TilemapLayer,
    Tileset,
)
from cybersprite.core.pixels import pixels_to_rows, rgba
from cybersprite.core.projects import new_project
from cybersprite.core.render import indexed_result, mul255, render, render_indexed, source_over

VECTORS = json.loads((Path(__file__).parents[1] / "vectors/compositing.json").read_bytes())


@pytest.mark.parametrize("case", VECTORS["cases"], ids=lambda c: c["name"])
def test_compositing_vectors(case):
    result = source_over(
        np.array(case["source"], dtype=np.uint8), np.array(case["destination"], dtype=np.uint8)
    )
    assert result.tolist() == case["expected"]


@pytest.mark.parametrize(("a", "b", "expected"), VECTORS["mul255"])
def test_mul255_vectors(a, b, expected):
    assert mul255(a, b) == expected


def test_half_blend_hand_calculation():
    # Ra=128+round(128*127/255)=192. Red rounds from 32640/192=170.
    # Blue rounds from (128*127)/192=84+2/3 to 85.
    assert source_over(
        np.array([255, 0, 0, 128], dtype=np.uint8), np.array([0, 0, 255, 128], dtype=np.uint8)
    ).tolist() == [170, 0, 85, 192]


def image(id="L1", index=1, **changes):
    return ImageLayer(
        id=id,
        name=id,
        cels=[ImageCel(frame=0, x=0, y=0, w=1, h=1, pixels=[f"{index:02x}"])],
        **changes,
    )


def test_opacity_group_order_and_fallback():
    project = new_project(width=1, height=1)
    project.palette.colors = ["#00000000", "#ff0000ff"]
    bottom = image(opacity=129, blend_mode="multiply")
    bottom.cels[0].opacity = 128
    project.layers = [
        GroupLayer(
            id="L3",
            name="grand",
            opacity=131,
            blend_mode="screen",
            children=[GroupLayer(id="L2", name="parent", opacity=130, children=[bottom])],
        )
    ]
    warnings = []
    result = render(project, warnings=warnings)
    # 128*129 -> 65; 65*130 ->33; 33*131 ->17 (all mul255 rounding).
    assert result[0, 0].tolist() == [255, 0, 0, 17]
    assert warnings[0]["code"] == "W_BLEND_FALLBACK" and warnings[0]["layers"] == ["L1"]


def test_groups_count_in_z_order_and_tie_breaks():
    project = new_project(width=1, height=1)
    a, b, c = image(), image("L3", index=2), image("L4")
    project.layers = [a, GroupLayer(id="L2", name="group", children=[b]), c]
    a.cels[0].z_index = 2  # key (2,2); child B: (2,0), so A is above B.
    assert render_indexed(project)[0, 0] == 1  # C remains highest at order 3.
    c.cels[0].z_index = -3  # key(0,-3); A now highest, validates z tie sorting.
    assert render_indexed(project)[0, 0] == 1
    a.cels[0].z_index = 1  # key(1,1) below B at (2,0).
    assert render_indexed(project)[0, 0] == 2


def test_hidden_ancestors_and_layers_filter():
    project = new_project(width=1, height=1)
    project.layers = [
        image(),
        GroupLayer(id="L2", name="Group", visible=False, children=[image("L3", index=2)]),
    ]
    assert render_indexed(project)[0, 0] == 1
    assert render_indexed(project, options={"include_hidden": True})[0, 0] == 2
    assert render_indexed(project, options={"layers": ["L2"]})[0, 0] == 0
    assert render_indexed(project, options={"layers": ["L2"], "include_hidden": True})[0, 0] == 2
    assert render_indexed(project, options={"layers": []})[0, 0] == 0


def test_links_use_owner_data_and_independent_z():
    project = new_project(width=1, height=1, frames=2)
    a, b = image(), image("L2", index=2)
    a.cels.append(LinkCel(frame=1, link=0, z_index=2))
    b.cels.append(LinkCel(frame=1, link=0))
    project.layers = [a, b]
    assert render_indexed(project, 0)[0, 0] == 2
    assert render_indexed(project, 1)[0, 0] == 1


def test_offcanvas_crop_scale_ratio(project):
    project.canvas.pixel_ratio.w = 2
    project.layers[0].cels = [
        ImageCel(frame=0, x=-1, y=-1, w=3, h=3, pixels=["010101", "010202", "010201"])
    ]
    output = render_indexed(
        project,
        options={"crop": {"x": 0, "y": 0, "w": 2, "h": 2}, "scale": 2, "apply_pixel_ratio": True},
    )
    assert output.tolist() == [[2] * 8, [2] * 8, [2] * 4 + [1] * 4, [2] * 4 + [1] * 4]


def test_background_layer_and_export_palette():
    project = new_project(width=1, height=1)
    project.palette.colors = ["#11223300", "#ff000080"]
    project.layers = [image(index=0, background=True)]
    output = indexed_result(project)
    assert output.pixels[0, 0] == 0
    assert output.palette[0] == "#112233ff"
    assert render(project)[0, 0].tolist() == [17, 34, 51, 255]
    assert project.palette.colors[0] == "#11223300"
    project.layers[0].cels[0].pixels = ["01"]
    assert indexed_result(project).palette[1] == "#ff0000ff"
    project.layers.append(image("L2", index=1))
    with pytest.raises(CyberSpriteError):
        render_indexed(project)


def test_transparent_index_skips_even_if_opaque_rgb():
    project = new_project(width=1, height=1)
    project.palette.colors[0] = "#ffff00ff"
    project.layers = [image(index=0)]
    assert render(project)[0, 0].tolist() == [0, 0, 0, 0]
    assert indexed_result(project).palette[0] == "#00000000"


def test_background_option():
    project = new_project(width=1, height=1)
    assert render(project, options={"background": "#123456"})[0, 0].tolist() == [18, 52, 86, 255]
    assert render_indexed(project, options={"background": 2})[0, 0] == 2
    with pytest.raises(CyberSpriteError) as caught:
        render_indexed(project, options={"background": "#123456"})
    assert caught.value.code == "E_NOT_PALETTE_CLOSED"


@pytest.mark.parametrize(
    "options",
    [
        {"scale": 0},
        {"scale": 65},
        {"scale": 1.5},
        {"flatten": "other"},
        {"crop": {"x": -1, "y": 0, "w": 1, "h": 1}},
    ],
)
def test_bad_render_options(project, options):
    with pytest.raises(CyberSpriteError):
        render(project, options=options)


def test_strict_opacity_palette_alpha_and_nearest():
    project = new_project(width=1, height=1)
    project.palette.colors = ["#00000000", "#000000ff", "#ffffffff", "#ffffff80"]
    project.layers = [image(index=3)]
    with pytest.raises(CyberSpriteError) as caught:
        render_indexed(project)
    assert caught.value.code == "E_NOT_PALETTE_CLOSED"
    assert caught.value.details["causes"][0]["colors"] == [3]
    assert render_indexed(project, options={"flatten": "nearest"})[0, 0] == 2
    project.layers[0].cels[0].opacity = 127
    assert render_indexed(project, options={"flatten": "nearest"})[0, 0] == 0


def test_nearest_tie_uses_lowest_index():
    project = new_project(width=1, height=1)
    project.palette.colors = ["#00000000", "#000000ff", "#020000ff", "#01000080"]
    project.layers = [image(index=3)]
    assert render_indexed(project, options={"flatten": "nearest"})[0, 0] == 1


EXPECTED_TRANSFORMS = [
    [[1, 2], [3, 4]],
    [[1, 3], [2, 4]],
    [[3, 4], [1, 2]],
    [[2, 4], [1, 3]],
    [[2, 1], [4, 3]],
    [[3, 1], [4, 2]],
    [[4, 3], [2, 1]],
    [[4, 2], [3, 1]],
]


@pytest.mark.parametrize(
    ("flags", "expected"),
    list(zip(itertools.product((False, True), repeat=3), EXPECTED_TRANSFORMS, strict=True)),
)
def test_all_eight_tile_transforms(flags, expected):
    x, y, d = flags
    project = new_project(width=2, height=2)
    project.palette.colors = ["#00000000", "#110000ff", "#220000ff", "#330000ff", "#440000ff"]
    project.tilesets = [
        Tileset(
            id="TS1",
            name="tiles",
            tile_w=2,
            tile_h=2,
            tiles=[{"pixels": ["0000", "0000"]}, {"pixels": ["0102", "0304"]}],
        )
    ]
    token = "1" + ("x" if x else "") + ("y" if y else "") + ("d" if d else "")
    project.layers = [
        TilemapLayer(
            id="L1",
            name="map",
            tileset="TS1",
            cels=[TileCel(frame=0, x=0, y=0, w=1, h=1, tiles=[token])],
        )
    ]
    assert render_indexed(project).tolist() == expected


def test_non_square_diagonal_is_ignored():
    project = new_project(width=2, height=1)
    project.tilesets = [
        Tileset(
            id="TS1",
            name="tiles",
            tile_w=2,
            tile_h=1,
            tiles=[{"pixels": ["0000"]}, {"pixels": ["0102"]}],
        )
    ]
    project.layers = [
        TilemapLayer(
            id="L1",
            name="map",
            tileset="TS1",
            cels=[TileCel(frame=0, x=0, y=0, w=1, h=1, tiles=["1xd"])],
        )
    ]
    assert render_indexed(project).tolist() == [[2, 1]]


def test_random_closed_consistency():
    rng = random.Random(103)
    for _ in range(80):
        project = new_project(width=4, height=3)
        project.palette.colors = ["#00000000"] + [
            "#" + bytes(rng.randrange(256) for _ in range(3)).hex() + "ff" for _ in range(8)
        ]
        layers = []
        for i in range(rng.randrange(1, 6)):
            pixels = np.array(
                [[rng.randrange(9) for _ in range(3)] for _ in range(2)], dtype=np.uint8
            )
            layer = ImageLayer(
                id=f"L{i + 1}",
                name=f"L{i + 1}",
                visible=bool(rng.randrange(2)),
                cels=[
                    ImageCel(
                        frame=0,
                        x=rng.randrange(-2, 3),
                        y=rng.randrange(-1, 2),
                        w=3,
                        h=2,
                        pixels=pixels_to_rows(pixels),
                        z_index=rng.randrange(-4, 5),
                    )
                ],
            )
            layers.append(layer)
        project.layers = layers
        indexed = indexed_result(project)
        lookup = np.array([rgba(c) for c in indexed.palette], dtype=np.uint8)[indexed.pixels]
        np.testing.assert_array_equal(render(project), lookup)
