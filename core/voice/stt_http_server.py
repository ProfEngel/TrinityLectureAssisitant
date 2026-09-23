"""Authenticated, transcription-only Parakeet endpoint for remote companions."""

from __future__ import annotations

import base64
import binascii
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np


SAMPLE_RATE = 16_000
MAX_AUDIO_SECONDS = 20


class CudaParakeetTranscriber:
    """A small standalone STT worker that does not reserve an Eve TTS slot."""

    def __init__(self, model_name: str, device: str = "cuda"):
        self.model_name = str(model_name)
        self.device = str(device or "cuda")
        self._model = None
        self._lock = threading.Lock()

    def _ensure_model(self):
        if self._model is None:
            from nano_parakeet import from_pretrained

            self._model = from_pretrained(
                model_name=self.model_name,
                device=self.device,
            )
            self._model.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32))
        return self._model

    def warm_up(self) -> None:
        with self._lock:
            self._ensure_model()

    def transcribe(self, audio_base64: str, *, sample_rate: int = SAMPLE_RATE, **_kwargs):
        audio = self.decode_pcm(audio_base64, sample_rate=sample_rate)
        rms = float(np.sqrt(np.mean(np.square(audio), dtype=np.float64)))
        if rms < 0.0015:
            return {"text": "", "language": "de", "language_probability": 0.0}
        with self._lock:
            text = str(self._ensure_model().transcribe(audio) or "").strip()
        return {
            "text": text,
            "language": "de",
            "language_probability": 1.0 if text else 0.0,
            "engine": "parakeet-cuda",
        }

    @staticmethod
    def decode_pcm(audio_base64: str, *, sample_rate: int = SAMPLE_RATE):
        if int(sample_rate) != SAMPLE_RATE:
            raise ValueError("Audio muss als 16-kHz-PCM gesendet werden.")
        try:
            raw = base64.b64decode(str(audio_base64 or ""), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Audio-Payload ist kein gueltiges Base64.") from exc
        if not raw or len(raw) % 2:
            raise ValueError("Audio-Payload muss signiertes 16-Bit-Mono-PCM enthalten.")
        if len(raw) > SAMPLE_RATE * 2 * MAX_AUDIO_SECONDS:
            raise ValueError(
                f"Audio-Payload darf hoechstens {MAX_AUDIO_SECONDS} Sekunden lang sein."
            )
        return np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0


class ParakeetSTTHTTPServer:
    """Lifecycle wrapper for the Ubuntu-only HTTP STT service."""

    def __init__(self, host: str, port: int, token: str, transcriber):
        self.host = str(host)
        self.port = int(port)
        self.token = str(token or "")
        self.transcriber = transcriber
        self._server = None
        self._thread = None
        self._warmup_thread = None
        self._warmup_error = ""

    def start(self) -> None:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "TrinityParakeetSTT/1.0"

            def log_message(self, _format, *_args):
                return

            def _authorized(self):
                supplied = self.headers.get("Authorization", "")
                expected = f"Bearer {owner.token}"
                return bool(owner.token) and hmac.compare_digest(supplied, expected)

            def _json(self, status, payload):
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):  # noqa: N802
                if self.path != "/health":
                    self._json(404, {"ok": False, "error": "not_found"})
                    return
                if not self._authorized():
                    self._json(401, {"ok": False, "error": "unauthorized"})
                    return
                self._json(
                    200 if not owner._warmup_error else 503,
                    {
                        "ok": not bool(owner._warmup_error),
                        "service": "trinity-parakeet-stt",
                        "ready": owner.transcriber._model is not None,
                        "error": owner._warmup_error,
                    },
                )

            def do_POST(self):  # noqa: N802
                if self.path != "/v1/audio/transcriptions":
                    self._json(404, {"ok": False, "error": "not_found"})
                    return
                if not self._authorized():
                    self._json(401, {"ok": False, "error": "unauthorized"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > 1_000_000:
                        raise ValueError("Ungueltige Audio-Anfragegroesse.")
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    result = owner.transcriber.transcribe(
                        payload.get("audio_base64", ""),
                        sample_rate=int(payload.get("sample_rate") or SAMPLE_RATE),
                        language=str(payload.get("language") or "de"),
                        quality=str(payload.get("quality") or "balanced"),
                    )
                    self._json(200, {"ok": True, **result})
                except ValueError as exc:
                    self._json(400, {"ok": False, "error": str(exc)})
                except Exception as exc:  # pylint: disable=broad-except
                    self._json(503, {"ok": False, "error": type(exc).__name__})

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="trinity-parakeet-stt-http",
            daemon=True,
        )
        self._thread.start()

        def warm_up():
            try:
                self.transcriber.warm_up()
            except Exception as exc:  # pylint: disable=broad-except
                self._warmup_error = f"{type(exc).__name__}: {exc}"

        self._warmup_thread = threading.Thread(
            target=warm_up,
            name="trinity-parakeet-stt-warmup",
            daemon=True,
        )
        self._warmup_thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=3)
        self._server = None
        self._thread = None
