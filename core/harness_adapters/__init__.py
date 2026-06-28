"""Harness adapter interfaces for Trinity's control plane."""

from .base import (
    AgentHarnessAdapter,
    HarnessArtifact,
    HarnessHealth,
    HarnessJobEvent,
    HarnessJobHandle,
    HarnessJobRequest,
    HarnessJobStatus,
)
from .builder import BuilderHarnessAdapter
from .script_workflow import ScriptWorkflowAdapter

__all__ = [
    "AgentHarnessAdapter",
    "BuilderHarnessAdapter",
    "HarnessArtifact",
    "HarnessHealth",
    "HarnessJobEvent",
    "HarnessJobHandle",
    "HarnessJobRequest",
    "HarnessJobStatus",
    "ScriptWorkflowAdapter",
]
