import json

from configuration import (
    load_config,
    parse_setting_value,
    save_config,
    set_config_value,
)


def test_missing_config_uses_independent_defaults(tmp_path):
    first = load_config(tmp_path / "missing.json", platform_name="Linux")
    second = load_config(tmp_path / "missing.json", platform_name="Linux")

    first["persona"]["trigger_variants"].append("changed")

    assert "changed" not in second["persona"]["trigger_variants"]
    assert first["system"]["eyes_ui_enabled"] is False
    assert first["system"]["classic_ui_enabled"] is True


def test_config_round_trip_and_dotted_setting(tmp_path):
    path = tmp_path / "config.json"
    config = load_config(path, platform_name="Linux")
    set_config_value(config, "system.classic_ui_enabled", True)
    set_config_value(config, "persona.agent_name", "Trinität")
    save_config(path, config)

    saved = json.loads(path.read_text(encoding="utf-8"))

    assert saved["system"]["classic_ui_enabled"] is True
    assert saved["persona"]["agent_name"] == "Trinität"


def test_setting_values_are_parsed_for_cli_use():
    assert parse_setting_value("true") is True
    assert parse_setting_value("42") == 42
    assert parse_setting_value('["classic", "terminal"]') == [
        "classic",
        "terminal",
    ]
    assert parse_setting_value("plain text") == "plain text"
