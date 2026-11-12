"""First-import undo leaves a usable transparent-only project for a retry."""

import numpy as np

from cybersprite.core.canonical import load_project
from cybersprite.core.render import render
from cybersprite.formats.png import encode_png
from cybersprite.ops import execute


def test_import_autocreates_and_reimports_after_undo(tmp_path):
    source = tmp_path / "source.png"
    image = np.full((4, 4, 4), [235, 30, 50, 255], dtype=np.uint8)
    source.write_bytes(encode_png(image))
    project = tmp_path / "not-created.csprite"
    args = {"files": str(source), "preset": "exact", "provenance": {"license": "CC0-1.0"}}
    first = execute("import_image", project, args, preview="none")
    assert first["result"]["accepted"]
    p = load_project(project)
    assert (p.canvas.width, p.canvas.height) == (4, 4)
    np.testing.assert_array_equal(render(p), image)
    execute("undo", project, {}, preview="none")
    assert load_project(project).palette.colors == ["#00000000"]
    second = execute("import_image", project, args, preview="none")
    assert second["result"]["accepted"]
    np.testing.assert_array_equal(render(load_project(project)), image)
    execute("undo", project, {}, preview="none")
    retried = execute(
        "import_image", project, {"source": "SRC1", "preset": "exact"}, preview="none"
    )
    assert retried["result"]["accepted"]
    np.testing.assert_array_equal(render(load_project(project)), image)
