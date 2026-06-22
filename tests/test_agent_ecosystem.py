import json
from pathlib import Path

import pytest

from core.brain import TrinityBrain
from approval_manager import ApprovalManager
from job_manager import JobManager
from policy_engine import PolicyEngine
from skill_registry import SkillRegistry
from task_orchestrator import TaskOrchestrator


def _manifest(skill_id="sample-skill", tier="staging", status="staging", job_id=""):
    data = {
        "id": skill_id,
        "name": "Sample Skill",
        "version": "0.1.0",
        "tier": tier,
        "description": "A test skill.",
        "triggers": ["sample task"],
        "allowed_tools": ["filesystem"],
        "allowed_paths": ["artifacts"],
        "requires_approval": ["activate_skill"],
        "tests": ["tests/test_skill.py"],
        "status": status,
    }
    if job_id:
        data["job_id"] = job_id
    return data


def _write_staging_skill(home, skill_id="sample-skill", job_id=""):
    target = home / "skills" / "staging" / skill_id
    (target / "tests").mkdir(parents=True)
    (target / "manifest.json").write_text(
        json.dumps(_manifest(skill_id=skill_id, job_id=job_id)),
        encoding="utf-8",
    )
    (target / "script.py").write_text(
        "def can_handle(query):\\n    return 'sample task' in query\\n"
        "def execute(query, context=None):\\n    return {'direct_answer': 'ok'}\\n",
        encoding="utf-8",
    )
    (target / "tests" / "test_skill.py").write_text("def test_placeholder(): pass\\n")
    return target


def test_registry_keeps_legacy_and_excludes_staging(tmp_path):
    legacy = tmp_path / "agents" / "old_agent"
    legacy.mkdir(parents=True)
    (legacy / "script.py").write_text("def can_handle(q): return False\\ndef execute(q, context=None): return {}\\n")
    _write_staging_skill(tmp_path)

    registry = SkillRegistry(tmp_path)
    summary = registry.summary()

    assert summary["legacy"] == 1
    assert summary["staging"] == 1
    assert registry.load_active_modules() == []


def test_promotion_requires_one_time_approval_and_moves_to_personal(tmp_path):
    jobs = JobManager(tmp_path)
    job = jobs.create_job("Promote skill")
    _write_staging_skill(tmp_path, job_id=job["job_id"])
    registry = SkillRegistry(tmp_path)
    approvals = ApprovalManager(tmp_path)
    request = approvals.request(
        job["job_id"], "activate_skill", "Promote the staging skill"
    )
    approvals.decide(request["approval_id"], "approve")

    promoted = registry.promote(
        "sample-skill",
        approval_manager=approvals,
        approval_id=request["approval_id"],
    )

    assert promoted.manifest.tier == "personal"
    assert promoted.manifest.status == "active"
    assert (tmp_path / "skills" / "personal" / "sample-skill" / "manifest.json").is_file()
    with pytest.raises(PermissionError):
        approvals.consume(
            request["approval_id"],
            expected_action="activate_skill",
            expected_job_id=job["job_id"],
        )


def test_child_approval_is_bound_to_parent_scope_and_job(tmp_path):
    approvals = ApprovalManager(tmp_path)
    parent = approvals.request("job_1", "external_upload", "Allow export")
    approvals.decide(
        parent["approval_id"],
        "approve",
        child_actions=["send_mail"],
    )
    child = approvals.request(
        "job_1",
        "send_mail",
        "Send prepared draft",
        parent_approval_id=parent["approval_id"],
    )
    approvals.decide(child["approval_id"], "approve")
    consumed = approvals.consume(
        child["approval_id"], expected_action="send_mail", expected_job_id="job_1"
    )

    assert consumed["status"] == "APPROVED"
    with pytest.raises(PermissionError):
        approvals.request(
            "job_1",
            "delete",
            "Delete file",
            parent_approval_id=parent["approval_id"],
        )


def test_orchestrator_creates_plan_and_blocks_risky_execution(tmp_path):
    orchestrator = TaskOrchestrator(tmp_path)

    planned = orchestrator.prepare(
        "Trinity, nutze Codex im Projekt Buch und pruefe die Tests."
    )
    assert planned.route == "codex"
    assert planned.requires_plan is True
    assert planned.blocked is False
    assert planned.job["status"] == "RUNNING"
    assert len(planned.job["steps"]) == 4

    blocked = orchestrator.prepare(
        "Trinity, nutze OpenCode im Projekt Buch und sende die Mail."
    )
    assert blocked.blocked is True
    assert blocked.approval is not None
    assert blocked.job["status"] == "WAITING_FOR_APPROVAL"


def test_policy_blocks_package_installation_and_requires_mail_approval():
    policy = PolicyEngine()

    assert policy.decide("install_package").allowed is False
    mail = policy.decide("send_mail")
    assert mail.allowed is True
    assert mail.requires_approval is True


def test_brain_records_a_planned_code_agent_job(tmp_path):
    class DirectSkill:
        __name__ = "agents.codex_agent"

        @staticmethod
        def can_handle(_query):
            return True

        @staticmethod
        def execute(_query, context=None):
            return {"direct_answer": "Pruefung und Bericht erledigt."}

    brain = TrinityBrain.__new__(TrinityBrain)
    brain.api_key = ""
    brain.url = "http://unused"
    brain.model = "unused"
    brain.live_skills = [DirectSkill]
    brain.unavailable_skills = []
    brain._telegram_cfg = {}
    brain._codex_cfg = {}
    brain._opencode_cfg = {}
    brain._soul_cache = ""
    brain._user_cache = ""
    brain.task_orchestrator = TaskOrchestrator(tmp_path)

    transcript = tmp_path / "transcript.md"
    transcript.write_text("", encoding="utf-8")
    answer, _payload = brain.ask(
        "Trinity, nutze Codex im Projekt Testprojekt und pruefe die Tests.",
        str(transcript),
    )

    jobs = JobManager(tmp_path).list()
    assert answer == "Pruefung und Bericht erledigt."
    assert len(jobs) == 1
    assert jobs[0]["route"] == "codex"
    assert jobs[0]["status"] == "SUCCEEDED"
    assert all(step["status"] == "SUCCEEDED" for step in jobs[0]["steps"])
