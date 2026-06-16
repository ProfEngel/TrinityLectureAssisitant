from types import SimpleNamespace

import trinity_cli
from configuration import (
    load_config,
    parse_setting_value,
    save_config,
    set_config_value,
)


def _modules():
    return {
        "ensure_support_files": lambda _home: [],
        "load_config": load_config,
        "parse_setting_value": parse_setting_value,
        "save_config": save_config,
        "set_config_value": set_config_value,
    }


def test_cli_exposes_requested_commands():
    parser = trinity_cli.build_parser()

    for command in ("start", "settings", "onboarding", "tui", "doctor", "bridge"):
        parsed = parser.parse_args([command])
        assert parsed.command == command


def test_surface_settings_force_terminal_without_graphical_ui():
    config = {"system": {}}
    answers = iter(["none"])

    trinity_cli._configure_surfaces(
        config,
        input_fn=lambda _prompt: next(answers),
    )

    assert config["system"]["terminal_cli_enabled"] is True


def test_direct_cli_setting_updates_shared_config(tmp_path, monkeypatch):
    home = tmp_path
    (home / "core").mkdir()
    (home / "trinity_launcher.py").touch()
    monkeypatch.setattr(trinity_cli, "_core_modules", lambda _home: _modules())
    args = SimpleNamespace(
        gui=False,
        show=False,
        set_values=[
            "system.classic_ui_enabled=true",
            "persona.agent_name=Nova",
        ],
    )

    result = trinity_cli.run_settings(home, args)
    config = load_config(home / "core" / "config.json")

    assert result == 0
    assert config["system"]["classic_ui_enabled"] is True
    assert config["persona"]["agent_name"] == "Nova"


def test_start_passes_temporary_surface_to_launcher(tmp_path, monkeypatch):
    captured = {}
    (tmp_path / "trinity_launcher.py").touch()

    def fake_call(command, cwd):
        captured["command"] = command
        captured["cwd"] = cwd
        return 0

    monkeypatch.setattr(trinity_cli.subprocess, "call", fake_call)

    result = trinity_cli.run_start(
        tmp_path,
        SimpleNamespace(surface="terminal"),
    )

    assert result == 0
    assert captured["command"][-2:] == ["--surface", "terminal"]
    assert captured["cwd"] == str(tmp_path)


def test_bridge_uses_saved_companion_settings(tmp_path, monkeypatch):
    import trinity_bridge

    home = tmp_path
    (home / "core").mkdir()
    (home / "trinity_launcher.py").touch()
    save_config(
        home / "core" / "config.json",
        {
            "companion": {
                "enabled": True,
                "host": "0.0.0.0",
                "port": 9999,
                "token": "secret",
            }
        },
    )
    captured = {}

    def fake_run_bridge(home_arg, host, port, token):
        captured.update(
            {
                "home": home_arg,
                "host": host,
                "port": port,
                "token": token,
            }
        )
        return 0

    monkeypatch.setattr(trinity_bridge, "run_bridge", fake_run_bridge)

    result = trinity_cli.run_bridge_command(
        home,
        SimpleNamespace(host=None, port=None, token=None),
    )

    assert result == 0
    assert captured == {
        "home": home,
        "host": "0.0.0.0",
        "port": 9999,
        "token": "secret",
    }
