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
    inspect_agent,
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
    assert (root / ".catalog" / "agent_catalog.json").is_file()
    assert (root / ".catalog" / "AGENT_CATALOG.md").is_file()

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
        {"control_plane": {"brainvault_root": str(vault)}},
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

    assert resolved == tmp_path / "MainHub"
