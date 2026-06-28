import importlib.util
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
    )

    assert answer == "Argument erledigt."
    assert captured["command"] == ["/usr/local/bin/pi", "ask", "Frage als Argument"]
    assert captured["kwargs"]["input"] is None


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
