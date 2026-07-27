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
    assert first["llm"]["local"]["enable_thinking"] is False
    assert first["llm"]["local"]["request_timeout_seconds"] == 120
    assert first["harness_routing"]["frameworks"]["trinity"]["roles"][
        "agent_execution"
    ] is True
    assert "goose" not in first
    assert "goose" not in first["harness_routing"]["frameworks"]
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


def test_legacy_goose_settings_are_adopted_by_opencode(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "goose": {
                    "enabled": True,
                    "projects": {"Lehre": "/tmp/lehre"},
                    "default_project": "Lehre",
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_config(path, platform_name="Linux")

    assert "goose" not in config
    assert "goose" not in config["harness_routing"]["frameworks"]
    assert config["opencode"]["enabled"] is True
    assert config["opencode"]["projects"] == {"Lehre": "/tmp/lehre"}
    assert is_harness_active(config, "opencode") is True


def test_legacy_goose_projects_extend_existing_opencode_projects(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "opencode": {
                    "enabled": False,
                    "projects": {"BrainVault": "/tmp/brain"},
                    "default_project": "BrainVault",
                },
                "goose": {
                    "enabled": True,
                    "projects": {
                        "BrainVault": "/tmp/legacy-brain",
                        "Agenten": "/tmp/agents",
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_config(path, platform_name="Linux")

    assert config["opencode"]["enabled"] is True
    assert config["opencode"]["default_project"] == "BrainVault"
    assert config["opencode"]["projects"] == {
        "BrainVault": "/tmp/brain",
        "Agenten": "/tmp/agents",
    }


def test_legacy_goose_assignments_migrate_to_opencode(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "goose": {"enabled": True},
                "control_plane": {
                    "default_brainvault_harness": "goose",
                    "builder_harness": "goose",
                },
                "harness_routing": {
                    "frameworks": {"goose": {"active": True}},
                    "agent_assignments": {
                        "skills.example": ["trinity", "goose"],
                        "legacy-goose-agent": ["trinity", "goose"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_config(path, platform_name="Linux")

    assert config["harness_routing"]["agent_assignments"]["skills.example"] == [
        "trinity",
        "opencode",
    ]
    assert "legacy-goose-agent" not in config["harness_routing"]["agent_assignments"]
    assert config["control_plane"]["default_brainvault_harness"] == "opencode"
    assert config["control_plane"]["builder_harness"] == "opencode"
