"""Operating-system integrations used by Trinity."""

from .capabilities import capability_message, detect_capabilities
from .tts import create_tts_backend

__all__ = [
    "capability_message",
    "create_tts_backend",
    "detect_capabilities",
]
