from pathlib import Path

import numpy as np
import pytest

from cybersprite.formats.png import decode_png
from tools.golden_cases import execute_case

CASES = sorted((Path(__file__).parent / "golden").glob("*/case.json"))


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.parent.name)
def test_golden_case(case):
    outputs = execute_case(case.parent)
    expected = case.parent / "expected"
    assert sorted(outputs) == sorted(path.name for path in expected.iterdir())
    for name, data in sorted(outputs.items()):
        assert data == (expected / name).read_bytes(), f"{case.parent.name}/{name}"
        if name.endswith(".stored.png"):
            image = decode_png(data)
            import json

            pixels = json.loads(outputs[name.replace(".stored.png", ".pixels.json")])
            np.testing.assert_array_equal(image.pixels, np.array(pixels, dtype=np.uint8))
