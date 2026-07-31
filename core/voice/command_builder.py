"""Build the pinned upstream speech-to-speech command without shell parsing."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from .config import VoiceConfig


def _entrypoint(config: VoiceConfig) -> list[str]:
    configured = config.speech_to_speech_executable.strip()
    if configured:
        return shlex.split(configured)
    return [sys.executable, "-m", "speech_to_speech.s2s_pipeline"]


def build_speech_to_speech_command(config: VoiceConfig) -> list[str]:
    """Return a deterministic argv list for speech-to-speech 0.2.11."""

    profile = config.profile
    command = _entrypoint(config)
    command.extend([
        "--mode", profile.mode,
        "--device", profile.device,
        "--stt", "parakeet-tdt",
        "--parakeet_tdt_model_name", profile.stt_model,
        "--parakeet_tdt_device", profile.device,
        "--parakeet_tdt_language", "de",
        "--language", "de",
        "--enable_live_transcription", "true",
        "--live_transcription_update_interval", "0.25",
        "--live_transcription_min_silence_ms", "420",
        "--min_silence_ms", "96",
        "--speech_pad_ms", "320",
        "--llm_backend", "chat-completions",
        "--model_name", "trinity-core" if profile.conversation_backend == "trinity" else config.direct_llm_model,
        "--responses_api_base_url",
        (
            f"http://{config.backend_host}:{config.backend_port}/v1"
            if profile.conversation_backend == "trinity"
            else config.direct_llm_base_url.rstrip("/")
        ),
        "--responses_api_api_key",
        config.backend_token if profile.conversation_backend == "trinity" else (config.direct_llm_api_key or "local"),
        "--responses_api_stream", "true",
        "--responses_api_disable_thinking", "true",
        "--init_chat_prompt",
        "Du bist die Sprachoberfläche von Trinity. Antworte ausschließlich auf Deutsch, knapp und natürlich.",
        "--stream_batch_sentences", "1",
        "--tts", "qwen3",
        "--qwen3_tts_model_name", profile.tts_model,
        "--qwen3_tts_device", profile.device,
        "--qwen3_tts_backend", profile.tts_backend,
        "--qwen3_tts_ref_audio", str(Path(config.reference_audio)),
        "--qwen3_tts_ref_text", config.reference_text,
        "--qwen3_tts_language", "German",
        "--qwen3_tts_streaming_chunk_size", str(config.streaming_chunk_size),
        "--log_level", "info",
    ])
    if profile.mode == "realtime":
        command.extend([
            "--ws_host", "127.0.0.1",
            "--ws_port", str(profile.internal_port),
            "--num_pipelines", "1",
        ])
    return command
