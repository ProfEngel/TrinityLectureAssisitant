"""First safe adapter for Trinity's agent-builder workflow."""

from __future__ import annotations

import uuid

from .base import HarnessArtifact, HarnessHealth, HarnessJobHandle, HarnessJobRequest
from .script_workflow import ScriptWorkflowAdapter


class BuilderHarnessAdapter(ScriptWorkflowAdapter):
    """Create reviewable agent capability requests without activating code."""

    id = "builder"
    display_name = "Agent Builder Harness"

    def __init__(self):
        super().__init__({"capability-request": self._capability_request})

    def health_check(self) -> HarnessHealth:
        return HarnessHealth(
            ok=True,
            message="Agent Builder bereit; erzeugt sichere Entwuerfe zur Freigabe.",
            details={"maturity": "draft", "activates_code": False},
        )

    def start_job(self, request: HarnessJobRequest) -> HarnessJobHandle:
        if not request.metadata.get("workflow"):
            request = HarnessJobRequest(
                agent_id=request.agent_id,
                title=request.title,
                prompt=request.prompt,
                mode=request.mode,
                workspace=request.workspace,
                inputs=request.inputs,
                allowed_tools=request.allowed_tools,
                allowed_paths=request.allowed_paths,
                metadata={**request.metadata, "workflow": "capability-request"},
            )
        handle = super().start_job(request)
        return HarnessJobHandle(handle.job_id, self.id, handle.status)

    def _capability_request(self, request: HarnessJobRequest) -> dict:
        title = request.title.strip() or "Neuer Agentenwunsch"
        prompt = request.prompt.strip()
        artifact = HarnessArtifact(
            artifact_id=f"capability_{uuid.uuid4().hex}",
            kind="capability_request",
            title=title,
            metadata={
                "agent_id": request.agent_id,
                "mode": request.mode,
                "workspace": request.workspace,
                "prompt": prompt,
                "next_steps": [
                    "Agentenvertrag erstellen",
                    "Tests und Fixtures definieren",
                    "Policy und Freigaben pruefen",
                    "Als Staging-Agent ablegen",
                ],
            },
        )
        return {
            "summary": f"Capability Request vorbereitet: {title}",
            "artifacts": [
                {
                    "artifact_id": artifact.artifact_id,
                    "kind": artifact.kind,
                    "title": artifact.title,
                    "metadata": artifact.metadata,
                }
            ],
        }
