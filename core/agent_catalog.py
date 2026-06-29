"""Unified Trinity agent catalog for settings, routing and audits."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from brainvault_agents import brainvault_root_from_config, list_agents
from skill_registry import SkillRecord, SkillRegistry


QUALITY_STATUSES = ("unverified", "testing", "validated", "stable", "deprecated")
DEFAULT_MAX_ATTEMPTS = 2
DEFAULT_PARALLEL_RUNS = 1


@dataclass
class AgentCatalogRecord:
    agent_id: str
    name: str
    tier: str
    runtime_status: str
    quality_status: str
    source: str
    path: str = ""
    description: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    requires_approval: list[str] = field(default_factory=list)
    risk_level: str = "low"
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    parallel_runs: int = DEFAULT_PARALLEL_RUNS
    job_total: int = 0
    job_open: int = 0
    job_failed: int = 0
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    legacy: bool = False
    synthetic: bool = False
    parent_agent: str = ""
    subagents: list[str] = field(default_factory=list)
    source_agent_path: str = ""
    enabled: bool = True
    execution_scope: str = ""
    workspace: str = ""
    compatible_harnesses: list[str] = field(default_factory=list)
    preferred_harness: str = ""
    natural_triggers: list[str] = field(default_factory=list)
    slash_triggers: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)
    last_validated: str = ""

    @property
    def tier_order(self) -> int:
        order = {"trinity": 0, "brainvault": 1, "shared": 2, "personal": 3, "staging": 4, "legacy": 5}
        return order.get(self.tier, 9)


def build_agent_catalog(
    home: Optional[Union[str, Path]] = None,
    config: Optional[dict] = None,
) -> list[AgentCatalogRecord]:
    """Return Trinity plus every discovered agent/skill with user overrides."""

    root = Path(home or Path(__file__).resolve().parents[1]).resolve()
    cfg = config or {}
    overrides = (cfg.get("agent_catalog") or {}).get("agents") or {}
    stats = _job_stats(root)
    records = [_trinity_record(root, overrides, stats)]

    registry = SkillRegistry(root)
    discovered = []
    try:
        discovered = registry.list()
    except Exception:  # pragma: no cover - UI should degrade gracefully
        discovered = []

    seen = {"trinity-core"}
    for record in discovered:
        catalog_record = _record_from_skill(record, overrides, stats)
        records.append(catalog_record)
        seen.add(catalog_record.agent_id)

    if "agent-builder" not in seen:
        records.append(_agent_builder_record(root, overrides, stats, synthetic=True))

    records.extend(_brainvault_records(root, cfg, overrides, stats, seen))

    return sorted(records, key=lambda item: (item.tier_order, item.name.casefold(), item.agent_id))


def default_harnesses_for_agent(agent_id: str) -> list[str]:
    """Default execution harnesses for a newly discovered agent."""

    normalized = str(agent_id or "").casefold()
    if normalized == "trinity-core":
        return ["trinity"]
    if normalized in {"agent-builder", "legacy-agent-builder-agent"}:
        return ["trinity", "codex"]
    if normalized in {"codex-agent", "legacy-codex-agent", "codex_agent"}:
        return ["trinity", "codex"]
    if normalized in {"opencode-agent", "legacy-opencode-agent", "opencode_agent"}:
        return ["trinity", "opencode"]
    if normalized in {"pi-agent", "legacy-pi-agent", "pi_agent"}:
        return ["trinity", "pi"]
    if normalized.startswith("brainvault.") or "." in normalized:
        return ["trinity", "pi", "codex", "opencode"]
    return ["trinity"]


def normalize_quality_status(value: str) -> str:
    clean = str(value or "").strip().lower()
    return clean if clean in QUALITY_STATUSES else "unverified"


def normalize_catalog_overrides(raw: Optional[dict]) -> dict:
    """Sanitize saved agent catalog overrides before writing config.json."""

    if not isinstance(raw, dict):
        return {}
    result = {}
    for agent_id, values in raw.items():
        if not isinstance(values, dict):
            continue
        clean_id = str(agent_id).strip()
        if not clean_id:
            continue
        result[clean_id] = {
            "quality_status": normalize_quality_status(values.get("quality_status")),
            "allowed_tools": _string_list(values.get("allowed_tools")),
            "allowed_paths": _string_list(values.get("allowed_paths")),
            "requires_approval": _string_list(values.get("requires_approval")),
            "max_attempts": _bounded_int(values.get("max_attempts"), DEFAULT_MAX_ATTEMPTS, 1, 20),
            "parallel_runs": _bounded_int(values.get("parallel_runs"), DEFAULT_PARALLEL_RUNS, 1, 20),
        }
    return result


def _trinity_record(root: Path, overrides: dict, stats: dict) -> AgentCatalogRecord:
    return _apply_override(
        AgentCatalogRecord(
            agent_id="trinity-core",
            name="Trinity",
            tier="trinity",
            runtime_status="active",
            quality_status="stable",
            source="core",
            path=str(root),
            description="Trinity selbst: FrontUI, Router, Memory, LLM-Kontext und lokale Orchestrierung.",
            allowed_tools=["llm", "memory", "stt", "tts", "payloads"],
            allowed_paths=["core", "memory", "RAG", "TrinityRuntime"],
            requires_approval=["send_mail", "delete", "external_upload", "publish"],
            risk_level="medium",
            max_attempts=1,
            parallel_runs=1,
            **stats.get("trinity-core", {}),
            synthetic=True,
        ),
        overrides,
    )


def _agent_builder_record(root: Path, overrides: dict, stats: dict, synthetic: bool) -> AgentCatalogRecord:
    path = root / "skills" / "shared" / "agent-builder"
    return _apply_override(
        AgentCatalogRecord(
            agent_id="agent-builder",
            name="Agentenbuilder",
            tier="shared",
            runtime_status="active" if path.exists() else "missing",
            quality_status="testing",
            source="managed",
            path=str(path),
            description="Erfasst neue Agentenanforderungen, erstellt Plan/Quality-Gates und bereitet Staging-Freigaben vor.",
            allowed_tools=["filesystem", "tests", "harness", "job_manager"],
            allowed_paths=["BrainVault/.agents", "TrinityRuntime/jobs"],
            requires_approval=["activate_skill", "write_code"],
            risk_level="medium",
            max_attempts=3,
            parallel_runs=1,
            valid=path.exists(),
            errors=[] if path.exists() else ["Agentenbuilder-Skill fehlt auf Datentraeger."],
            synthetic=synthetic,
            **stats.get("agent-builder", {}),
        ),
        overrides,
    )


def _brainvault_records(
    root: Path,
    config: dict,
    overrides: dict,
    stats: dict,
    seen: set[str],
) -> list[AgentCatalogRecord]:
    try:
        brainvault_root = brainvault_root_from_config(root, config)
        agents = list_agents(brainvault_root)
    except Exception:
        return []
    records: list[AgentCatalogRecord] = []
    for agent in agents:
        agent_id = str(agent.get("id") or "").strip()
        if not agent_id or agent_id in seen:
            continue
        status = str(agent.get("status") or "draft")
        quality = "stable" if status == "active" and agent.get("enabled") else "testing"
        permissions = agent.get("permissions") if isinstance(agent.get("permissions"), dict) else {}
        records.append(
            _apply_override(
                AgentCatalogRecord(
                    agent_id=agent_id,
                    name=str(agent.get("name") or agent_id),
                    tier="brainvault",
                    runtime_status=status,
                    quality_status=quality,
                    source="brainvault",
                    path=str(agent.get("absolute_path") or ""),
                    description=str(agent.get("description") or ""),
                    allowed_tools=["filesystem", "harness"],
                    allowed_paths=_string_list(permissions.get("read")) + _string_list(permissions.get("write")),
                    requires_approval=_string_list(agent.get("approval_required")),
                    risk_level="medium",
                    valid=True,
                    enabled=bool(agent.get("enabled", False)),
                    execution_scope=str(agent.get("execution_scope") or "shared_harness"),
                    workspace=str(agent.get("workspace") or ""),
                    compatible_harnesses=_string_list(agent.get("compatible_harnesses")),
                    preferred_harness=str(agent.get("preferred_harness") or "auto"),
                    natural_triggers=_string_list(agent.get("natural_triggers")),
                    slash_triggers=_string_list(agent.get("slash_triggers")),
                    examples=_string_list(agent.get("examples")),
                    forbidden=_string_list(agent.get("forbidden")),
                    last_validated=str(agent.get("last_validated") or ""),
                    **stats.get(agent_id, {}),
                ),
                overrides,
            )
        )
        seen.add(agent_id)
    return records


def _record_from_skill(record: SkillRecord, overrides: dict, stats: dict) -> AgentCatalogRecord:
    tier = "legacy" if record.legacy else record.manifest.tier
    runtime_status = record.manifest.status
    if not record.valid:
        runtime_status = "invalid"
    agent_id = record.manifest.skill_id
    return _apply_override(
        AgentCatalogRecord(
            agent_id=agent_id,
            name=record.manifest.name.replace("_", " "),
            tier=tier,
            runtime_status=runtime_status,
            quality_status="stable" if record.legacy or record.is_active else "testing",
            source=record.manifest.source,
            path=str(record.directory),
            description=record.manifest.description,
            allowed_tools=list(record.manifest.allowed_tools),
            allowed_paths=list(record.manifest.allowed_paths),
            requires_approval=list(record.manifest.requires_approval),
            risk_level=record.manifest.risk_level,
            valid=record.valid,
            errors=list(record.errors),
            legacy=record.legacy,
            parent_agent=str(record.manifest.raw.get("parent_agent") or ""),
            subagents=_string_list(record.manifest.raw.get("subagents")),
            source_agent_path=str(record.manifest.raw.get("source_agent_path") or ""),
            **stats.get(agent_id, {}),
        ),
        overrides,
    )


def _apply_override(record: AgentCatalogRecord, overrides: dict) -> AgentCatalogRecord:
    values = overrides.get(record.agent_id, {}) if isinstance(overrides, dict) else {}
    if not isinstance(values, dict):
        return record
    if "quality_status" in values:
        record.quality_status = normalize_quality_status(values.get("quality_status"))
    for attr in ("allowed_tools", "allowed_paths", "requires_approval"):
        if attr in values:
            setattr(record, attr, _string_list(values.get(attr)))
    record.max_attempts = _bounded_int(values.get("max_attempts"), record.max_attempts, 1, 20)
    record.parallel_runs = _bounded_int(values.get("parallel_runs"), record.parallel_runs, 1, 20)
    return record


def _job_stats(root: Path) -> dict[str, dict[str, int]]:
    db_path = root / "memory" / "jobs.sqlite3"
    if not db_path.is_file():
        return {}
    result: dict[str, dict[str, int]] = {}
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute("SELECT route, status, COUNT(*) FROM jobs GROUP BY route, status").fetchall()
    except sqlite3.Error:
        return {}
    for route, status, count in rows:
        agent_id = _agent_id_for_route(route)
        bucket = result.setdefault(agent_id, {"job_total": 0, "job_open": 0, "job_failed": 0})
        bucket["job_total"] += int(count)
        if status not in {"SUCCEEDED", "FAILED", "NEEDS_ESCALATION", "CANCELLED"}:
            bucket["job_open"] += int(count)
        if status in {"FAILED", "NEEDS_ESCALATION"}:
            bucket["job_failed"] += int(count)
    return result


def _agent_id_for_route(route: str) -> str:
    mapping = {
        "local": "trinity-core",
        "codex": "legacy-codex-agent",
        "opencode": "legacy-opencode-agent",
        "pi": "legacy-pi-agent",
        "agent_forge": "agent-builder",
        "agent_builder": "agent-builder",
    }
    return mapping.get(str(route or "").strip(), "trinity-core")


def _string_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _bounded_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))
