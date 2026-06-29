"""Trinity control plane foundation.

This layer keeps UI, jobs, policies, vault layout and harness adapters separate.
It deliberately does not migrate existing Ideaverse/CampusHub agents by itself.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from agent_catalog import build_agent_catalog
from artifact_store import ArtifactStore
from brainvault_agents import (
    brainvault_root_from_config,
    build_catalog as build_brainvault_catalog,
    ensure_brainvault_layout,
)
from configuration import load_config
from harness_adapters import BuilderHarnessAdapter, ScriptWorkflowAdapter
from job_manager import JobManager
from policy_engine import PolicyEngine
from skill_registry import SkillRegistry
from trinity_paths import TrinityPaths


class TrinityControlPlane:
    """Central coordination object for the harness-agnostic Trinity foundation."""

    def __init__(self, home: str | Path, config: Optional[dict] = None):
        self.home = Path(home).expanduser().resolve()
        self.config = config or load_config(self.home / "core" / "config.json")
        self.paths = TrinityPaths.from_config(self.home, self.config)
        self.brainvault_root = brainvault_root_from_config(self.home, self.config)
        self.registry = SkillRegistry(self.home)
        self.jobs = JobManager(self.paths.runtime_root)
        self.artifacts = ArtifactStore(self.paths.vault_root)
        self.policy = PolicyEngine()
        self.adapters = {
            "script-workflow": ScriptWorkflowAdapter(),
            "builder": BuilderHarnessAdapter(),
        }

    def ensure_foundation(self) -> dict:
        layout = self.paths.ensure_layout()
        brainvault_layout = ensure_brainvault_layout(self.brainvault_root)
        brainvault_catalog = build_brainvault_catalog(self.brainvault_root)
        self.artifacts.ensure()
        self._write_vault_readme()
        catalog = self.export_agent_catalog()
        self._write_default_policy()
        self._write_default_model_profile()
        return {
            "layout": layout,
            "brainvault": {
                "root": brainvault_layout["root"],
                "catalog": brainvault_catalog["path"],
                "agent_count": brainvault_catalog["summary"].get("total", 0),
            },
            "catalog": {
                "path": str(self.agent_catalog_path),
                "agent_count": len(catalog["agents"]),
                "legacy_count": catalog["summary"].get("legacy", 0),
            },
            "adapters": self.adapter_health(),
        }

    def status(self) -> dict:
        self.registry.reload()
        return {
            "paths": self.paths.summary(),
            "catalog_path": str(self.agent_catalog_path),
            "catalog_exists": self.agent_catalog_path.is_file(),
            "registry": self.registry.summary(),
            "adapters": self.adapter_health(),
            "artifact_index": str(self.artifacts.index_path),
        }

    def export_agent_catalog(self) -> dict:
        records = build_agent_catalog(self.home, self.config)
        summary = {"total": len(records)}
        for record in records:
            summary[record.tier] = summary.get(record.tier, 0) + 1
        catalog = {
            "schema_version": 2,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "source_home": str(self.home),
            "summary": summary,
            "agents": [asdict(record) for record in records],
        }
        self.agent_catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.agent_catalog_path.write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return catalog

    def adapter_health(self) -> dict:
        result = {}
        for adapter_id, adapter in self.adapters.items():
            health = adapter.health_check()
            result[adapter_id] = {
                "ok": health.ok,
                "message": health.message,
                "details": health.details,
            }
        return result

    def status_card(self, job_id: str) -> dict:
        job = self.jobs.get(job_id)
        current_step = next(
            (step for step in job["steps"] if step["status"] not in {"SUCCEEDED", "SKIPPED"}),
            None,
        )
        completed = sum(step["status"] == "SUCCEEDED" for step in job["steps"])
        total = len(job["steps"])
        return {
            "title": job["title"],
            "status": _status_label(job["status"]),
            "progress": f"{completed} von {total} Schritten" if total else "Keine Schritte",
            "mode": job["metadata"].get("mode", job["route"]),
            "current_step": (current_step or {}).get("title", "Abgeschlossen"),
            "job_id": job["job_id"],
        }

    def register_artifact(
        self,
        job_id: str,
        kind: str,
        title: str,
        source_path: str = "",
        url: str = "",
        metadata: Optional[dict] = None,
    ) -> dict:
        return self.artifacts.register(
            job_id,
            kind,
            title,
            source_path=source_path,
            url=url,
            metadata=metadata or {},
        ).as_dict()

    @property
    def agent_catalog_path(self) -> Path:
        return self.paths.vault_root / "00_registry" / "agent_catalog.json"

    def _write_vault_readme(self) -> None:
        path = self.paths.vault_root / "README.md"
        if path.exists():
            return
        path.write_text(
            "# TrinityVault\n\n"
            "Synchronisierte Nutzerablage fuer freigegebene Trinity-Agenten, "
            "Projekte, Ergebnisse, Vorlagen, Wissensbestaende, Audit-Berichte "
            "und Exporte.\n\n"
            "Nicht hier ablegen: API-Keys, Secrets, aktive Datenbanken, laufende "
            "Sessions, temporaere Dateien oder aktive Job-Workspaces.\n",
            encoding="utf-8",
        )

    def _write_default_policy(self) -> None:
        path = self.paths.vault_root / "00_registry" / "policies" / "default_policy.json"
        if path.exists():
            return
        policy = {
            "schema_version": 1,
            "green_autonomous": [
                "analyze",
                "summarize",
                "create_artifact",
                "read_file",
            ],
            "yellow_requires_approval": [
                "move_file",
                "delete",
                "send_mail",
                "external_upload",
                "publish",
                "cloud_model",
                "activate_skill",
                "share_skill",
                "network_access",
            ],
            "red_denied": [
                "install_package",
                "system_command",
                "final_grade_submission",
                "payment",
                "legal_signature",
            ],
        }
        path.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _write_default_model_profile(self) -> None:
        path = self.paths.vault_root / "00_registry" / "model_profiles" / "local-default.json"
        if path.exists():
            return
        llm = self.config.get("llm", {})
        active = llm.get("active_slot", "local")
        provider = llm.get(active, {}) if isinstance(llm.get(active), dict) else {}
        profile = {
            "id": "local-default",
            "provider": "openai-compatible",
            "model": provider.get("model", ""),
            "purpose": ["routing", "planning", "text_generation", "review"],
            "capabilities": {
                "tool_use": True,
                "json_mode": True,
                "vision": False,
                "long_context": True,
                "reasoning": True,
            },
            "limits": {
                "max_parallel_agent_jobs": 2,
                "context_window": 65536,
            },
        }
        path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _status_label(status: str) -> str:
    mapping = {
        "PENDING": "wartet",
        "QUEUED": "in Warteschlange",
        "RUNNING": "laeuft",
        "WAITING_FOR_INPUT": "wartet auf Eingabe",
        "WAITING_FOR_APPROVAL": "wartet auf Freigabe",
        "SUCCEEDED": "abgeschlossen",
        "FAILED": "fehlgeschlagen",
        "NEEDS_ESCALATION": "braucht Aufmerksamkeit",
        "CANCELLED": "abgebrochen",
    }
    return mapping.get(str(status).upper(), str(status).lower())
