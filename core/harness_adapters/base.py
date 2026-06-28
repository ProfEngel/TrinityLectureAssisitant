"""Harness-agnostic contracts used by the Trinity control plane."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass(frozen=True)
class HarnessHealth:
    ok: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HarnessJobRequest:
    agent_id: str
    title: str
    prompt: str = ""
    mode: str = "guided"
    workspace: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    allowed_tools: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HarnessJobHandle:
    job_id: str
    harness_id: str
    status: str = "queued"


@dataclass(frozen=True)
class HarnessJobStatus:
    job_id: str
    status: str
    message: str = ""
    progress: Optional[float] = None


@dataclass(frozen=True)
class HarnessJobEvent:
    job_id: str
    event_type: str
    message: str
    timestamp: float = field(default_factory=time.time)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HarnessArtifact:
    artifact_id: str
    kind: str
    title: str
    path: str = ""
    url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentHarnessAdapter(Protocol):
    id: str
    display_name: str

    def health_check(self) -> HarnessHealth:
        ...

    def start_job(self, request: HarnessJobRequest) -> HarnessJobHandle:
        ...

    def get_job_status(self, job_id: str) -> HarnessJobStatus:
        ...

    def get_job_events(self, job_id: str, cursor: str = "") -> list[HarnessJobEvent]:
        ...

    def send_input(self, job_id: str, input_data: dict[str, Any]) -> None:
        ...

    def cancel_job(self, job_id: str) -> None:
        ...

    def collect_artifacts(self, job_id: str) -> list[HarnessArtifact]:
        ...
