import json

from configuration import (
    is_harness_active,
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
    assert first["companion"]["enabled"] is False
    assert first["companion"]["port"] == 8765
    assert first["harness_routing"]["frameworks"]["trinity"]["roles"][
        "agent_execution"
    ] is True
    assert first["goose"]["enabled"] is False
    assert first["harness_routing"]["frameworks"]["goose"]["active"] is False
    assert first["harness_routing"]["agent_assignments"]["trinity-core"] == [
        "trinity"
    ]
    assert first["agent_catalog"]["agents"]["agent-builder"]["quality_status"] == "testing"


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


def test_legacy_enabled_harnesses_seed_roles_once(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "codex": {"enabled": True},
                "opencode": {"enabled": True},
                "pi": {"enabled": True},
            }
        ),
        encoding="utf-8",
    )

    config = load_config(path, platform_name="Linux")
    frameworks = config["harness_routing"]["frameworks"]

    assert frameworks["codex"]["roles"]["agent_builder"] is True
    assert frameworks["codex"]["roles"]["agent_execution"] is True
    assert frameworks["trinity"]["roles"]["agent_execution"] is True
    assert frameworks["opencode"]["roles"]["agent_execution"] is True
    assert frameworks["pi"]["roles"]["agent_execution"] is True


def test_existing_harness_roles_are_not_overwritten_by_enabled_flags(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "codex": {"enabled": True},
                "harness_routing": {
                    "frameworks": {
                        "codex": {
                            "label": "Codex",
                            "roles": {
                                "agent_builder": False,
                                "complex_cases": False,
                                "agent_execution": False,
                            },
                        }
                    },
                    "agent_assignments": {},
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_config(path, platform_name="Linux")
    roles = config["harness_routing"]["frameworks"]["codex"]["roles"]

    assert roles["agent_builder"] is False
    assert roles["complex_cases"] is False
    assert roles["agent_execution"] is False
    assert config["harness_routing"]["agent_assignments"] == {}


def test_harness_master_switch_migrates_from_legacy_enabled_flag(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"goose": {"enabled": True}}), encoding="utf-8")

    config = load_config(path, platform_name="Linux")

    assert is_harness_active(config, "goose") is True
    assert config["harness_routing"]["frameworks"]["goose"]["active"] is True


def test_explicit_harness_master_switch_overrides_enabled_flag(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "goose": {"enabled": True},
                "harness_routing": {"frameworks": {"goose": {"active": False}}},
            }
        ),
        encoding="utf-8",
    )

    config = load_config(path, platform_name="Linux")

    assert is_harness_active(config, "goose") is False
