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

    for command in (
        "start",
        "settings",
        "onboarding",
        "tui",
        "doctor",
        "bridge",
        "server",
        "control-plane",
        "vault",
        "session",
        "memory",
        "canvas",
    ):
        arguments = [command, "status"] if command in {"control-plane", "vault", "memory", "canvas"} else [command]
        if command == "session":
            arguments = [command, "list"]
        parsed = parser.parse_args(arguments)
        assert parsed.command == command


def test_destructive_cli_commands_require_explicit_confirmation(tmp_path):
    for runner, args, message in (
        (
            trinity_cli.run_memory_command,
            SimpleNamespace(
                memory_action="reset",
                memory_id=None,
                limit=50,
                yes=False,
                no_backup=False,
                include_generated=False,
                include_canvas=False,
            ),
            "--yes",
        ),
        (
            trinity_cli.run_session_command,
            SimpleNamespace(
                session_action="delete",
                session_id="session-test",
                title="",
                workspace="_inbox",
                mode="chat",
                limit=50,
                archive=False,
                yes=False,
            ),
            "--yes",
        ),
    ):
        (tmp_path / "core").mkdir(exist_ok=True)
        try:
            runner(tmp_path, args)
        except ValueError as exc:
            assert message in str(exc)
        else:
            raise AssertionError("Destructive command must require confirmation")


def test_surface_settings_force_terminal_without_graphical_ui():
    config = {"system": {}}
    answers = iter(["none"])

    trinity_cli._configure_surfaces(
        config,
        input_fn=lambda _prompt: next(answers),
    )

    assert config["system"]["terminal_cli_enabled"] is True


def test_surface_settings_accept_web_ui_without_terminal():
    config = {"system": {}}

    trinity_cli._configure_surfaces(config, input_fn=lambda _prompt: "web")

    assert config["system"]["web_ui_enabled"] is True
    assert config["system"]["terminal_cli_enabled"] is False


def test_control_plane_onboarding_records_runtime_and_brainvault(tmp_path):
    home = tmp_path / "Trinity"
    runtime = home / "local-runtime"
    brainvault = tmp_path / "brainvault"
    agents = tmp_path / "agents-root"
    config = {}
    answers = iter(
        ["privat", "ja", str(runtime), str(brainvault), "ja", str(agents), "pi"]
    )

    trinity_cli._configure_control_plane(
        config,
        home,
        input_fn=lambda _prompt: next(answers),
    )

    assert config["control_plane"]["enabled"] is True
    assert config["system"]["profile"] == "PRIVAT"
    assert config["control_plane"]["runtime_root"] == str(runtime)
    assert config["control_plane"]["vault_root"] == str(brainvault)
    assert config["control_plane"]["brainvault_root"] == str(agents)
    assert config["control_plane"]["external_agents_root"] == str(agents)
    assert config["control_plane"]["default_brainvault_harness"] == "pi"
    assert (brainvault / "10 Aktive Projekte").is_dir()


def test_vault_init_reuses_saved_location_without_duplicate_content(tmp_path):
    home = tmp_path / "Trinity"
    core = home / "core"
    core.mkdir(parents=True)
    vault = tmp_path / "BrainVault"
    existing = vault / "Bestehendes Projekt"
    existing.mkdir(parents=True)
    (existing / "inhalt.md").write_text("bleibt", encoding="utf-8")
    save_config(
        core / "config.json",
        {
            "system": {"profile": "PRIVAT"},
            "control_plane": {
                "runtime_root": str(home / "TrinityRuntime"),
                "vault_root": str(vault),
            },
        },
    )

    result = trinity_cli.run_vault_command(
        home,
        SimpleNamespace(
            vault_action="init",
            root="",
            profile="",
            accept_existing=False,
        ),
    )

    assert result == 0
    assert (existing / "inhalt.md").read_text(encoding="utf-8") == "bleibt"
    assert (vault / "10 Aktive Projekte").is_dir()


def test_control_plane_reuses_known_vault_without_asking_for_it_again(tmp_path):
    home = tmp_path / "Trinity"
    runtime = home / "TrinityRuntime"
    vault = tmp_path / "BrainVault"
    agents = tmp_path / "agents"
    config = {
        "system": {"profile": "PRIVAT"},
        "control_plane": {"vault_root": str(vault)},
    }
    prompts = []
    answers = iter(["privat", "ja", str(runtime), str(agents), "pi"])

    def answer(prompt):
        prompts.append(prompt)
        return next(answers)

    trinity_cli._configure_control_plane(config, home, input_fn=answer)

    assert config["control_plane"]["vault_root"] == str(vault.resolve())
    assert not any("Speicherort des Inhalts-Vaults" in prompt for prompt in prompts)
    assert (vault / "10 Aktive Projekte").is_dir()


def test_noninteractive_vault_setup_requires_acceptance_for_existing_data(tmp_path):
    home = tmp_path / "Trinity"
    (home / "core").mkdir(parents=True)
    vault = tmp_path / "Existing"
    vault.mkdir()
    (vault / "datei.txt").write_text("wichtig", encoding="utf-8")

    args = SimpleNamespace(
        vault_action="setup",
        root=str(vault),
        profile="privat",
        accept_existing=False,
    )
    try:
        trinity_cli.run_vault_command(home, args)
    except ValueError as exc:
        assert "--accept-existing" in str(exc)
    else:
        raise AssertionError("Existing content must require explicit acceptance")


def test_interactive_vault_setup_asks_for_profile_and_location(tmp_path):
    home = tmp_path / "Trinity"
    (home / "core").mkdir(parents=True)
    vault = tmp_path / "Mein BrainVault"
    answers = iter(["privat", str(vault), "ja"])

    result = trinity_cli.run_vault_command(
        home,
        SimpleNamespace(
            vault_action="setup",
            root="",
            profile="",
            accept_existing=False,
        ),
        input_fn=lambda _prompt: next(answers),
    )
    config = load_config(home / "core" / "config.json")

    assert result == 0
    assert config["system"]["profile"] == "PRIVAT"
    assert config["control_plane"]["vault_root"] == str(vault.resolve())
    assert (vault / "10 Aktive Projekte").is_dir()


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


def test_server_uses_saved_server_settings(tmp_path, monkeypatch):
    import trinity_server

    home = tmp_path
    (home / "core").mkdir()
    (home / "trinity_launcher.py").touch()
    save_config(home / "core" / "config.json", {"server": {"host": "0.0.0.0", "port": 8888, "token": "secret"}})
    captured = {}
    monkeypatch.setattr(trinity_server, "run_server", lambda home_arg, host, port, token: captured.update({"home": home_arg, "host": host, "port": port, "token": token}) or 0)

    result = trinity_cli.run_server_command(home, SimpleNamespace(host=None, port=None, token=None))

    assert result == 0
    assert captured == {"home": home, "host": "0.0.0.0", "port": 8888, "token": "secret"}
