"""Conversation-path latency benchmark without loading STT or TTS models."""

from __future__ import annotations

import json
import statistics
import time

from .config import VoiceConfig
from .conversation import DirectLLMConversationBackend, TrinityConversationBackend


def benchmark(config: VoiceConfig, rounds: int = 1, prompt: str = "Antworte nur mit: bereit") -> int:
    if config.profile.conversation_backend == "direct":
        backend = DirectLLMConversationBackend(
            config.direct_llm_base_url,
            config.direct_llm_model,
            config.direct_llm_api_key,
        )
    else:
        backend = TrinityConversationBackend(config.home)
    samples = []
    lengths = []
    for _index in range(max(1, int(rounds))):
        started = time.perf_counter()
        answer = " ".join(backend.respond(prompt))
        samples.append((time.perf_counter() - started) * 1000)
        lengths.append(len(answer))
    result = {
        "profile": config.profile.name,
        "conversation_backend": config.profile.conversation_backend,
        "rounds": len(samples),
        "median_ms": round(statistics.median(samples), 1),
        "min_ms": round(min(samples), 1),
        "max_ms": round(max(samples), 1),
        "response_chars": lengths,
        "note": "Misst den Conversation-Pfad; STT/TTS-Kaltstart wird separat im Live-Test sichtbar.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
