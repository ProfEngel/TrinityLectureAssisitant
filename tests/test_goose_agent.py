import importlib.util
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "agents" / "goose_agent" / "script.py"


def _load_agent():
    spec = importlib.util.spec_from_file_location("goose_agent_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _enabled_config(project):
    return {
        "goose": {
            "enabled": True,
            "projects": {"Sandbox": str(project)},
            "default_project": "Sandbox",
            "arguments": ["run", "--no-session", "--quiet", "--text", "{prompt}"],
        },
        "harness_routing": {"frameworks": {"goose": {"active": True}}},
    }


def test_goose_requires_an_explicit_trigger():
    agent = _load_agent()

    assert agent.can_handle("Trinity, nutze Goose im Projekt Sandbox.")
    assert agent.can_handle("Starte den Goose-Agent fuer einen Test.")
    assert not agent.can_handle("Was ist eine Gans?")


def test_goose_runs_in_the_selected_project(monkeypatch, tmp_path):
    agent = _load_agent()
    project = tmp_path / "Sandbox"
    project.mkdir()
    captured = {}
    monkeypatch.setattr(agent, "_resolve_executable", lambda _value: "/usr/local/bin/goose")

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="Goose fertig.", stderr="")

    monkeypatch.setattr(agent.subprocess, "run", fake_run)
    config = _enabled_config(project)

    result = agent.execute(
        "Trinity, nutze Goose im Projekt Sandbox und pruefe die Regeln.",
        {"goose_cfg": config["goose"], "full_config": config},
    )

    assert result["has_payload"] is False
    assert result["direct_answer"].endswith("Goose fertig.")
    assert captured["command"][:5] == [
        "/usr/local/bin/goose",
        "run",
        "--no-session",
        "--quiet",
        "--text",
    ]
    assert captured["kwargs"]["cwd"] == str(project.resolve())
    assert captured["kwargs"]["env"]["TRINITY_PROJECT_ALIAS"] == "Sandbox"


def test_goose_master_switch_blocks_execution(tmp_path):
    agent = _load_agent()
    project = tmp_path / "Sandbox"
    project.mkdir()
    config = _enabled_config(project)
    config["harness_routing"]["frameworks"]["goose"]["active"] = False

    result = agent.execute(
        "Trinity, nutze Goose im Projekt Sandbox.",
        {"goose_cfg": config["goose"], "full_config": config},
    )

    assert "noch nicht aktiviert" in result["direct_answer"]
