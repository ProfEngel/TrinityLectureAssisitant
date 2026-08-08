"""Start speech-to-speech without requiring the remote Trinity Core at boot."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any


LOGGER = logging.getLogger(__name__)


def tolerate_remote_warmup(handler_class: type[Any]) -> Callable[..., Any]:
    """Skip the optional remote-Core warm-up entirely.

    Normal conversation requests still use the configured authenticated Core.
    The remote endpoint must not consume the GPU server's startup budget or
    determine whether STT/TTS and the WebSocket gateway can become ready.
    """

    original = handler_class.warmup

    def resilient_warmup(_self) -> None:
        LOGGER.info(
            "Remote Trinity Core warm-up skipped; Eve starts independently "
            "and connects when the Windows VM is available."
        )

    handler_class.warmup = resilient_warmup
    return original


def prefer_shared_gpu_ggml_quantization(
    model_class: type[Any],
    quant: str,
) -> Callable[..., Any]:
    """Select an explicitly configured GGUF for a shared-GPU server."""

    original = model_class.from_pretrained

    def shared_gpu_loader(_class, *args, **kwargs):
        if kwargs.get("backend") == "ggml":
            kwargs.setdefault("quant", quant)
        return original(*args, **kwargs)

    model_class.from_pretrained = classmethod(shared_gpu_loader)
    return original


def main() -> None:
    from faster_qwen3_tts import FasterQwen3TTS
    from speech_to_speech.LLM.chat_completions_language_model import (
        ChatCompletionsApiModelHandler,
    )
    from speech_to_speech.s2s_pipeline import main as upstream_main

    tolerate_remote_warmup(ChatCompletionsApiModelHandler)
    quant = os.environ.get("TRINITY_QWENTTS_QUANT", "").strip()
    if quant:
        prefer_shared_gpu_ggml_quantization(FasterQwen3TTS, quant)
    upstream_main()


if __name__ == "__main__":
    main()
