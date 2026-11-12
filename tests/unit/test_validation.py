from copy import deepcopy

import pytest

from cybersprite.core.canonical import loads_project
from cybersprite.core.errors import CyberSpriteError
from cybersprite.core.models import ImageCel
from cybersprite.core.validation import check_structure, validation_report


def cel(**changes):
    return {"frame": 0, "x": 0, "y": 0, "w": 1, "h": 1, "pixels": ["01"], **changes}


def raw(project):
    return project.model_dump(by_alias=True)


def codes(project):
    return {issue.rule for issue in check_structure(project)}


def test_valid_appendix(appendix):
    assert not check_structure(appendix)
    assert validation_report(appendix)["ok"] is True
    assert validation_report(appendix)["metrics"]["linked_cels"] == 1


@pytest.mark.parametrize(
    ("rule", "mutate"),
    [
        ("S-01", lambda p: p.update(revision=True)),
        ("S-01", lambda p: p.update(unknown_field="x")),
        ("S-01", lambda p: p["canvas"].update(width=1.5)),
        ("S-01", lambda p: p["canvas"].update(pixel_ratio={"w": 2, "h": 2})),
        ("S-02", lambda p: p["layers"][0].update(cels=[cel(pixels=["ff"])])),
        ("S-03", lambda p: p["layers"][0].update(cels=[cel(w=2)])),
        ("S-03", lambda p: p["layers"][0].update(cels=[cel(h=2)])),
        ("S-04", lambda p: p["layers"][0].update(cels=[cel(frame=2)])),
        ("S-04", lambda p: p["layers"][0].update(cels=[cel(), cel()])),
        ("S-04", lambda p: p["layers"][0].update(cels=[cel(frame=1), cel(frame=0)])),
        ("S-05", lambda p: p["layers"][0].update(cels=[{"frame": 1, "link": 0, "z_index": 0}])),
        (
            "S-05",
            lambda p: p["layers"][0].update(
                cels=[{"frame": 0, "link": 1, "z_index": 0}, cel(frame=1)]
            ),
        ),
        ("S-06", lambda p: p["id_counters"].update(layer=0)),
        ("S-06", lambda p: p["layers"].append(deepcopy(p["layers"][0]))),
        ("S-07", lambda p: p.update(tags=[{"id": "T1", "name": "bad", "from": 1, "to": 0}])),
        (
            "S-08",
            lambda p: p.update(
                slices=[
                    {
                        "id": "S1",
                        "name": "bad",
                        "keys": [{"frame": 2, "x": 0, "y": 0, "w": 1, "h": 1}],
                    }
                ]
            ),
        ),
        (
            "S-09",
            lambda p: p.update(
                tilesets=[
                    {
                        "id": "TS1",
                        "name": "bad",
                        "tile_w": 1,
                        "tile_h": 1,
                        "tiles": [{"pixels": ["01"]}],
                    }
                ]
            ),
        ),
        (
            "S-10",
            lambda p: p["layers"].__setitem__(
                0, {"id": "L1", "name": "bad", "type": "tilemap", "tileset": "TS99", "cels": []}
            ),
        ),
        ("S-11", lambda p: p["layers"][0].update(background=True)),
        ("S-12", lambda p: p["canvas"].update(width=8193)),
        ("S-12", lambda p: p["canvas"].update(width=8192, height=8192)),
        ("S-13", lambda p: p["palette"].update(colors=[])),
        ("S-13", lambda p: p["palette"].update(transparent_index=99)),
        ("S-14", lambda p: p.update(frames=[])),
        ("S-14", lambda p: p.update(layers=[])),
    ],
)
def test_structural_invariants(project, rule, mutate):
    model = raw(project)
    mutate(model)
    issues = check_structure(model)
    assert rule in {issue.rule for issue in issues}
    assert all(issue.message and issue.hint for issue in issues)
    import json

    with pytest.raises(CyberSpriteError) as caught:
        loads_project(json.dumps(model))
    assert caught.value.code == "E_INVALID_PROJECT"
    assert rule in {issue["rule"] for issue in caught.value.details["issues"]}


def test_background_linked_frames_allowed(project):
    model = raw(project)
    model["layers"][0].update(
        background=True,
        cels=[cel(w=4, h=3, pixels=["00" * 4] * 3), {"frame": 1, "link": 0, "z_index": 0}],
    )
    assert not check_structure(model)


def test_link_chain_rejected(project):
    model = raw(project)
    model["frames"] *= 2
    model["layers"][0]["cels"] = [
        cel(),
        {"frame": 1, "link": 0, "z_index": 0},
        {"frame": 2, "link": 1, "z_index": 0},
    ]
    assert "S-05" in codes(model)


@pytest.mark.parametrize("token", ["0x", "2", "1yx", "-1", "01"])
def test_tile_refs_are_checked(project, token):
    model = raw(project)
    model["tilesets"] = [
        {
            "id": "TS1",
            "name": "test",
            "tile_w": 1,
            "tile_h": 1,
            "tiles": [{"pixels": ["00"]}, {"pixels": ["01"]}],
        }
    ]
    model["id_counters"]["tileset"] = 1
    model["layers"][0] = {
        "id": "L1",
        "name": "map",
        "type": "tilemap",
        "tileset": "TS1",
        "cels": [{k: v for k, v in cel(tiles=[token]).items() if k != "pixels"}],
    }
    assert "S-10" in codes(model)


def test_invalid_model_edit_is_revalidated(project):
    project.layers[0].cels = [ImageCel(frame=0, x=0, y=0, w=1, h=1, pixels=["01"])]
    project.layers[0].cels[0].opacity = 999
    assert "S-01" in codes(project)


def test_user_properties_depth(project):
    from cybersprite.core.models import UserData

    nested = {"leaf": 1}
    for _ in range(18):
        nested = {"more": nested}
    project.user_data = UserData(properties=nested)
    assert "S-01" in codes(project)


def test_deep_groups_limit(project):
    model = raw(project)
    layer = model["layers"][0]
    for i in range(2, 20):
        layer = {"id": f"L{i}", "name": "Group", "type": "group", "children": [layer]}
    model["layers"] = [layer]
    model["id_counters"]["layer"] = 19
    assert "S-12" in codes(model)


def test_name_limit_is_identified(project):
    project.name = "a" * 256
    assert "S-12" in codes(project)
