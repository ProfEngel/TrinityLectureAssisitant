import importlib.util
import json
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "agents" / "pi_agent" / "script.py"


def _load_agent():
    spec = importlib.util.spec_from_file_location("pi_agent_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pi_requires_explicit_agent_trigger():
    agent = _load_agent()

    assert agent.can_handle("Trinity, nutze Pi für diese Aufgabe")
    assert agent.can_handle("Trinity, frage Pi dazu")
    assert agent.can_handle("Trinity, starte den Pi-Agent")
    assert agent.can_handle("Trinity, frag Pi nach Erendria")
    assert agent.can_handle("Bitte pi darum alle Ordner in BrainVault aufzulisten")
    assert agent.can_handle("Hi Trinity, welche Fähigkeiten hast Du?")
    assert agent.can_handle("Trinity, gibt es einen Mail-Agenten?")
    assert agent.can_handle("Ist da auch das Projekt Erendria?")
    assert not agent.can_handle("Trinity, was ist die Kreiszahl Pi?")


def test_run_pi_uses_stdin_when_no_prompt_placeholder(monkeypatch):
    agent = _load_agent()
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="Pi antwortet.", stderr="")

    monkeypatch.setattr(agent.subprocess, "run", fake_run)

    answer = agent._run_pi(
        executable="/usr/local/bin/pi",
        arguments=["chat", "--stdin"],
        prompt="Frage",
        timeout=120,
        project_path=None,
        project_alias="",
    )

    assert answer == "Pi antwortet."
    assert captured["command"] == ["/usr/local/bin/pi", "chat", "--stdin"]
    assert captured["kwargs"]["input"] == "Frage"
    assert captured["kwargs"]["shell"] is False


def test_run_pi_can_pass_prompt_as_argument(monkeypatch):
    agent = _load_agent()
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="Argument erledigt.", stderr="")

    monkeypatch.setattr(agent.subprocess, "run", fake_run)

    answer = agent._run_pi(
        executable="/usr/local/bin/pi",
        arguments=["ask", "{prompt}"],
        prompt="Frage als Argument",
        timeout=120,
        project_path=None,
        project_alias="",
    )

    assert answer == "Argument erledigt."
    assert captured["command"] == ["/usr/local/bin/pi", "ask", "Frage als Argument"]
    assert captured["kwargs"]["input"] is None


def test_pi_selects_project_and_runs_in_project_cwd(monkeypatch, tmp_path):
    agent = _load_agent()
    project = tmp_path / "SandboxVault"
    project.mkdir()
    monkeypatch.setattr(agent, "_resolve_executable", lambda _value: "/bin/pi")
    captured = {}

    def fake_run_pi(**kwargs):
        captured.update(kwargs)
        return "Pi Projekt ok."

    monkeypatch.setattr(agent, "_run_pi", fake_run_pi)

    result = agent.execute(
        "Trinity, nutze Pi im Projekt SandboxVault und pruefe hello-agent.",
        {
            "pi_cfg": {
                "enabled": True,
                "projects": {"SandboxVault": str(project)},
                "default_project": "SandboxVault",
                "arguments": ["-p", "{prompt}"],
            }
        },
    )

    assert result["direct_answer"] == "Pi Projekt ok."
    assert captured["project_path"] == project.resolve()
    assert captured["project_alias"] == "SandboxVault"
    assert captured["arguments"] == ["-p", "{prompt}"]
    assert "Projekt: SandboxVault" in captured["prompt"]
    assert "relative Pfade" in captured["prompt"]


