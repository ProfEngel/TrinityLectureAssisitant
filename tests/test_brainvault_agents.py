import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from agent_catalog import build_agent_catalog  # noqa: E402
from brainvault_agents import (  # noqa: E402
    brainvault_root_from_config,
    build_catalog,
    create_agent,
    ensure_brainvault_layout,
    import_agent_directory,
    inspect_agent,
    register_external_agent,
    validate_agent,
)


def test_brainvault_layout_and_agentctl_primitives(tmp_path):
    root = tmp_path / "MainHub"

    ensure_brainvault_layout(root)
    created = create_agent(
        root,
        "research",
        "thesis-reviewer",
        name="Thesis Reviewer",
        description="Reviews thesis drafts.",
    )

    assert (root / ".agents" / "research" / "thesis-reviewer" / "agent.yaml").is_file()
    assert (root / ".agents" / "research" / "thesis-reviewer" / "SKILL.md").is_file()
    assert created["agent_id"] == "research.thesis_reviewer"

    catalog = build_catalog(root)
    assert catalog["summary"]["total"] == 1
    assert (root / ".agents" / "_meta" / "agent_catalog.json").is_file()
    assert (root / ".agents" / "_meta" / "AGENT_CATALOG.md").is_file()
    assert not (root / ".catalog").exists()
    assert not (root / ".ai").exists()

    inspected = inspect_agent(root, "research.thesis_reviewer")
    assert inspected["status"] == "draft"
    assert inspected["source"] == "brainvault"

    validation = validate_agent(root, "research.thesis_reviewer")
    assert validation["ok"] is True


def test_brainvault_catalog_records_are_visible_in_trinity_catalog(tmp_path):
    home = tmp_path / "Trinity"
    vault = tmp_path / "MainHub"
    (home / "core").mkdir(parents=True)
    create_agent(vault, "media", "image-agent", name="Bildgenerierung")

    records = build_agent_catalog(
        home,
        {"control_plane": {"external_agents_root": str(vault)}},
    )
    by_id = {record.agent_id: record for record in records}

    assert "media.image_agent" in by_id
    assert by_id["media.image_agent"].tier == "brainvault"
    assert by_id["media.image_agent"].source == "brainvault"
    assert by_id["media.image_agent"].execution_scope == "shared_harness"


def test_brainvault_root_derives_parent_when_config_points_to_trinityvault(tmp_path):
    home = tmp_path / "Trinity"
    vault = tmp_path / "MainHub" / "TrinityVault"

    resolved = brainvault_root_from_config(
        home,
        {"control_plane": {"vault_root": str(vault)}},
    )

    assert resolved == tmp_path


def test_external_agents_root_overrides_brainvault_root(tmp_path):
    home = tmp_path / "Trinity"
    brainvault = tmp_path / "BrainVault"
    external = tmp_path / "ExternalAgents"

    resolved = brainvault_root_from_config(
        home,
        {
            "control_plane": {
                "brainvault_root": str(brainvault),
                "external_agents_root": str(external),
            }
        },
    )

    assert resolved == external.resolve()


def test_import_agent_directory_copies_skill_and_catalogs_as_active(tmp_path):
    root = tmp_path / "BrainVault"
    source = tmp_path / "CampusHub" / ".agents" / "skills" / "demo-agent"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\nname: demo-agent\ndescription: Demo skill.\n---\n# Demo\n",
        encoding="utf-8",
    )
    (source / "script.py").write_text("print('ok')\n", encoding="utf-8")
    (source / ".venv").mkdir()
    (source / ".venv" / "skip.py").write_text("broken python", encoding="utf-8")

    result = import_agent_directory(root, source, preferred_harness="codex")

    assert result["agent_id"] == "skills.demo_agent"
    target = root / ".agents" / "skills" / "demo-agent"
    assert (target / "SKILL.md").is_file()
    assert (target / "script.py").is_file()
    assert not (target / ".venv").exists()
    validation = validate_agent(root, "skills.demo_agent")
    assert validation["ok"] is True
    inspected = inspect_agent(root, "skills.demo_agent")
    assert inspected["preferred_harness"] == "codex"
    assert inspected["status"] == "active"


def test_register_external_agent_keeps_origin_and_optional_snapshot(tmp_path):
    root = tmp_path / "BrainVault"
    source = tmp_path / "CampusHub" / "Mail" / "agents" / "01_mail_reader.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Mail Reader\n\nReads mail metadata.\n", encoding="utf-8")

    result = register_external_agent(
        root,
        source,
        area="mail",
        agent_id="mail-reader",
        name="Mail Reader",
        description="Reads mail metadata safely.",
        parent_agent="projects.campushub_mail_automation",
        copy_source=True,
    )

    assert result["agent_id"] == "mail.mail_reader"
    target = root / ".agents" / "mail" / "mail-reader"
    assert (target / "agent.yaml").is_file()
    assert (target / "source" / "01_mail_reader.md").is_file()
    validation = validate_agent(root, "mail.mail_reader")
    assert validation["ok"] is True
    inspected = inspect_agent(root, "mail.mail_reader")
    assert inspected["workspace"] == str(source.parent)
    assert inspected["origin"]["source_paths"] == [str(source)]
    assert inspected["parent_agent"] == "projects.campushub_mail_automation"

    records = build_agent_catalog(
        tmp_path / "Trinity",
        {"control_plane": {"external_agents_root": str(root)}},
    )
    by_id = {record.agent_id: record for record in records}
    assert by_id["mail.mail_reader"].parent_agent == "projects.campushub_mail_automation"
