"""Validated Qwen3-TTS voice-clone settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class QwenVoiceCloneConfig:
    model: str
    reference_audio: Path
    reference_text: str
    language: str = "de"
    streaming_chunk_size: int = 8

    def validate(self) -> None:
        if not self.reference_audio.is_file():
            raise FileNotFoundError(f"Eve-Referenzaudio fehlt: {self.reference_audio}")
        if not self.reference_text.strip():
            raise ValueError("Das Eve-Referenztranskript ist leer.")
        if self.language != "de":
            raise ValueError("Das Eve-Profil unterstützt ausschließlich Deutsch.")
