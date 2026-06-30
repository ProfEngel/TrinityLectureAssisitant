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
    assert skill.can_handle(
        "Trinity, hier ist ein Agent aus Antigravity. Mach ihn fuer Trinity moeglich."
    )
    assert skill.can_handle("Trinity, erweitere den Agenten Gutachten")
    assert not skill.can_handle("Trinity, erklaere Spieltheorie")


def test_agent_builder_returns_reviewable_payload(tmp_path, monkeypatch):
    skill = _load_agent_builder()
    monkeypatch.setattr(skill, "_repo_root", lambda: tmp_path / "Trinity")

    result = skill.execute("Trinity, baue einen Agenten fuer Folienchecks")

    assert result["direct_answer"].startswith("Ich habe den Agentenbuilder aktiviert")
    assert "Builder-Job" in result["direct_answer"]
    assert result["has_payload"] is True
    assert "Quality-Gates" in result["html_payload"]
    assert "Freigabe" in result["html_payload"]


def test_agent_builder_imports_existing_agent_as_brainvault_draft(tmp_path, monkeypatch):
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
    monkeypatch.setattr(skill, "_brainvault_root", lambda _context: repo / "BrainVault")

    result = skill.execute(f'Trinity, hol Dir diesen Agenten "{source}"')

    assert "BrainVault-Draft vorbereitet" in result["direct_answer"]
    agents_root = repo / "BrainVault" / ".agents" / "imported"
    created = list(agents_root.iterdir())
    assert len(created) == 1
    manifest = json.loads((created[0] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["tier"] == "brainvault"
    assert manifest["status"] == "draft"
    assert manifest["source_agent_path"] == str(source.resolve())
    assert manifest["subagents"] == ["SubagentRecherche"]
    assert (created[0] / "agent.yaml").is_file()
    assert (created[0] / "origin_snapshot" / "Agenten-Uebersicht.md").is_file()
    assert (created[0] / "README.md").is_file()
    assert (created[0] / "SKILL.md").is_file()
    assert (created[0] / "README_IMPORT.md").is_file()
    assert (created[0] / "BUILDER_PLAN.md").is_file()
    assert (created[0] / "VALIDATION_REPORT.md").is_file()
    assert "Builder-Job" in result["direct_answer"]
    assert (repo / "BrainVault" / ".agents" / "_meta" / "agent_catalog.json").is_file()


def test_agent_builder_natural_import_phrase_uses_import_mode(tmp_path, monkeypatch):
    skill = _load_agent_builder()
    source = tmp_path / "BrainVault" / "Antigravity-Agent"
    source.mkdir(parents=True)
    (source / "README.md").write_text("# Antigravity-Agent\n", encoding="utf-8")
    repo = tmp_path / "Trinity"
    monkeypatch.setattr(skill, "_repo_root", lambda: repo)
    monkeypatch.setattr(skill, "_brainvault_root", lambda _context: repo / "BrainVault")

    result = skill.execute(
        f'Trinity, hier ist ein Agent, den ich mit Antigravity erstellt habe: "{source}". '
        "Mach ihn fuer Trinity moeglich."
    )

    assert "BrainVault-Draft vorbereitet" in result["direct_answer"]
    created = list((repo / "BrainVault" / ".agents" / "imported").iterdir())
    assert len(created) == 1
    manifest = json.loads((created[0] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_agent_path"] == str(source.resolve())


def test_agent_builder_selects_configured_builder_harness_without_explicit_name(monkeypatch):
    skill = _load_agent_builder()
    config = {
        "control_plane": {"builder_harness": "pi"},
        "harness_routing": {
            "frameworks": {
                "pi": {"roles": {"agent_builder": True}},
                "codex": {"roles": {"agent_builder": True}},
            }
        },
        "pi": {"enabled": True},
        "codex": {"enabled": True, "projects": {"SandboxVault": "/tmp/sandbox"}},
    }
    monkeypatch.setattr(skill, "_config_from_context", lambda context: config)

    assert skill._requested_harnesses(
        "Trinity, hier ist ein Agent. Mach ihn fuer Trinity moeglich.",
        {},
    ) == ["pi"]
    assert skill._builder_harness_candidates(config)[0] == "pi"


def test_agent_builder_edit_creates_brainvault_draft_with_parent(tmp_path, monkeypatch):
    skill = _load_agent_builder()
    repo = tmp_path / "Trinity"
    monkeypatch.setattr(skill, "_repo_root", lambda: repo)
    monkeypatch.setattr(skill, "_brainvault_root", lambda _context: repo / "BrainVault")

    result = skill.execute("Trinity, erweitere den Deep Research Agent um Quellenbewertung")

    draft_root = repo / "BrainVault" / ".agents" / "draft"
    created = list(draft_root.iterdir())
    assert len(created) == 1
    manifest = json.loads((created[0] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["tier"] == "brainvault"
    assert manifest["status"] == "draft"
    assert manifest["source"] == "agent-builder-edit"
    assert manifest["parent_agent"] == "Deep Research Agent"
    assert (created[0] / "agent.yaml").is_file()
    assert (created[0] / "README.md").is_file()
    assert (created[0] / "SKILL.md").is_file()
    assert (created[0] / "README_BUILDER.md").is_file()
    assert (created[0] / "BUILDER_PLAN.md").is_file()
    assert (created[0] / "VALIDATION_REPORT.md").is_file()
    assert "Builder-Job" in result["direct_answer"]
