import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "skills" / "shared" / "agent-builder" / "script.py"


def _load_agent_builder():
    spec = importlib.util.spec_from_file_location("agent_builder_skill_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agent_builder_requires_builder_trigger():
    skill = _load_agent_builder()

    assert skill.can_handle("Trinity, baue einen Agenten fuer Mail-Triage")
    assert skill.can_handle("Bitte den Agentenbuilder aktivieren")
    assert not skill.can_handle("Trinity, erklaere Spieltheorie")


def test_agent_builder_returns_reviewable_payload():
    skill = _load_agent_builder()

    result = skill.execute("Trinity, baue einen Agenten fuer Folienchecks")

    assert result["direct_answer"].startswith("Ich habe den Agentenbuilder aktiviert.")
    assert result["has_payload"] is True
    assert "Quality-Gates" in result["html_payload"]
    assert "Freigabe" in result["html_payload"]
