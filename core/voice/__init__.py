"""Optional low-latency voice runtime for Trinity.

The package deliberately imports no ML dependencies at module import time.  A
normal Trinity installation therefore keeps using the legacy STT/TTS path until
the user selects an Eve profile and installs the optional voice dependencies.
"""

from .config import VoiceConfig, VoiceProfile, load_voice_config

__all__ = ["VoiceConfig", "VoiceProfile", "load_voice_config"]
