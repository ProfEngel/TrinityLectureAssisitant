"""Configuration and platform profiles for the optional Eve voice runtime."""

from __future__ import annotations

import copy
import os
import platform
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


EVE_REFERENCE_TEXT = (
    "Herzlich willkommen lieber Schülerinnen und Schüler des Max Planck Gymnasiums. "
    "Schön, dass Ihr heute hier seid. Unser Schülervortrag dreht sich um das Thema "
    "KI und Wir. Lasst uns gemeinsam entdecken wie künstliche Intelligenz unseren "
    "Alltag verändert."
)

DEFAULT_PROFILES: dict[str, dict[str, Any]] = {
    "eve-mac-local": {
        "mode": "local",
        "device": "mps",
        "conversation_backend": "trinity",
        "bind_host": "127.0.0.1",
        "public_port": 8766,
        "internal_port": 18766,
        "stt_model": "mlx-community/parakeet-tdt-0.6b-v3",
        "tts_model": "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-6bit",
        "tts_backend": "ggml",
    },
    "eve-mac-server": {
        "mode": "realtime",
        "device": "mps",
        "conversation_backend": "trinity",
        "bind_host": "127.0.0.1",
        "public_port": 8766,
        "internal_port": 18766,
        "stt_model": "mlx-community/parakeet-tdt-0.6b-v3",
        "tts_model": "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-6bit",
        "tts_backend": "ggml",
    },
    "eve-windows-server": {
        "mode": "realtime",
        "device": "cuda",
        "conversation_backend": "trinity",
        "bind_host": "127.0.0.1",
        "public_port": 8766,
        "internal_port": 18766,
        "stt_model": "nvidia/parakeet-tdt-0.6b-v3",
        "tts_model": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        "tts_backend": "torch",
    },
    "eve-direct-ornith": {
        "mode": "local",
        "device": "mps",
        "conversation_backend": "direct",
        "bind_host": "127.0.0.1",
        "public_port": 8766,
        "internal_port": 18766,
        "stt_model": "mlx-community/parakeet-tdt-0.6b-v3",
        "tts_model": "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-6bit",
        "tts_backend": "ggml",
    },
    "eve-trinity": {
        "mode": "local",
        "device": "auto",
        "conversation_backend": "trinity",
        "bind_host": "127.0.0.1",
        "public_port": 8766,
        "internal_port": 18766,
        "stt_model": "mlx-community/parakeet-tdt-0.6b-v3",
        "tts_model": "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-6bit",
        "tts_backend": "ggml",
    },
}


def _expand_path(value: str | os.PathLike[str] | None, home: Path) -> Path:
    raw = os.path.expandvars(str(value or "")).strip()
    if not raw:
        return Path()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = home / path
    return path.resolve()


