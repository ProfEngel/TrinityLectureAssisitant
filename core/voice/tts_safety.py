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


def trim_clone_silence(chunks):
    """Trim only the outer silent ramp, never sentence-internal pauses."""
    import numpy as np

    if not chunks:
        return []
    rate = chunks[0][1]
    if rate <= 0 or any(item[1] != rate for item in chunks):
        return []
    audio = np.concatenate([np.asarray(item[0]).reshape(-1) for item in chunks])
    audible = np.flatnonzero(np.abs(audio) > 0.002)
    if not audible.size:
        return []
    begin = max(0, int(audible[0]) - int(rate * 0.05))
    end = min(audio.size, int(audible[-1]) + 1 + int(rate * 0.10))
    return [(audio[begin:end], rate, *chunks[0][2:])]


def checked_clone_chunks(handler, text):
    import numpy as np

    words = len(re.findall(r"\w+", text))
    # Normal Eve speaks ~2.6 words/s. Bound runaway generation before it can
    # consume multiple 29-second retries for a short reply.
    duration_limit = max(6.0, 2.5 + words / 1.5)
    cap = min(handler._estimate_max_new_tokens(text), math.ceil(duration_limit * 12.5))
    generation = handler.cancel_scope.generation if handler.cancel_scope else None
    for attempt in range(3):
        started = time.monotonic()
        chunks = []
        duration = 0.0
        valid = True
        generator = handler.model.generate_voice_clone_streaming(
            text=text, language=handler.language, ref_audio=handler.ref_audio,
            # After one failed in-context synthesis, retain the same Eve speaker
            # embedding without replaying the fragile reference-text context.
            ref_text=handler.ref_text, xvec_only=handler.xvec_only or attempt >= 1,
            chunk_size=handler.streaming_chunk_size, max_new_tokens=cap,
            parity_mode=handler.parity_mode, non_streaming_mode=handler.non_streaming_mode,
            do_sample=attempt != 1, temperature=0.9 if attempt == 2 else 0.65,
            repetition_penalty=1.05 if attempt == 2 else 1.1,
        )
        found_voice = False
        try:
            for item in generator:
                if generation is not None and handler.cancel_scope.is_stale(generation):
                    return
                audio, rate = item[:2]
                audio = np.asarray(audio)
                if rate <= 0 or not np.isfinite(audio).all():
                    valid = False
                    break
                duration += audio.size / rate
                chunks.append(item)
                found_voice = found_voice or bool(np.any(np.abs(audio) > 0.002))
                if not found_voice and duration > 1.5:
                    valid = False
                    break
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
        chunks = trim_clone_silence(chunks) if valid else []
        if valid and chunks and duration < cap / 12.5 - 0.08:
            duration = sum(np.asarray(item[0]).size / item[1] for item in chunks)
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
