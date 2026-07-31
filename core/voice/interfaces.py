"""Stable interfaces around the replaceable stages of Trinity Voice."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str = "de"
    confidence: float | None = None


class SpeechToTextBackend(ABC):
    @abstractmethod
    def transcribe(self, pcm16: bytes, sample_rate: int = 16_000) -> Transcript:
        """Return a final transcript for one speech turn."""


class ConversationBackend(ABC):
    @abstractmethod
    def respond(self, text: str, *, session_id: str = "", turn_id: str = "") -> Iterable[str]:
        """Yield speakable German response segments."""


class TextToSpeechBackend(ABC):
    @abstractmethod
    def synthesize(self, text: str, *, turn_id: str = "") -> Iterable[bytes]:
        """Yield encoded or PCM audio chunks for one turn."""

    def cancel(self, turn_id: str) -> None:
        """Cancel queued output for a superseded turn when supported."""


class VoiceTransport(ABC):
    @abstractmethod
    def run(self, service: Any) -> None:
        """Serve a voice service until it is stopped."""

    @abstractmethod
    def stop(self) -> None:
        """Stop accepting and emitting audio."""
