"""GUI generation requires explicit service enablement before execution."""

import pytest

pytest.importorskip("starlette")
from cybersprite import ops  # noqa: E402
from cybersprite.core.errors import CyberSpriteError  # noqa: E402
from cybersprite.server.app import Service  # noqa: E402


def test_gui_generation_opt_in(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        ops,
        "execute",
        lambda *args, **kw: calls.append(args)
        or {"ok": True, "project": str(tmp_path / "p"), "result": {"sources": [], "files": []}},
    )
    with pytest.raises(CyberSpriteError, match="--enable-generation"):
        Service(tmp_path).run_op("generate_image", tmp_path / "p", {})
    assert not calls
    Service(tmp_path, enable_generation=True).run_op("generate_image", tmp_path / "p", {})
    assert len(calls) == 1
