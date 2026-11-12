"""Confinement and contracts of the integrated formats/pipeline tools."""

from pathlib import Path

import pytest

pytest.importorskip("mcp.server")
from jsonschema import Draft202012Validator  # noqa: E402

from cybersprite.mcp.contracts import MINIMAL  # noqa: E402
from cybersprite.mcp.server import MCPService  # noqa: E402

CORPUS = Path(__file__).resolve().parents[1] / "pipeline/corpus/originals/hero_16x16.png"


@pytest.mark.parametrize("profile", ["standard", "minimal"])
def test_m6_profiles_and_batch_cleanup(tmp_path, profile):
    (tmp_path / "input.png").write_bytes(CORPUS.read_bytes())
    service = MCPService(root=tmp_path, profile=profile)
    for name in ("import_image", "list_sources", "get_source", "cleanup_pixels"):
        assert (name in service.exposed) == (profile == "standard" or name in MINIMAL)
    value = service.call(
        "import_image",
        {
            "project": "p",
            "files": ["input.png"],
            "preset": "exact",
            "provenance": {"license": "unknown"},
            "preview": "inline",
        },
    )
    assert not value.is_error, value.structured_content
    Draft202012Validator(service.contracts["import_image"]["outputSchema"]).validate(
        value.structured_content
    )
    layer = value.structured_content["result"]["placed"]["layer"]
    assert not service.call(
        "apply_ops", {"project": "p", "ops": [{"op": "cleanup_pixels", "args": {"layer": layer}}]}
    ).is_error


def test_export_root_allow_dir_and_input_escapes(tmp_path):
    root, extra = tmp_path / "root", tmp_path / "extra"
    root.mkdir()
    extra.mkdir()
    (extra / "input.png").write_bytes(CORPUS.read_bytes())
    service = MCPService(root=root)
    assert not service.call("new_project", {"project": "p", "width": 16, "height": 16}).is_error
    before = (root / "p/project.json").read_bytes()
    for out in ("../escape.png", str(extra / "blocked.png")):
        result = service.call("export_image", {"project": "p", "out": out})
        assert result.structured_content["error"]["code"] == "E_PATH_NOT_ALLOWED"
    for files in ("../extra/input.png", [str(extra / "input.png")]):
        result = service.call(
            "import_image",
            {
                "project": "p",
                "files": files,
                "preset": "exact",
                "provenance": {"license": "unknown"},
            },
        )
        assert result.structured_content["error"]["code"] == "E_PATH_NOT_ALLOWED"
    result = service.call(
        "import_image",
        {
            "project": "p",
            "files": "input.png",
            "pipeline": {"palette": {"mode": "fixed", "source": "../outside.hex"}},
            "provenance": {"license": "unknown"},
        },
    )
    assert result.structured_content["error"]["code"] == "E_PATH_NOT_ALLOWED"
    assert before == (root / "p/project.json").read_bytes()
    service = MCPService(root=root, allow_dir=[extra])
    exported = service.call("export_image", {"project": "p", "out": "../extra/allowed.png"})
    assert not exported.is_error, exported.structured_content
    assert exported.structured_content["result"]["files"][0]["path"] == "../extra/allowed.png"
    assert (extra / "allowed.png").is_file()
    relative = service.call("export_image", {"project": "p", "out": "local.png"})
    assert not relative.is_error
    assert relative.structured_content["result"]["files"][0]["path"] == "local.png"
    assert (root / "local.png").is_file() and not (root / "p/local.png").exists()
    imported = service.call(
        "import_image",
        {
            "project": "other",
            "files": "../extra/input.png",
            "preset": "exact",
            "provenance": {"license": "unknown"},
        },
    )
    assert not imported.is_error, imported.structured_content


def test_aseprite_quantization_palette_path_is_confined(tmp_path):
    service = MCPService(root=tmp_path)
    result = service.call(
        "import_aseprite",
        {
            "project": "p",
            "file": "input.aseprite",
            "quantize": {"mode": "fixed", "source": "../outside.hex"},
        },
    )
    assert result.structured_content["error"]["code"] == "E_PATH_NOT_ALLOWED"
    assert not (tmp_path / "p/project.json").exists()
