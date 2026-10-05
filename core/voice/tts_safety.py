"""Do not play runaway clone synthesis; preserve the existing voice reference."""
import logging
import math
import re
import time
import os


def _status(message):
    home = os.environ.get("TRINITY_VOICE_HOME")
    if home:
        from .diagnostics import diagnostic
        diagnostic(home, "Eve TTS", message)

LOGGER = logging.getLogger(__name__)


def checked_clone_chunks(handler, text):
    import numpy as np

    words = len(re.findall(r"\w+", text))
    # Very generous slow-speech allowance. Normal Eve speaks ~2.6 words/s.
    duration_limit = max(6.0, 3.0 + words / 0.9)
    cap = min(handler._estimate_max_new_tokens(text), math.ceil(duration_limit * 12.5))
    generation = handler.cancel_scope.generation if handler.cancel_scope else None
    for attempt in range(3):
        started = time.monotonic()
        chunks = []
        duration = 0.0
        valid = True
        generator = handler.model.generate_voice_clone_streaming(
            text=text, language=handler.language, ref_audio=handler.ref_audio,
            ref_text=handler.ref_text, xvec_only=handler.xvec_only or attempt == 2,
            chunk_size=handler.streaming_chunk_size, max_new_tokens=cap,
            parity_mode=handler.parity_mode, non_streaming_mode=handler.non_streaming_mode,
            do_sample=attempt != 1, temperature=0.9 if attempt == 2 else 0.65,
            repetition_penalty=1.05 if attempt == 2 else 1.1,
        )
        try:
            for item in generator:
                if generation is not None and handler.cancel_scope.is_stale(generation):
                    return
                audio, rate = item[:2]
                audio = np.asarray(audio)
                if not np.isfinite(audio).all():
                    valid = False
                    break
                duration += audio.size / rate
                chunks.append(item)
                if duration > duration_limit:
                    valid = False
                    break
        finally:
            generator.close()
        # GGML exposes the actual generated frame count after its last chunk.
        runtime = getattr(handler.model, "runtime", None)
        profile = getattr(runtime, "last_stream_profile", {}) or {}
        frames = profile.get("generated_frames", profile.get("n_frames", 0))
        if frames and frames >= cap:
            valid = False
        if valid and chunks and duration < cap / 12.5 - 0.08:
            _status(f"Audio geprüft: {duration:.1f} s Sprache, Synthese {time.monotonic() - started:.2f} s, Versuch {attempt + 1}; wird an das Ausgabegerät gesendet.")
            LOGGER.info("Eve audio validated: %.2fs audio in %.2fs, attempt=%d",
                        duration, time.monotonic() - started, attempt + 1)
            yield from handler._stream(iter(chunks), label="voice_clone_checked")
            return
        LOGGER.warning("Rejected suspicious Eve audio: %.2fs, cap=%d, attempt=%d",
                       duration, cap, attempt + 1)
        _status(f"Audio-Sicherheitsprüfung verwirft Versuch {attempt + 1}; keine Geräusche abgespielt.")
    # Silence is safer than playing noises or silently switching voice.
    LOGGER.error("Eve synthesis failed safety checks; no audio played")
    _status("Alle drei Versuche fehlgeschlagen. Antworttext vorhanden, aber keine sichere Sprachausgabe.")


def install_tts_safety():
    from speech_to_speech.TTS.qwen3_tts_handler import Qwen3TTSHandler

    if getattr(Qwen3TTSHandler, "_trinity_safe_clone", False):
        return
    original = Qwen3TTSHandler._process_voice_clone

    def guarded(self, text):
        if self.backend != "mlx" and self.faster_backend == "ggml":
            yield from checked_clone_chunks(self, text)
        else:
            yield from original(self, text)

    Qwen3TTSHandler._process_voice_clone = guarded
    Qwen3TTSHandler._trinity_safe_clone = True
