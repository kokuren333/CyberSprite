"""Settings are user-owned, validated data; command execution is never accepted as tool input."""

import json

import pytest
from click.testing import CliRunner

from cybersprite.cli import cli
from cybersprite.config import config_path, load_config, reject_tool_configuration
from cybersprite.core.errors import CyberSpriteError


@pytest.fixture
def settings_path(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = config_path()
    path.parent.mkdir(parents=True)
    return path


def test_default_and_valid_settings(settings_path):
    assert load_config().generators.command == {}
    settings_path.write_text(
        '[generators.command.local]\nprogram = "C:/tools/generate.exe"\n'
        'args = ["--prompt", "{prompt}", "--out", "{out}"]\n'
        'license = "user supplied; see model card"\ntimeout_seconds = 300\n'
        '[generators.diffusers.models.local]\nid = "example/model"\nlicense = "Apache-2.0"\n'
        '[gui]\nport = 9010\nopen_browser = false\nlanguage = "en"\n'
        '[plugins]\nenabled = ["my-plugin"]\n',
        encoding="utf-8",
        newline="\n",
    )
    config = load_config()
    assert config.generators.command["local"].args[-1] == "{out}"
    assert config.gui.port == 9010 and config.gui.open_browser is False
    result = CliRunner().invoke(cli, ["doctor"])
    assert result.exit_code == 0
    report = json.loads(result.stdout)["result"]["config"]
    assert report == {
        "path": settings_path.as_posix(),
        "exists": True,
        "valid": True,
        "command_backends": ["local"],
        "models": ["local"],
        "enabled_plugins": ["my-plugin"],
    }
    assert "generate.exe" not in result.stdout


@pytest.mark.parametrize(
    "content",
    [
        "not [valid toml",
        "unknown = 1",
        '[gui]\nport = "9010"',
        "[gui]\nport = 99999",
        '[generators.command.x]\nprogram="run"\nargs=["{prompt.__class__}"]\nlicense="unknown"',
        '[generators.command.x]\nprogram="run"\nargs=["{out!r}"]\nlicense="unknown"',
        '[generators.command.x]\nprogram="run"\nargs=[]\nlicense=""',
        '[generators.command.x]\nprogram="run"\nargs=[]\nlicense="unknown"\nshell=true',
    ],
)
def test_invalid_config_is_actionable_json(settings_path, content):
    settings_path.write_text(content, "utf-8")
    with pytest.raises(CyberSpriteError) as error:
        load_config()
    assert error.value.code == "E_INVALID_ARGS"
    result = CliRunner().invoke(cli, ["doctor"])
    assert result.exit_code == 2 and not result.stderr
    assert json.loads(result.stdout)["error"]["details"]["path"] == settings_path.as_posix()


def test_platform_config_locations(tmp_path, monkeypatch):
    import cybersprite.config as config

    monkeypatch.setattr(config.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert config_path() == tmp_path / "xdg/cybersprite/config.toml"
    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.setattr(config.Path, "home", lambda: tmp_path)
    assert config_path() == tmp_path / ".config/cybersprite/config.toml"
    monkeypatch.setattr(config.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    assert config_path() == tmp_path / "roaming/cybersprite/config.toml"


@pytest.mark.parametrize(
    "args",
    [
        {"program": "run"},
        {"params": {"shell": True}},
        {"params": [{"local_path": "C:/model"}]},
        {"params": {"command": ["run"]}},
    ],
)
def test_tool_configuration_injection_is_rejected(args):
    with pytest.raises(CyberSpriteError, match="config.toml"):
        reject_tool_configuration(args)


def test_generation_hook_cannot_receive_command_definition(settings_path, monkeypatch):
    import sys
    import types

    from cybersprite.ops import registry

    # Load the shared contracts before replacing the optional runtime package.
    registry()
    called = []
    module = types.ModuleType("cybersprite.generate")
    module.generate_image = lambda **kwargs: called.append(kwargs)
    monkeypatch.setitem(sys.modules, module.__name__, module)
    result = CliRunner().invoke(
        cli,
        [
            "gen",
            "run",
            "--params",
            '{"command":"injected"}',
        ],
    )
    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "E_INVALID_ARGS"
    assert called == []
