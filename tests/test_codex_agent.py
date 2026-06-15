import importlib.util
import re
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "agents" / "codex_agent" / "script.py"


def _load_agent():
    spec = importlib.util.spec_from_file_location("codex_agent_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_codex_requires_explicit_trigger():
    agent = _load_agent()

    assert agent.can_handle("Trinity, nutze Codex für diese Aufgabe")
    assert agent.can_handle("Trinity, starte Kodeks")
    assert not agent.can_handle("Trinity, prüfe meine Mails")


def test_project_selection_uses_explicit_alias_or_default(tmp_path):
    agent = _load_agent()
    automation = tmp_path / "automation"
    teaching = tmp_path / "teaching"
    automation.mkdir()
    teaching.mkdir()
    projects = {"Automatismen": automation, "Lehre": teaching}

    alias, path, error = agent._select_project(
        "Trinity, Codex im Projekt Lehre: prüfe die Unterlagen",
        projects,
        {"default_project": "Automatismen"},
    )
    assert (alias, path, error) == ("Lehre", teaching, None)

    alias, path, error = agent._select_project(
        "Trinity, Codex: prüfe meine Mails",
        projects,
        {"default_project": "automatismen"},
    )
    assert (alias, path, error) == ("Automatismen", automation, None)


def test_project_alias_is_not_selected_by_partial_task_word(tmp_path):
    agent = _load_agent()
    mail = tmp_path / "mail"
    teaching = tmp_path / "teaching"
    mail.mkdir()
    teaching.mkdir()

    alias, path, error = agent._select_project(
        "Trinity, Codex soll meine Mails prüfen",
        {"Mail": mail, "Lehre": teaching},
        {},
    )

    assert alias is None
    assert path is None
    assert "Bitte nenne" in error


def test_run_codex_uses_stdin_workspace_sandbox_and_last_message(
    monkeypatch, tmp_path
):
    agent = _load_agent()
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text("Aufgabe erledigt.", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(agent.subprocess, "run", fake_run)

    answer = agent._run_codex(
        executable="/usr/local/bin/codex",
        project_path=tmp_path,
        prompt="Prüfe das Projekt.",
        sandbox="workspace-write",
        timeout=120,
        ephemeral=True,
        network_access=True,
    )

    command = captured["command"]
    assert answer == "Aufgabe erledigt."
    assert command[:2] == ["/usr/local/bin/codex", "exec"]
    assert command[command.index("--cd") + 1] == str(tmp_path)
    assert command[command.index("--sandbox") + 1] == "workspace-write"
    assert 'approval_policy="never"' in command
    assert "sandbox_workspace_write.writable_roots=[]" in command
    assert "sandbox_workspace_write.network_access=true" in command
    assert "--ephemeral" in command
    assert command[-1] == "-"
    assert captured["kwargs"]["input"] == "Prüfe das Projekt."
    assert captured["kwargs"]["shell"] is False


def test_windows_cmd_launcher_uses_shell_argument_escaping(monkeypatch, tmp_path):
    agent = _load_agent()
    captured = {}

    def fake_run(command, **kwargs):
        expected_command = [
            r"C:\Users\Name\AppData\Roaming\npm\codex.cmd",
            "exec",
            "--cd",
            str(tmp_path),
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "--skip-git-repo-check",
            "--output-last-message",
        ]
        captured["kwargs"] = kwargs
        captured["command"] = command
        output_match = re.search(
            r'--output-last-message\s+(?:"([^"]+)"|(\S+))',
            command,
        )
        output_path = Path(output_match.group(1) or output_match.group(2))
        output_path.write_text("Windows-Aufgabe erledigt.", encoding="utf-8")
        captured["expected_prefix"] = subprocess.list2cmdline(expected_command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(agent.subprocess, "run", fake_run)
    monkeypatch.setattr(agent, "_needs_windows_shell", lambda executable: True)

    answer = agent._run_codex(
        executable=r"C:\Users\Name\AppData\Roaming\npm\codex.cmd",
        project_path=tmp_path,
        prompt="Prüfe das Windows-Projekt.",
        sandbox="read-only",
        timeout=120,
        ephemeral=True,
        network_access=False,
    )

    assert answer == "Windows-Aufgabe erledigt."
    assert captured["kwargs"]["shell"] is True
    assert isinstance(captured["command"], str)
    assert captured["command"].startswith(captured["expected_prefix"])


def test_windows_shell_detection():
    agent = _load_agent()

    assert agent._needs_windows_shell(r"C:\Tools\codex.cmd", host_os="nt") is True
    assert agent._needs_windows_shell(r"C:\Tools\codex.exe", host_os="nt") is False
    assert agent._needs_windows_shell("/usr/local/bin/codex", host_os="posix") is False


def test_execute_returns_codex_answer_directly(monkeypatch, tmp_path):
    agent = _load_agent()
    monkeypatch.setattr(agent, "_resolve_executable", lambda _value: "/bin/codex")
    monkeypatch.setattr(
        agent,
        "_run_codex",
        lambda **_kwargs: "Drei Entwürfe wurden lokal vorbereitet.",
    )

    result = agent.execute(
        "Trinity, Codex im Projekt Automatismen: prüfe die Mails",
        {
            "codex_cfg": {
                "enabled": True,
                "projects": {"Automatismen": str(tmp_path)},
                "default_project": "Automatismen",
            }
        },
    )

    assert result["direct_answer"] == "Drei Entwürfe wurden lokal vorbereitet."
    assert result["has_payload"] is True
    assert "Automatismen" in result["html_payload"]
