"""Public, secret-free compatibility information for microphone-only clients."""
from .config import load_voice_config


def transcription_stream_capability(home, config):
    voice = load_voice_config(home, config)
    profile = voice.profile
    # The bundled entrypoint installs the transcription-only guard. A custom
    # executable or remote upstream has not made that guarantee.
    if (not voice.enabled or profile.mode != "realtime"
            or profile.runtime_role == "client" or voice.speech_to_speech_executable):
        return None
    return {"protocol": "trinity-stt-v1", "port": profile.public_port,
            "sample_rate": 16000, "transcription_only": True}
