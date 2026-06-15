import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "agents"
    / "powerpoint_agent"
    / "script.py"
)


def load_agent():
    spec = importlib.util.spec_from_file_location("test_powerpoint_agent_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_powerpoint_agent_dispatches_next(monkeypatch):
    module = load_agent()
    actions = []

    class FakeController:
        def perform(self, action):
            actions.append(action)
            return True, ""

    monkeypatch.setattr(module, "create_powerpoint_controller", lambda: FakeController())

    result = module.execute("Trinity, nächste Folie")

    assert actions == ["next"]
    assert "Zur nächsten Folie" in result["search_context"]


def test_powerpoint_agent_reports_real_failure(monkeypatch):
    module = load_agent()

    class FakeController:
        def perform(self, action):
            return False, "PowerPoint ist nicht geöffnet."

    monkeypatch.setattr(module, "create_powerpoint_controller", lambda: FakeController())

    result = module.execute("Trinity, Präsentation starten")

    assert "POWERPOINT FEHLER" in result["search_context"]
    assert "nicht geöffnet" in result["search_context"]
