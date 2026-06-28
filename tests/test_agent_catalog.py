import json
import sqlite3

from agent_catalog import build_agent_catalog, default_harnesses_for_agent


def _write_shared_skill(home, skill_id="research-helper"):
    target = home / "skills" / "shared" / skill_id
    target.mkdir(parents=True)
    (target / "manifest.json").write_text(
        json.dumps(
            {
                "id": skill_id,
                "name": "Research Helper",
                "version": "0.1.0",
                "tier": "shared",
                "description": "Test helper.",
                "triggers": ["research"],
                "allowed_tools": ["web", "filesystem"],
                "allowed_paths": ["projects/research"],
                "requires_approval": ["external_upload"],
                "tests": [],
                "status": "active",
                "script": "script.py",
                "risk_level": "medium",
                "parent_agent": "haupt-agent",
                "subagents": ["sub-a", "sub-b"],
                "source_agent_path": "/tmp/source-agent",
            }
        ),
        encoding="utf-8",
    )
    (target / "script.py").write_text(
        "def can_handle(query): return False\n"
        "def execute(query, context=None): return {}\n",
        encoding="utf-8",
    )


def _write_legacy_agent(home):
    target = home / "agents" / "codex_agent"
    target.mkdir(parents=True)
    (target / "script.py").write_text(
        "def can_handle(query): return False\n"
        "def execute(query, context=None): return {}\n",
        encoding="utf-8",
    )


def test_catalog_includes_trinity_agent_builder_managed_and_legacy_agents(tmp_path):
    _write_shared_skill(tmp_path)
    _write_legacy_agent(tmp_path)

    records = build_agent_catalog(tmp_path, {})
    by_id = {record.agent_id: record for record in records}

    assert by_id["trinity-core"].name == "Trinity"
    assert by_id["trinity-core"].quality_status == "stable"
    assert by_id["agent-builder"].runtime_status == "missing"
    assert by_id["research-helper"].allowed_tools == ["web", "filesystem"]
    assert by_id["research-helper"].parent_agent == "haupt-agent"
    assert by_id["research-helper"].subagents == ["sub-a", "sub-b"]
    assert by_id["research-helper"].source_agent_path == "/tmp/source-agent"
    assert by_id["legacy-codex-agent"].legacy is True
    assert "codex" in default_harnesses_for_agent("legacy-codex-agent")
    assert default_harnesses_for_agent("unknown") == ["trinity"]


def test_catalog_applies_user_overrides_and_job_stats(tmp_path):
    _write_shared_skill(tmp_path)
    _write_legacy_agent(tmp_path)
    db_path = tmp_path / "memory" / "jobs.sqlite3"
    db_path.parent.mkdir(parents=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE jobs (route TEXT, status TEXT)")
        conn.executemany(
            "INSERT INTO jobs(route, status) VALUES (?, ?)",
            [("codex", "RUNNING"), ("codex", "FAILED"), ("local", "SUCCEEDED")],
        )

    config = {
        "agent_catalog": {
            "agents": {
                "research-helper": {
                    "quality_status": "validated",
                    "allowed_tools": ["web"],
                    "allowed_paths": ["projects/research", "RAG"],
                    "requires_approval": ["publish"],
                    "max_attempts": 4,
                    "parallel_runs": 2,
                }
            }
        }
    }

    records = build_agent_catalog(tmp_path, config)
    by_id = {record.agent_id: record for record in records}

    helper = by_id["research-helper"]
    assert helper.quality_status == "validated"
    assert helper.allowed_tools == ["web"]
    assert helper.allowed_paths == ["projects/research", "RAG"]
    assert helper.requires_approval == ["publish"]
    assert helper.max_attempts == 4
    assert helper.parallel_runs == 2
    assert by_id["legacy-codex-agent"].job_total == 2
    assert by_id["legacy-codex-agent"].job_open == 1
    assert by_id["legacy-codex-agent"].job_failed == 1
