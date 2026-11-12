"""The core dependency audit covers package-relative imports as well as absolute ones."""

from tools import check_repository


def test_relative_imports_cannot_escape_core(tmp_path, monkeypatch):
    core = tmp_path / "src/cybersprite/core"
    core.mkdir(parents=True)
    sources = {
        "allowed.py": "from .models import Project\nimport numpy as np\n",
        "plugin.py": "from ..plugins import PluginManager\n",
        "format.py": "from ..formats.png import encode_png\n",
        "parent.py": "from .. import plugins\n",
    }
    for name, contents in sources.items():
        (core / name).write_text(contents, encoding="utf-8", newline="\n")
    monkeypatch.setattr(check_repository, "ROOT", tmp_path)
    monkeypatch.setattr(check_repository.subprocess, "check_output", lambda *a, **kw: b"")
    errors = check_repository.violations()
    assert len(errors) == 3
    assert sum("cybersprite.plugins" in error for error in errors) == 2
    assert any("cybersprite.formats.png" in error for error in errors)
