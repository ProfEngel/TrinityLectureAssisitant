"""Turn ownership and stale-stream rejection."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceTurn:
    session_id: str
    turn_id: str
    revision: int


class VoiceSession:
    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or uuid.uuid4().hex
        self._revision = 0
        self._turn_id = ""
        self._lock = threading.Lock()

    def next_turn(self) -> VoiceTurn:
        with self._lock:
            self._revision += 1
            self._turn_id = uuid.uuid4().hex
            return VoiceTurn(self.session_id, self._turn_id, self._revision)

    def is_current(self, turn: VoiceTurn) -> bool:
        with self._lock:
            return turn.turn_id == self._turn_id and turn.revision == self._revision

    def current_turn(self) -> VoiceTurn | None:
        with self._lock:
            if not self._turn_id:
                return None
            return VoiceTurn(self.session_id, self._turn_id, self._revision)

    def cancel_current(self) -> None:
        with self._lock:
            self._revision += 1
            self._turn_id = ""
