from types import SimpleNamespace

import trinity_tui
from configuration import load_config, save_config


def test_tui_slash_commands_manage_memory_and_sessions(tmp_path, monkeypatch):
    home = tmp_path
    (home / "core").mkdir()
    save_config(home / "core" / "config.json", {"llm": {"active_slot": "local", "local": {"model": "demo", "url": "http://localhost"}}})
    output = []

    tui = trinity_tui.TrinityTui(
        home,
        input_fn=lambda _prompt: "/exit",
        output_fn=output.append,
    )
    tui.handle_command("/remember Momora Memory Graph --tags momora,memory")
    tui.handle_command("/memory search Momora")
    tui.handle_command("/session new Test")

    assert any("Gespeichert" in line for line in output)
    assert any("Momora Memory Graph" in line for line in output)
    assert any("Neue Session" in line for line in output)


def test_tui_model_command_switches_slot(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    save_config(
        home / "core" / "config.json",
        {
            "llm": {
                "active_slot": "local",
                "local": {"model": "local-model", "url": "http://localhost"},
                "remote_1": {"model": "remote-model", "url": "https://example.test"},
            }
        },
    )
    output = []
    tui = trinity_tui.TrinityTui(home, output_fn=output.append)

    tui.handle_command("/model remote_1 better-model")

    config = load_config(home / "core" / "config.json")
    assert config["llm"]["active_slot"] == "remote_1"
    assert config["llm"]["remote_1"]["model"] == "better-model"