def test_pi_enriches_brainvault_prompt_with_matching_agent_and_project(monkeypatch, tmp_path):
    agent = _load_agent()
    brainvault = tmp_path / "BrainVault"
    erendria_agent = brainvault / ".agents" / "skills" / "erendria-orchestrator"
    erendria_agent.mkdir(parents=True)
    (erendria_agent / "agent.yaml").write_text(
        "\n".join(
            [
                "id: skills.erendria_orchestrator",
                "name: Erendria Buchschreib-Orchestrator",
                "status: active",
                "preferred_harness: pi",
                "description: Koordiniert Buchschreiben und Erendria-Wiki.",
                "path: .agents/skills/erendria-orchestrator",
            ]
        ),
        encoding="utf-8",
    )
    (brainvault / "Ideaverse" / "projects" / "Erendria").mkdir(parents=True)
    monkeypatch.setattr(agent, "_resolve_executable", lambda _value: "/bin/pi")
    captured = {}

    def fake_run_pi(**kwargs):
        captured.update(kwargs)
        return "Erendria ist im BrainVault vorhanden."

    monkeypatch.setattr(agent, "_run_pi", fake_run_pi)

    result = agent.execute(
        "Trinity, frag Pi nach Erendria und welche Agenten dafuer genutzt werden.",
        {
            "pi_cfg": {
                "enabled": True,
                "projects": {"BrainVault": str(brainvault)},
                "default_project": "BrainVault",
                "arguments": ["-p", "{prompt}"],
            }
        },
    )

    assert result["direct_answer"] == "Erendria ist im BrainVault vorhanden."
    assert captured["project_path"] == brainvault.resolve()
    assert "Erendria Buchschreib-Orchestrator" in captured["prompt"]
    assert ".agents/skills/erendria-orchestrator" in captured["prompt"]
    assert "Ideaverse/projects/Erendria" in captured["prompt"]


def test_run_pi_sets_project_environment(monkeypatch, tmp_path):
    agent = _load_agent()
    project = tmp_path / "BrainVault"
    (project / ".agents").mkdir(parents=True)
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(agent.subprocess, "run", fake_run)

    answer = agent._run_pi(
        executable="/usr/local/bin/pi",
        arguments=["-p", "{prompt}"],
        prompt="Frage",
        timeout=120,
        project_path=project,
        project_alias="BrainVault",
    )

    assert answer == "ok"
    assert captured["kwargs"]["cwd"] == str(project)
    assert captured["kwargs"]["env"]["TRINITY_PROJECT_ROOT"] == str(project)
    assert captured["kwargs"]["env"]["TRINITY_BRAINVAULT_ROOT"] == str(project)
    assert captured["kwargs"]["env"]["TRINITY_PROJECT_ALIAS"] == "BrainVault"


def test_clean_pi_answer_removes_leaked_thinking():
    agent = _load_agent()
    raw = """Here's a thinking process:
1. Analyse.
2. Draft.

Final Answer:
Erendria ist vorhanden und nutzt den Orchestrator.
"""

    assert agent._clean_pi_answer(raw) == "Erendria ist vorhanden und nutzt den Orchestrator."


def test_execute_returns_pi_answer_directly(monkeypatch):
    agent = _load_agent()
    monkeypatch.setattr(agent, "_resolve_executable", lambda _value: "/bin/pi")
    monkeypatch.setattr(agent, "_run_pi", lambda **_kwargs: "Pi hat geantwortet.")

    result = agent.execute(
        "Trinity, nutze Pi und bewerte diese Idee.",
        {"pi_cfg": {"enabled": True}},
    )

    assert result["direct_answer"] == "Pi hat geantwortet."
    assert result["has_payload"] is True
    assert "Pi hat geantwortet" in result["html_payload"]


def test_capability_request_lists_brainvault_agents_without_explicit_pi(monkeypatch, tmp_path):
    agent = _load_agent()
    brainvault = tmp_path / "BrainVault"
    catalog_dir = brainvault / ".agents" / "_meta"
    catalog_dir.mkdir(parents=True)
    (catalog_dir / "agent_catalog.json").write_text(
        json.dumps(
            {
                "agents": [
                    {
                        "id": "skills.mail_agent",
                        "name": "Mail-Agent",
                        "status": "active",
                        "enabled": True,
                        "description": "Bereitet Mailentwuerfe und Rundlaeufe vor.",
                    },
                    {
                        "id": "draft.hidden",
                        "name": "Draft",
                        "status": "draft",
                        "enabled": False,
                        "description": "Noch nicht sichtbar.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    def fail_run_pi(**_kwargs):
        raise AssertionError("Faehigkeitslisten sollen keinen Pi-Lauf starten.")

    monkeypatch.setattr(agent, "_run_pi", fail_run_pi)

    result = agent.execute(
        "Hi Trinity, welche Fähigkeiten hast Du?",
        {
            "pi_cfg": {
                "enabled": True,
                "projects": {"BrainVault": str(brainvault)},
                "default_project": "BrainVault",
            }
        },
    )

    answer = result["direct_answer"]
    assert "Trinity direkt" in answer
    assert "Mail-Agent" in answer
    assert "Pi nicht nennen" in answer
    assert "Codex und Antigravity" in answer