def _loopback(host: str) -> bool:
    return host.strip().lower() in {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class VoiceProfile:
    name: str
    mode: str
    device: str
    conversation_backend: str
    bind_host: str
    public_port: int
    internal_port: int
    stt_model: str
    tts_model: str
    tts_backend: str


@dataclass
class VoiceConfig:
    home: Path
    engine: str = "legacy"
    profile_name: str = "eve-trinity"
    fallback_to_legacy: bool = True
    language_policy: str = "de_only"
    access_token: str = ""
    backend_host: str = "127.0.0.1"
    backend_port: int = 18767
    backend_token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    stt_model: str = "mlx-community/parakeet-tdt-0.6b-v3"
    tts_model: str = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-6bit"
    reference_audio: Path = field(default_factory=Path)
    reference_text: str = EVE_REFERENCE_TEXT
    streaming_chunk_size: int = 8
    audio_prebuffer_ms: int = 180
    speech_to_speech_executable: str = ""
    direct_llm_base_url: str = "http://127.0.0.1:8080/v1"
    direct_llm_model: str = "mlx-community/Ornith-1.0-35B-4bit"
    direct_llm_api_key: str = ""
    first_response_max_sentences: int = 4
    profiles: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def enabled(self) -> bool:
        return self.engine == "eve"

    @property
    def profile(self) -> VoiceProfile:
        raw = copy.deepcopy(DEFAULT_PROFILES.get(self.profile_name, DEFAULT_PROFILES["eve-trinity"]))
        raw.update(self.profiles.get(self.profile_name, {}))
        device = str(raw.get("device") or "auto")
        if device == "auto":
            device = "mps" if platform.system() == "Darwin" else "cuda" if platform.system() == "Windows" else "cpu"
        if self.profile_name == "eve-trinity" and platform.system() != "Darwin":
            raw["stt_model"] = "nvidia/parakeet-tdt-0.6b-v3"
            raw["tts_model"] = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
            raw["tts_backend"] = "torch"
        return VoiceProfile(
            name=self.profile_name,
            mode=str(raw.get("mode") or "local"),
            device=device,
            conversation_backend=str(raw.get("conversation_backend") or "trinity"),
            bind_host=str(raw.get("bind_host") or "127.0.0.1"),
            public_port=int(raw.get("public_port") or 8766),
            internal_port=int(raw.get("internal_port") or 18766),
            stt_model=str(raw.get("stt_model") or self.stt_model),
            tts_model=str(raw.get("tts_model") or self.tts_model),
            tts_backend=str(raw.get("tts_backend") or "ggml"),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        profile = self.profile
        if self.engine not in {"legacy", "eve"}:
            errors.append("voice.engine muss legacy oder eve sein.")
        if self.language_policy != "de_only":
            errors.append("Aktuell wird nur voice.language_policy=de_only unterstützt.")
        if profile.mode not in {"local", "realtime"}:
            errors.append(f"Unbekannter Voice-Modus: {profile.mode}")
        if profile.conversation_backend not in {"trinity", "direct"}:
            errors.append(f"Unbekanntes Conversation-Backend: {profile.conversation_backend}")
        if profile.mode == "realtime" and not _loopback(profile.bind_host) and not self.access_token:
            errors.append("Ein extern gebundener Voice-Server braucht voice.access_token.")
        if self.enabled and not self.reference_audio.is_file():
            errors.append(f"Eve-Referenzaudio fehlt: {self.reference_audio or '(nicht konfiguriert)'}")
        if self.enabled and not self.reference_text.strip():
            errors.append("Eve-Referenztranskript fehlt.")
        if not 1 <= int(self.streaming_chunk_size) <= 64:
            errors.append("voice.streaming_chunk_size muss zwischen 1 und 64 liegen.")
        if not 0 <= int(self.audio_prebuffer_ms) <= 2000:
            errors.append("voice.audio_prebuffer_ms muss zwischen 0 und 2000 liegen.")
        if profile.tts_backend not in {"ggml", "torch"}:
            errors.append("voice.profiles.<name>.tts_backend muss ggml oder torch sein.")
        return errors


def default_voice_config() -> dict[str, Any]:
    return {
        "engine": "legacy",
        "profile": "eve-trinity",
        "fallback_to_legacy": True,
        "language_policy": "de_only",
        "access_token": "",
        "backend_host": "127.0.0.1",
        "backend_port": 18767,
        "stt_model": "mlx-community/parakeet-tdt-0.6b-v3",
        "tts_model": "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-6bit",
        "reference_audio": "",
        "reference_text": EVE_REFERENCE_TEXT,
        "streaming_chunk_size": 8,
        "audio_prebuffer_ms": 180,
        "speech_to_speech_executable": "",
        "direct_llm_base_url": "http://127.0.0.1:8080/v1",
        "direct_llm_model": "mlx-community/Ornith-1.0-35B-4bit",
        "direct_llm_api_key": "",
        "first_response_max_sentences": 4,
        "profiles": copy.deepcopy(DEFAULT_PROFILES),
    }


def load_voice_config(home: str | Path, config: dict[str, Any], profile_name: str | None = None) -> VoiceConfig:
    root = Path(home).expanduser().resolve()
    raw = copy.deepcopy(default_voice_config())
    incoming = config.get("voice") if isinstance(config, dict) else {}
    if isinstance(incoming, dict):
        for key, value in incoming.items():
            if key == "profiles" and isinstance(value, dict):
                for name, profile in value.items():
                    if isinstance(profile, dict):
                        raw["profiles"].setdefault(name, {}).update(profile)
            else:
                raw[key] = value

    env_profile = os.environ.get("TRINITY_VOICE_PROFILE", "").strip()
    selected_profile = profile_name or env_profile or str(raw.get("profile") or "eve-trinity")
    env_audio = (
        os.environ.get("TRINITY_EVE_VOICE_FILE", "").strip()
        or os.environ.get("TRINITY_EVE_REFERENCE_AUDIO", "").strip()
    )
    configured_audio = env_audio or str(raw.get("reference_audio") or "")
    if not configured_audio:
        configured_audio = str(root / "TrinityRuntime" / "voices" / "eve" / "Eve_Schule.mp3")

    reference_text = str(raw.get("reference_text") or EVE_REFERENCE_TEXT)
    transcript_file = os.environ.get("TRINITY_EVE_TRANSCRIPT_FILE", "").strip()
    if transcript_file:
        transcript_path = _expand_path(transcript_file, root)
        if transcript_path.is_file():
            reference_text = transcript_path.read_text(encoding="utf-8").strip()

    profiles = raw["profiles"]
    env_tts_model = os.environ.get("TRINITY_TTS_MODEL", "").strip()
    if env_tts_model:
        profiles.setdefault(selected_profile, {})["tts_model"] = env_tts_model

    return VoiceConfig(
        home=root,
        engine=str(os.environ.get("TRINITY_VOICE_ENGINE") or raw.get("engine") or "legacy").strip().lower(),
        profile_name=selected_profile,
        fallback_to_legacy=bool(raw.get("fallback_to_legacy", True)),
        language_policy=str(raw.get("language_policy") or "de_only"),
        access_token=str(
            os.environ.get("TRINITY_VOICE_ACCESS_TOKEN")
            or os.environ.get("TRINITY_VOICE_TOKEN")
            or raw.get("access_token")
            or ""
        ),
        backend_host=str(raw.get("backend_host") or "127.0.0.1"),
        backend_port=int(raw.get("backend_port") or 18767),
        stt_model=str(raw.get("stt_model") or "mlx-community/parakeet-tdt-0.6b-v3"),
        tts_model=str(raw.get("tts_model") or "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-6bit"),
        reference_audio=_expand_path(configured_audio, root),
        reference_text=reference_text,
        streaming_chunk_size=int(raw.get("streaming_chunk_size") or 8),
        audio_prebuffer_ms=int(raw.get("audio_prebuffer_ms") if raw.get("audio_prebuffer_ms") is not None else 180),
        speech_to_speech_executable=str(raw.get("speech_to_speech_executable") or ""),
        direct_llm_base_url=str(
            os.environ.get("TRINITY_LLM_BASE_URL")
            or raw.get("direct_llm_base_url")
            or "http://127.0.0.1:8080/v1"
        ),
        direct_llm_model=str(
            os.environ.get("TRINITY_LLM_MODEL")
            or raw.get("direct_llm_model")
            or "mlx-community/Ornith-1.0-35B-4bit"
        ),
        direct_llm_api_key=str(
            os.environ.get("TRINITY_LLM_API_KEY")
            or raw.get("direct_llm_api_key")
            or ""
        ),
        first_response_max_sentences=int(raw.get("first_response_max_sentences") or 4),
        profiles=profiles,
    )
