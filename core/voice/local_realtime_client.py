"""Local full-duplex client for Trinity's OpenAI-compatible realtime voice server."""

from __future__ import annotations

import base64
import json
import logging
import math
import threading
import time
from collections import deque
from queue import Empty, Full, Queue
from typing import Any

import numpy as np

from .config import VoiceConfig


LOGGER = logging.getLogger(__name__)
SAMPLE_RATE = 16_000
BLOCK_SAMPLES = 512
SAMPLE_BYTES = 2


class LocalRealtimeAudioClient:
    """Stream the desktop microphone and Eve audio with voice interruption.

    The upstream local streamer is half duplex. This client uses the upstream
    realtime protocol instead, so server VAD can cancel LLM and TTS output as
    soon as the user speaks. A lightweight correlation gate suppresses obvious
    loudspeaker echo; headphones remain the recommended route for barge-in.
    """

    def __init__(self, config: VoiceConfig, host: str = "127.0.0.1"):
        self.config = config
        self.host = host
        self.port = config.profile.internal_port
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._connection = None
        self._error: BaseException | None = None
        self._send_queue: Queue[dict[str, Any]] = Queue(maxsize=96)
        self._output = bytearray()
        self._output_lock = threading.Lock()
        self._played_output: deque[np.ndarray] = deque(maxlen=20)
        self._last_output_at = 0.0
        self._last_cancel_at = 0.0

    def start(self, timeout: float = 20.0) -> None:
        self._thread = threading.Thread(
            target=self._run,
            name="trinity-local-eve-client",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout):
            raise TimeoutError("Lokaler Eve-Audioclient wurde nicht rechtzeitig bereit.")
        if self._error:
            raise RuntimeError(f"Lokaler Eve-Audioclient konnte nicht starten: {self._error}")

    def stop(self) -> None:
        self._stop.set()
        connection = self._connection
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None
        self._connection = None

    @property
    def failure(self) -> BaseException | None:
        return self._error

    @property
    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _queue_event(self, event: dict[str, Any]) -> None:
        try:
            self._send_queue.put_nowait(event)
        except Full:
            try:
                self._send_queue.get_nowait()
            except Empty:
                pass
            try:
                self._send_queue.put_nowait(event)
            except Full:
                pass

    def _session_update(self) -> dict[str, Any]:
        return {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "instructions": (
                    "Du bist die Sprachoberfläche von Trinity. Verstehe und sprich "
                    "ausschließlich Deutsch. Antworte natürlich, klar und kurz."
                ),
                "output_modalities": ["text", "audio"],
                "audio": {
                    "input": {
                        "transcription": {"language": "de", "model": "parakeet-tdt"},
                        "turn_detection": {
                            "type": "server_vad",
                            "create_response": True,
                            "interrupt_response": self.config.barge_in_enabled,
                            "prefix_padding_ms": 320,
                            "silence_duration_ms": 420,
                        },
                    }
                },
            },
        }

    def _run(self) -> None:
        sender: threading.Thread | None = None
        try:
            import sounddevice as sd
            from websockets.sync.client import connect

            uri = f"ws://{self.host}:{self.port}/v1/realtime"
            with connect(uri, open_timeout=12, max_size=None, proxy=None) as connection:
                self._connection = connection
                connection.send(json.dumps(self._session_update(), ensure_ascii=False))
                sender = threading.Thread(
                    target=self._send_loop,
                    args=(connection,),
                    name="trinity-local-eve-sender",
                    daemon=True,
                )
                sender.start()
                # Input and output devices commonly use different native sample
                # rates on macOS (for example 44.1 kHz and 48 kHz). Separate
                # PortAudio streams avoid the CoreAudio deadlock caused by a
                # combined duplex stream while retaining full-duplex barge-in.
                with sd.RawOutputStream(
                    samplerate=SAMPLE_RATE,
                    dtype="int16",
                    channels=1,
                    blocksize=BLOCK_SAMPLES,
                    callback=self._output_callback,
                ), sd.RawInputStream(
                    samplerate=SAMPLE_RATE,
                    dtype="int16",
                    channels=1,
                    blocksize=BLOCK_SAMPLES,
                    callback=self._input_callback,
                ):
                    self._ready.set()
                    print("Eve Desktop-Audio bereit: Unterbrechen durch Sprechen ist aktiv.")
                    while not self._stop.is_set():
                        try:
                            raw = connection.recv(timeout=0.1)
                        except TimeoutError:
                            continue
                        if raw is None:
                            break
                        self._handle_event(raw)
                    if not self._stop.is_set():
                        raise RuntimeError("Realtime-Verbindung wurde unerwartet geschlossen.")
        except BaseException as exc:
            self._error = exc
            self._ready.set()
            if not self._stop.is_set():
                LOGGER.exception("Lokaler Eve-Audioclient beendet")
        finally:
            self._stop.set()
            if sender:
                sender.join(timeout=2)

    def _send_loop(self, connection) -> None:
        while not self._stop.is_set():
            try:
                event = self._send_queue.get(timeout=0.1)
            except Empty:
                continue
            try:
                connection.send(json.dumps(event, ensure_ascii=False))
            except Exception:
                self._stop.set()
                return

    def _output_callback(self, outdata, frames, _time_info, status) -> None:
        if status:
            LOGGER.debug("Desktop-Audioausgabe: %s", status)
        wanted = frames * SAMPLE_BYTES
        with self._output_lock:
            take = min(wanted, len(self._output))
            outgoing = bytes(self._output[:take])
            del self._output[:take]
        if take < wanted:
            outgoing += b"\x00" * (wanted - take)
        outdata[:] = outgoing

        output_samples = np.frombuffer(outgoing, dtype=np.int16).copy()
        if np.any(output_samples):
            self._played_output.append(output_samples)
            self._last_output_at = time.monotonic()

    def _input_callback(self, indata, _frames, _time_info, status) -> None:
        if status:
            LOGGER.debug("Desktop-Audioeingabe: %s", status)
        microphone = bytes(indata)
        if self._should_forward_microphone(microphone):
            self._interrupt_playback_if_needed()
            self._queue_event({
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(microphone).decode("ascii"),
            })

    def _audio_callback(self, indata, outdata, frames, time_info, status) -> None:
        """Compatibility wrapper used by existing integrations and tests."""

        self._output_callback(outdata, frames, time_info, status)
        self._input_callback(indata, frames, time_info, status)

    def _interrupt_playback_if_needed(self) -> None:
        if not self.config.barge_in_enabled:
            return
        now = time.monotonic()
        if now - self._last_output_at >= 0.18 or now - self._last_cancel_at < 0.45:
            return
        self._last_cancel_at = now
        self._clear_output()
        self._queue_event({"type": "response.cancel"})

    def _should_forward_microphone(self, pcm: bytes) -> bool:
        if not pcm or self._stop.is_set():
            return False
        output_active = (time.monotonic() - self._last_output_at) < 0.18
        if not output_active:
            return True
        if not self.config.barge_in_enabled:
            return False

        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        level = math.sqrt(float(np.mean(samples * samples))) if samples.size else 0.0
        if level < self.config.barge_in_min_level:
            return False
        if not self.config.echo_suppression_enabled:
            return True

        norm = float(np.linalg.norm(samples))
        if norm <= 1.0:
            return False
        strongest = 0.0
        for played in self._played_output:
            if played.size != samples.size:
                continue
            candidate = played.astype(np.float32)
            denominator = norm * float(np.linalg.norm(candidate))
            if denominator > 1.0:
                strongest = max(strongest, abs(float(np.dot(samples, candidate) / denominator)))
        return strongest < 0.62

    def _handle_event(self, raw: str | bytes) -> None:
        try:
            event = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        event_type = str(event.get("type") or "")
        if event_type == "input_audio_buffer.speech_started":
            self._clear_output()
        elif event_type == "response.output_audio.delta":
            encoded = str(event.get("delta") or "")
            try:
                audio = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError):
                return
            with self._output_lock:
                self._output.extend(audio)
            self._last_output_at = time.monotonic()
        elif event_type == "error":
            error = event.get("error") if isinstance(event.get("error"), dict) else {}
            LOGGER.warning("Eve-Realtime-Fehler: %s", error.get("message") or "unbekannt")

    def _clear_output(self) -> None:
        with self._output_lock:
            self._output.clear()
        self._played_output.clear()
        self._last_output_at = 0.0
