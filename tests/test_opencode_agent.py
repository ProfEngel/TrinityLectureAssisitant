import importlib.util
import re
import shlex
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "agents" / "opencode_agent" / "script.py"


def _load_agent():
    spec = importlib.util.spec_from_file_location("opencode_agent_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_opencode_requires_explicit_trigger():
    agent = _load_agent()

    assert agent.can_handle("Trinity, nutze OpenCode für diese Aufgabe")
    assert agent.can_handle("Trinity, starte Open Code")
    assert not agent.can_handle("Trinity, prüfe meine Mails")


def test_project_selection_uses_explicit_alias_or_default(tmp_path):
    agent = _load_agent()
    automation = tmp_path / "automation"
    teaching = tmp_path / "teaching"
    automation.mkdir()
    teaching.mkdir()
    projects = {"Automatismen": automation, "Lehre": teaching}

    alias, path, error = agent._select_project(
        "Trinity, OpenCode im Projekt Lehre: prüfe die Unterlagen",
        projects,
        {"default_project": "Automatismen"},
    )
    assert (alias, path, error) == ("Lehre", teaching, None)

    alias, path, error = agent._select_project(
        "Trinity, OpenCode: prüfe meine Mails",
        projects,
        {"default_project": "automatismen"},
    )
    assert (alias, path, error) == ("Automatismen", automation, None)


def test_run_opencode_uses_run_model_agent_and_project_cwd(monkeypatch, tmp_path):
    agent = _load_agent()
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="Aufgabe erledigt.", stderr="")

    monkeypatch.setattr(agent.subprocess, "run", fake_run)
    monkeypatch.setattr(agent, "_needs_posix_shell", lambda _executable: True)

    answer = agent._run_opencode(
        executable="/usr/local/bin/opencode",
        project_path=tmp_path,
        prompt="Prüfe das Projekt.",
        timeout=120,
        model="provider/model",
        agent="build",
    )

    command = captured["command"]
    assert answer == "Aufgabe erledigt."
    assert shlex.split(command)[:2] == ["/usr/local/bin/opencode", "run"]
    parsed = shlex.split(command)
    assert parsed[parsed.index("--model") + 1] == "provider/model"
    assert parsed[parsed.index("--agent") + 1] == "build"
    assert parsed[-1] == "Prüfe das Projekt."
    assert captured["kwargs"]["shell"] is True
    assert captured["kwargs"]["cwd"] == str(tmp_path)


def test_windows_cmd_launcher_uses_shell_argument_escaping(monkeypatch, tmp_path):
    agent = _load_agent()
    captured = {}

    def fake_run(command, **kwargs):
        expected_command = [
            r"C:\Users\Name\AppData\Roaming\npm\opencode.cmd",
            "run",
            "--agent",
            "build",
        ]
        captured["kwargs"] = kwargs
        captured["command"] = command
        captured["expected_prefix"] = subprocess.list2cmdline(expected_command)
        assert re.search(r"Windows-Projekt", command)
        return subprocess.CompletedProcess(command, 0, stdout="Windows erledigt.", stderr="")

    monkeypatch.setattr(agent.subprocess, "run", fake_run)
    monkeypatch.setattr(agent, "_needs_windows_shell", lambda executable: True)

    answer = agent._run_opencode(
        executable=r"C:\Users\Name\AppData\Roaming\npm\opencode.cmd",
        project_path=tmp_path,
        prompt="Prüfe das Windows-Projekt.",
        timeout=120,
        agent="build",
    )

    assert answer == "Windows erledigt."
    assert captured["kwargs"]["shell"] is True
    assert isinstance(captured["command"], str)
    assert captured["command"].startswith(captured["expected_prefix"])


def test_posix_opencode_launcher_uses_shell_quoted_command(monkeypatch, tmp_path):
    agent = _load_agent()
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="macOS erledigt.", stderr="")

    monkeypatch.setattr(agent.subprocess, "run", fake_run)
    monkeypatch.setattr(agent, "_needs_posix_shell", lambda executable: True)

    answer = agent._run_opencode(
        executable="/Users/test/.opencode/bin/opencode",
        project_path=tmp_path,
        prompt="Prüfe das Projekt mit Leerzeichen.",
        timeout=120,
        agent="trinity-smoke",
    )

    assert answer == "macOS erledigt."
    assert captured["kwargs"]["shell"] is True
    assert isinstance(captured["command"], str)
    assert "--agent trinity-smoke" in captured["command"]
    assert "'Prüfe das Projekt mit Leerzeichen.'" in captured["command"]


def test_execute_returns_opencode_answer_directly(monkeypatch, tmp_path):
    agent = _load_agent()
    monkeypatch.setattr(agent, "_resolve_executable", lambda _value: "/bin/opencode")
    monkeypatch.setattr(
        agent,
        "_run_opencode",
        lambda **_kwargs: "Drei Entwürfe wurden lokal vorbereitet.",
    )

    result = agent.execute(
        "Trinity, OpenCode im Projekt Automatismen: prüfe die Mails",
        {
            "opencode_cfg": {
                "enabled": True,
                "projects": {"Automatismen": str(tmp_path)},
                "default_project": "Automatismen",
            }
        },
    )

    assert result["direct_answer"] == "Drei Entwürfe wurden lokal vorbereitet."
    assert result["has_payload"] is True
    assert "Automatismen" in result["html_payload"]
