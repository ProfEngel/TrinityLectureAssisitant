"""Transport-neutral event envelope used by Trinity Voice."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


EVENT_TYPES = {
    "session.created", "session.updated", "input_audio.started", "input_audio.stopped",
    "transcript.partial", "transcript.final", "assistant.text.delta", "assistant.text.final",
    "tool.started", "tool.completed", "tool.failed", "audio.started", "audio.chunk",
    "audio.completed", "response.cancelled", "error",
}


@dataclass(frozen=True)
class VoiceEvent:
    type: str
    session_id: str
    turn_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.type not in EVENT_TYPES:
            raise ValueError(f"Unbekannter Voice-Eventtyp: {self.type}")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
