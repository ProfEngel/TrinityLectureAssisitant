"""Local PCM transcription for trusted Trinity companion clients."""

from __future__ import annotations

import base64
import binascii
import importlib.util
import json
import platform
import re
import threading
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


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
    """Transcribe companion PCM without consuming an Eve conversation slot."""

    def __init__(
        self,
        model_name="small",
        *,
        backend="whisper",
        parakeet_model_name="mlx-community/parakeet-tdt-0.6b-v3",
        remote_voice_url="",
        remote_stt_url="",
        remote_voice_token="",
        remote_timeout_seconds=12,
        remote_requester=None,
    ):
        self.model_name = str(model_name or "small")
        self.backend = self.resolve_backend(backend)
        self.parakeet_model_name = str(
            parakeet_model_name or "mlx-community/parakeet-tdt-0.6b-v3"
        )
        self.remote_voice_url = str(remote_voice_url or "").strip()
        self.remote_stt_url = str(remote_stt_url or "").strip()
        self.remote_voice_token = str(remote_voice_token or "").strip()
        self.remote_timeout_seconds = max(2.0, float(remote_timeout_seconds or 12))
        self._remote_requester = remote_requester
        self._model = None
        self._fallback_model = None
        self._lock = threading.Lock()

    @staticmethod
    def resolve_backend(value):
        backend = str(value or "auto").strip().lower()
        if backend == "remote":
            backend = "eve-remote"
        if backend not in {"auto", "parakeet", "whisper", "eve-remote"}:
            raise ValueError(
                "STT-Backend muss auto, parakeet, whisper oder eve-remote sein."
            )
        if backend == "auto":
            if platform.system() == "Darwin" and importlib.util.find_spec("mlx_audio"):
                return "parakeet"
            return "whisper"
        return backend

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
            if self.backend == "parakeet":
                from mlx_audio.stt.generate import load_model

                self._model = load_model(self.parakeet_model_name)
            else:
                from faster_whisper import WhisperModel

                self._model = WhisperModel(
                    self.model_name,
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=8,
                )
        return self._model

    def _ensure_fallback_model(self):
        if self._fallback_model is None:
            from faster_whisper import WhisperModel

            self._fallback_model = WhisperModel(
                self.model_name,
                device="cpu",
                compute_type="int8",
                cpu_threads=8,
            )
        return self._fallback_model

    def warm_up(self):
        """Load the fast model before the first glasses utterance arrives."""
        if self.backend == "parakeet":
            with self._lock:
                self._ensure_model()

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
            if self.backend == "eve-remote":
                try:
                    remote = self._transcribe_eve_remote(
                        audio_base64,
                        language=selected_language or "de",
                    )
                    text = str(remote.get("text") or "").strip()
                    if self.is_known_hallucination(text):
                        text = ""
                    return {
                        "text": text,
                        "language": str(remote.get("language") or selected_language or "de"),
                        "language_probability": float(
                            remote.get("language_probability", 1.0 if text else 0.0)
                        ),
                        "engine": "eve-remote",
                    }
                except Exception as exc:  # pylint: disable=broad-except
                    # Keep the Windows control plane usable while the GPU host
                    # is rebooting or Tailscale briefly reconnects.
                    fallback = self._transcribe_whisper(
                        audio,
                        selected_language=selected_language,
                        beam_size=beam_size,
                        model=self._ensure_fallback_model(),
                    )
                    fallback["engine"] = "whisper-fallback"
                    fallback["remote_error"] = self._short_error(exc)
                    return fallback
            if self.backend == "parakeet":
                result = self._transcribe_parakeet(audio)
                text = str(getattr(result, "text", result) or "").strip()
                if self.is_known_hallucination(text):
                    text = ""
                detected_language = selected_language or "de"
                language_probability = 1.0 if text else 0.0
            else:
                local = self._transcribe_whisper(
                    audio,
                    selected_language=selected_language,
                    beam_size=beam_size,
                    model=self._ensure_model(),
                )
                text = local["text"]
                detected_language = local["language"]
                language_probability = local["language_probability"]
        return {
            "text": text,
            "language": detected_language,
            "language_probability": language_probability,
            "engine": self.backend,
        }

    def _transcribe_parakeet(self, audio):
        import mlx.core as mx

        return self._ensure_model().generate(mx.array(audio))

    def _transcribe_whisper(self, audio, *, selected_language, beam_size, model):
        segments, info = model.transcribe(
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
            "language_probability": float(
                getattr(info, "language_probability", 0.0) or 0.0
            ),
        }

    def _transcribe_eve_remote(self, audio_base64, *, language):
        endpoint = self.remote_stt_url or self.derive_remote_stt_url(
            self.remote_voice_url
        )
        if not endpoint:
            raise RuntimeError("Keine Ubuntu-STT-URL konfiguriert.")
        payload = json.dumps({
            "audio_base64": str(audio_base64 or ""),
            "sample_rate": G2_SAMPLE_RATE,
            "language": str(language or "de"),
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.remote_voice_token:
            headers["Authorization"] = f"Bearer {self.remote_voice_token}"
        request = Request(endpoint, data=payload, headers=headers, method="POST")
        requester = self._remote_requester or urlopen
        with requester(request, timeout=self.remote_timeout_seconds) as response:
            result = json.load(response)
        if not result.get("ok", True):
            raise RuntimeError(str(result.get("error") or "Ubuntu-STT-Fehler"))
        return result

    @staticmethod
    def derive_remote_stt_url(remote_voice_url):
        parts = urlsplit(str(remote_voice_url or "").strip())
        if parts.scheme not in {"ws", "wss", "http", "https"} or not parts.hostname:
            return ""
        scheme = "https" if parts.scheme in {"wss", "https"} else "http"
        port = (parts.port + 1) if parts.port else 8767
        host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
        return urlunsplit((
            scheme,
            f"{host}:{port}",
            "/v1/audio/transcriptions",
            "",
            "",
        ))

    @staticmethod
    def _short_error(exc):
        return " ".join(str(exc or exc.__class__.__name__).split())[:240]

    @staticmethod
    def is_known_hallucination(text):
        normalized = " ".join(str(text or "").split())
        return bool(normalized) and any(pattern.search(normalized) for pattern in _KNOWN_SUBTITLE_HALLUCINATIONS)
