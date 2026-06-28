"""Deterministic local workflow adapter for Trinity jobs."""

from __future__ import annotations

import traceback
import uuid
from collections.abc import Callable
from typing import Any

from .base import (
    HarnessArtifact,
    HarnessHealth,
    HarnessJobEvent,
    HarnessJobHandle,
    HarnessJobRequest,
    HarnessJobStatus,
)


Workflow = Callable[[HarnessJobRequest], dict[str, Any]]


class ScriptWorkflowAdapter:
    """Run trusted deterministic Python workflows behind the generic adapter API."""

    id = "script-workflow"
    display_name = "Lokaler Script-Workflow"

    def __init__(self, workflows: dict[str, Workflow] | None = None):
        self.workflows = workflows or {}
        self._status: dict[str, HarnessJobStatus] = {}
        self._events: dict[str, list[HarnessJobEvent]] = {}
        self._artifacts: dict[str, list[HarnessArtifact]] = {}

    def health_check(self) -> HarnessHealth:
        return HarnessHealth(
            ok=True,
            message=f"{len(self.workflows)} Script-Workflow(s) registriert.",
        )

    def start_job(self, request: HarnessJobRequest) -> HarnessJobHandle:
        job_id = f"script_{uuid.uuid4().hex}"
        self._events[job_id] = [
            HarnessJobEvent(job_id, "job_started", "Script-Workflow gestartet.")
        ]
        workflow_name = str(request.metadata.get("workflow") or request.agent_id)
        workflow = self.workflows.get(workflow_name)
        if workflow is None:
            self._status[job_id] = HarnessJobStatus(
                job_id,
                "failed",
                f"Kein Script-Workflow registriert: {workflow_name}",
            )
            self._events[job_id].append(
                HarnessJobEvent(
                    job_id,
                    "job_failed",
                    f"Workflow nicht gefunden: {workflow_name}",
                )
            )
            return HarnessJobHandle(job_id, self.id, "failed")

        self._status[job_id] = HarnessJobStatus(job_id, "running", "Workflow läuft.")
        try:
            result = workflow(request) or {}
            artifacts = [
                _artifact_from_dict(item)
                for item in result.get("artifacts", [])
                if isinstance(item, dict)
            ]
            self._artifacts[job_id] = artifacts
            message = str(result.get("summary") or "Script-Workflow abgeschlossen.")
            self._status[job_id] = HarnessJobStatus(job_id, "completed", message, 1.0)
            self._events[job_id].append(
                HarnessJobEvent(
                    job_id,
                    "job_completed",
                    message,
                    details={"artifact_count": len(artifacts)},
                )
            )
        except Exception as exc:  # pragma: no cover - defensive logging path
            self._status[job_id] = HarnessJobStatus(job_id, "failed", str(exc))
            self._events[job_id].append(
                HarnessJobEvent(
                    job_id,
                    "job_failed",
                    "Script-Workflow ist fehlgeschlagen.",
                    details={"error": str(exc), "traceback": traceback.format_exc()},
                )
            )
        return HarnessJobHandle(job_id, self.id, self._status[job_id].status)

    def get_job_status(self, job_id: str) -> HarnessJobStatus:
        return self._status.get(job_id, HarnessJobStatus(job_id, "failed", "Job unbekannt."))

    def get_job_events(self, job_id: str, cursor: str = "") -> list[HarnessJobEvent]:
        events = self._events.get(job_id, [])
        if not cursor:
            return list(events)
        try:
            offset = max(0, int(cursor))
        except ValueError:
            offset = 0
        return list(events[offset:])

    def send_input(self, job_id: str, input_data: dict[str, Any]) -> None:
        self._events.setdefault(job_id, []).append(
            HarnessJobEvent(job_id, "input_received", "Eingabe empfangen.", details=input_data)
        )

    def cancel_job(self, job_id: str) -> None:
        self._status[job_id] = HarnessJobStatus(job_id, "cancelled", "Vom Nutzer abgebrochen.")
        self._events.setdefault(job_id, []).append(
            HarnessJobEvent(job_id, "job_cancelled", "Vom Nutzer abgebrochen.")
        )

    def collect_artifacts(self, job_id: str) -> list[HarnessArtifact]:
        return list(self._artifacts.get(job_id, []))


def _artifact_from_dict(data: dict[str, Any]) -> HarnessArtifact:
    return HarnessArtifact(
        artifact_id=str(data.get("artifact_id") or data.get("id") or uuid.uuid4().hex),
        kind=str(data.get("kind") or "file"),
        title=str(data.get("title") or "Artefakt"),
        path=str(data.get("path") or ""),
        url=str(data.get("url") or ""),
        metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
    )
