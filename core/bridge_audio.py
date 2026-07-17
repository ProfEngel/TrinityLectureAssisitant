"""Local PCM transcription for trusted Trinity companion clients."""

from __future__ import annotations

import base64
import binascii
import threading


G2_SAMPLE_RATE = 16_000
MAX_AUDIO_SECONDS = 20


class BridgeAudioTranscriber:
    """Lazily load faster-whisper and transcribe signed 16-bit mono PCM."""

    def __init__(self, model_name="small"):
        self.model_name = str(model_name or "small")
        self._model = None
        self._lock = threading.Lock()

    @staticmethod
    def decode_pcm(audio_base64, sample_rate=G2_SAMPLE_RATE):
        if int(sample_rate) != G2_SAMPLE_RATE:
            raise ValueError("Audio muss als 16-kHz-PCM gesendet werden.")
        try:
            raw = base64.b64decode(str(audio_base64 or ""), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Audio-Payload ist kein gueltiges Base64.") from exc
        if not raw or len(raw) % 2:
            raise ValueError("Audio-Payload muss signiertes 16-Bit-Mono-PCM enthalten.")
        if len(raw) > G2_SAMPLE_RATE * 2 * MAX_AUDIO_SECONDS:
            raise ValueError(f"Audio-Payload darf hoechstens {MAX_AUDIO_SECONDS} Sekunden lang sein.")

        import numpy as np

        return np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0

    def _ensure_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_name,
                device="cpu",
                compute_type="int8",
                cpu_threads=8,
            )
        return self._model

    def transcribe(self, audio_base64, *, sample_rate=G2_SAMPLE_RATE, language="de"):
        audio = self.decode_pcm(audio_base64, sample_rate=sample_rate)
        selected_language = str(language or "de").strip().lower()
        if selected_language in {"", "auto"}:
            selected_language = None
        elif selected_language not in {"de", "en"}:
            raise ValueError("Unterstuetzte Sprachen sind de, en oder auto.")

        with self._lock:
            segments, info = self._ensure_model().transcribe(
                audio,
                language=selected_language,
                initial_prompt="Trinity. Deutsche Vorlesung und natuerliche Konversation.",
                condition_on_previous_text=False,
                vad_filter=True,
                beam_size=1,
                best_of=1,
            )
            text = " ".join(str(segment.text or "").strip() for segment in segments).strip()
        return {
            "text": text,
            "language": str(getattr(info, "language", selected_language or "") or ""),
            "language_probability": float(getattr(info, "language_probability", 0.0) or 0.0),
        }
