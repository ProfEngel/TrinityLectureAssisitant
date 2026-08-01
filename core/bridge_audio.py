"""Local PCM transcription for trusted Trinity companion clients."""

from __future__ import annotations

import base64
import binascii
import re
import threading


G2_SAMPLE_RATE = 16_000
MAX_AUDIO_SECONDS = 20
TRINITY_VOCABULARY = (
    "Natuerliche deutsche Sprache. Trinity ist der Name der Assistentin."
)
TRINITY_HOTWORDS = "Trinity"

_KNOWN_SUBTITLE_HALLUCINATIONS = (
    re.compile(r"\bcopyright\b.*\b(?:ard|zdf|wdr|ndr|swr|br|mdr|rbb)\b", re.IGNORECASE),
    re.compile(r"\buntertitel\b.*\b(?:auftrag|community|amara)\b", re.IGNORECASE),
    re.compile(r"\bamara\s*\.\s*org\b", re.IGNORECASE),
    re.compile(r"\b(?:www\s*\.\s*)?schnellsessions?\s*\.\s*com\b", re.IGNORECASE),
)


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

    def transcribe(self, audio_base64, *, sample_rate=G2_SAMPLE_RATE, language="de", quality="balanced"):
        audio = self.decode_pcm(audio_base64, sample_rate=sample_rate)
        import numpy as np

        if float(np.sqrt(np.mean(np.square(audio), dtype=np.float64))) < 0.0015:
            return {"text": "", "language": str(language or ""), "language_probability": 0.0}
        selected_language = str(language or "de").strip().lower()
        if selected_language in {"", "auto"}:
            selected_language = None
        elif selected_language not in {"de", "en"}:
            raise ValueError("Unterstuetzte Sprachen sind de, en oder auto.")

        quality = str(quality or "balanced").strip().lower()
        if quality not in {"fast", "balanced", "precise"}:
            raise ValueError("Erkennungsqualitaet muss fast, balanced oder precise sein.")
        beam_size = {"fast": 1, "balanced": 2, "precise": 4}[quality]

        with self._lock:
            segments, info = self._ensure_model().transcribe(
                audio,
                language=selected_language,
                initial_prompt=TRINITY_VOCABULARY,
                hotwords=TRINITY_HOTWORDS,
                condition_on_previous_text=False,
                vad_filter=True,
                vad_parameters={
                    "threshold": 0.5,
                    "min_speech_duration_ms": 180,
                    "min_silence_duration_ms": 250,
                    "speech_pad_ms": 120,
                },
                beam_size=beam_size,
                best_of=1,
                temperature=0.0,
                no_speech_threshold=0.55,
                log_prob_threshold=-0.9,
            )
            accepted = []
            for segment in segments:
                text = str(segment.text or "").strip()
                no_speech = float(getattr(segment, "no_speech_prob", 0.0) or 0.0)
                average_log_probability = float(getattr(segment, "avg_logprob", 0.0) or 0.0)
                if no_speech > 0.65 and average_log_probability < -0.7:
                    continue
                if text and not self.is_known_hallucination(text):
                    accepted.append(text)
            text = " ".join(accepted).strip()
            if self.is_known_hallucination(text):
                text = ""
        return {
            "text": text,
            "language": str(getattr(info, "language", selected_language or "") or ""),
            "language_probability": float(getattr(info, "language_probability", 0.0) or 0.0),
        }

    @staticmethod
    def is_known_hallucination(text):
        normalized = " ".join(str(text or "").split())
        return bool(normalized) and any(pattern.search(normalized) for pattern in _KNOWN_SUBTITLE_HALLUCINATIONS)
