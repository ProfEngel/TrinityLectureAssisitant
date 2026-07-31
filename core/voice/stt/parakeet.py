"""Parakeet settings consumed by the upstream speech-to-speech pipeline."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ParakeetSTTConfig:
    model: str = "mlx-community/parakeet-tdt-0.6b-v3"
    language: str = "de"
    live_transcription: bool = True
