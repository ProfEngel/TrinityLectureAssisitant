"""Operating-system integrations used by Trinity."""

from .capabilities import (
    capability_message,
    detect_capabilities,
    find_codex_executable,
    find_opencode_executable,
)
from .tts import create_tts_backend

__all__ = [
    "capability_message",
    "create_tts_backend",
    "detect_capabilities",
    "find_codex_executable",
    "find_opencode_executable",
]
