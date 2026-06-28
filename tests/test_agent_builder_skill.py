import importlib.util
import json
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
    assert skill.can_handle("Trinity, hol Dir diesen Agenten aus dem Ordner")
    assert skill.can_handle("Trinity, erweitere den Agenten Gutachten")
    assert not skill.can_handle("Trinity, erklaere Spieltheorie")


def test_agent_builder_returns_reviewable_payload():
    skill = _load_agent_builder()

    result = skill.execute("Trinity, baue einen Agenten fuer Folienchecks")

    assert result["direct_answer"].startswith("Ich habe den Agentenbuilder aktiviert.")
    assert result["has_payload"] is True
    assert "Quality-Gates" in result["html_payload"]
    assert "Freigabe" in result["html_payload"]


def test_agent_builder_imports_existing_agent_as_staging_skill(tmp_path, monkeypatch):
    skill = _load_agent_builder()
    source = tmp_path / "BrainVault" / "DCM-Agent"
    subagent = source / "SubagentRecherche"
    subagent.mkdir(parents=True)
    (source / "Agenten-Uebersicht.md").write_text(
        "# DCM-Agent\n\nTrigger: DCM bewerten\n",
        encoding="utf-8",
    )
    (source / "workflow.yaml").write_text("steps: []\n", encoding="utf-8")
    (subagent / "README.md").write_text("# Subagent\n", encoding="utf-8")
    repo = tmp_path / "Trinity"
    monkeypatch.setattr(skill, "_repo_root", lambda: repo)

    result = skill.execute(f'Trinity, hol Dir diesen Agenten "{source}"')

    assert "Staging-Skill vorbereitet" in result["direct_answer"]
    staging_root = repo / "skills" / "staging"
    created = list(staging_root.iterdir())
    assert len(created) == 1
    manifest = json.loads((created[0] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["tier"] == "staging"
    assert manifest["source_agent_path"] == str(source.resolve())
    assert manifest["subagents"] == ["SubagentRecherche"]
    assert (created[0] / "source_snapshot" / "Agenten-Uebersicht.md").is_file()
    assert (created[0] / "README_IMPORT.md").is_file()
