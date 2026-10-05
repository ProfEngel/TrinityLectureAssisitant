import importlib.util
from pathlib import Path

import pytest

from platform_adapters.microsoft_word import MacOSWordController, WordSelection
from word_control import WordControlService


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "agents" / "word_agent" / "script.py"


def load_agent():
    spec = importlib.util.spec_from_file_location("test_word_agent", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def enabled_config():
    return {
        "enabled": True,
        "dry_run": False,
        "allowed_applications": ["Microsoft Word"],
    }


def test_macos_word_adapter_passes_text_as_argument_without_shell(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return type("Result", (), {"returncode": 0, "stdout": "Dokument1\n", "stderr": ""})()

    monkeypatch.setattr("platform_adapters.microsoft_word.subprocess.run", fake_run)
    controller = MacOSWordController()

    controller.insert_text('Text mit "Anfuehrung" und \\ Pfad')

    command, kwargs = calls[0]
    assert command[:2] == ["/usr/bin/osascript", "-"]
    assert command[2] == 'Text mit "Anfuehrung" und \\ Pfad'
    assert kwargs["input"].startswith("\non run argv")
    assert kwargs.get("shell") is not True


def test_word_service_blocks_paths_outside_vault_and_existing_files(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    existing = vault / "vorhanden.docx"
    existing.write_text("bestehend", encoding="utf-8")

    class FakeController:
        def save_as(self, path):
            Path(path).write_text("docx", encoding="utf-8")
            return str(path)

    service = WordControlService(enabled_config(), FakeController(), tmp_path)

    with pytest.raises(ValueError, match="ausserhalb"):
        service.save(tmp_path / "draussen.docx", [vault])
    with pytest.raises(FileExistsError, match="existiert bereits"):
        service.save(existing, [vault])

    target = vault / "neu.docx"
    assert service.save(target, [vault]) == str(target)
    assert target.exists()


def test_agent_recognizes_word_actions_and_not_explanations():
    agent = load_agent()

    assert agent.can_handle("Erstelle ein neues Word-Dokument")
    assert agent.can_handle("Schreibe in Word: Hallo Welt")
    assert agent.can_handle("Mach die markierte Auswahl fett")
    assert agent.can_handle("Formuliere den Absatz besser aus")
    assert agent.can_handle("Speichere das Word-Dokument")
    assert not agent.can_handle("Erklaere mir, was Microsoft Word ist")


def test_agent_creates_writes_formats_and_rewrites_selection(tmp_path, monkeypatch):
    agent = load_agent()
    calls = []

    class FakeController:
        def create_document(self):
            calls.append(("new",))
            return "Dokument1"

        def insert_text(self, text):
            calls.append(("write", text))
            return "eingefuegt"

        def format_selection(self, style):
            calls.append(("format", style))
            return "formatiert"

        def selection(self):
            return WordSelection("Das ist holprig.")

        def replace_selection(self, text):
            calls.append(("replace", text))
            return "ersetzt"

    class FakeBrain:
        def ask_llm(self, messages):
            assert "Das ist holprig." in messages[0]["content"]
            return "Dieser Absatz ist klar formuliert."

    monkeypatch.setattr(agent, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(agent, "create_word_controller", lambda: FakeController())
    context = {"full_config": {"desktop_control": enabled_config()}, "brain": FakeBrain()}

    assert "geoeffnet" in agent.execute("Erstelle ein neues Word-Dokument", context)["direct_answer"]
    agent.execute("Schreibe in Word: Hallo Welt", context)
    agent.execute("Mach die markierte Auswahl zu Stichpunkten", context)
    agent.execute("Formuliere den Absatz besser aus", context)

    assert calls == [
        ("new",),
        ("write", "Hallo Welt"),
        ("format", "bullets"),
        ("replace", "Dieser Absatz ist klar formuliert."),
    ]


def test_guided_save_walks_folders_and_persists_dialog(tmp_path, monkeypatch):
    agent = load_agent()
    vault = tmp_path / "BrainVault"
    module = vault / "10 Aktive Projekte" / "Trinity"
    module.mkdir(parents=True)
    opened = []
    saved = []

    class FakeController:
        def open_folder(self, path):
            opened.append(Path(path))

        def save_as(self, path):
            path = Path(path)
            path.write_text("docx", encoding="utf-8")
            saved.append(path)
            return str(path)

    monkeypatch.setattr(agent, "STATE_PATH", tmp_path / "word_dialog.json")
    monkeypatch.setattr(agent, "create_word_controller", lambda: FakeController())
    context = {
        "full_config": {
            "desktop_control": enabled_config(),
            "control_plane": {"vault_root": str(vault)},
        }
    }

    first = agent.execute("Speichere das Word-Dokument", context)["direct_answer"]
    assert "Wo soll" in first
    assert "BrainVault" in first
    agent.execute("in BrainVault", context)
    assert agent.can_handle("10 Aktive Projekte")
    agent.execute("10 Aktive Projekte", context)
    agent.execute("Trinity", context)
    assert "Wie soll" in agent.execute("hier speichern", context)["direct_answer"]
    final = agent.execute("Word Sprachtest", context)["direct_answer"]

    assert "Word Sprachtest.docx" in final
    assert saved == [module / "Word Sprachtest.docx"]
    assert opened[-1] == module
    assert not agent.STATE_PATH.exists()


def test_save_dialog_can_go_back_but_never_above_root(tmp_path, monkeypatch):
    agent = load_agent()
    vault = tmp_path / "Vault"
    child = vault / "Kind"
    child.mkdir(parents=True)
    opened = []

    class FakeController:
        def open_folder(self, path):
            opened.append(Path(path))

    monkeypatch.setattr(agent, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(agent, "create_word_controller", lambda: FakeController())
    context = {
        "full_config": {
            "desktop_control": enabled_config(),
            "control_plane": {"vault_root": str(vault)},
        }
    }
    agent.execute("Speichere das Word-Dokument", context)
    agent.execute("in Vault", context)
    agent.execute("Kind", context)
    agent.execute("zurueck", context)
    agent.execute("zurueck", context)

    assert opened[-1] == vault
