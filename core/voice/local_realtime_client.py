"""Local full-duplex client for Trinity's OpenAI-compatible realtime voice server."""

from __future__ import annotations

import base64
import json
import logging
import math
import os
import threading
import time
from collections import deque
from queue import Empty, Full, Queue
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import numpy as np

from .config import VoiceConfig


LOGGER = logging.getLogger(__name__)
SAMPLE_RATE = 16_000
BLOCK_SAMPLES = 512
SAMPLE_BYTES = 2
BARGE_IN_CONFIRM_BLOCKS = 4


class LocalRealtimeAudioClient:
    """Stream the desktop microphone and Eve audio with voice interruption.

    The upstream local streamer is half duplex. This client uses the upstream
    realtime protocol instead, so server VAD can cancel LLM and TTS output as
    soon as the user speaks. A lightweight correlation gate suppresses obvious
    loudspeaker echo; headphones remain the recommended route for barge-in.
    """

    def __init__(
        self,
        config: VoiceConfig,
        host: str = "127.0.0.1",
        endpoint: str = "",
        access_token: str = "",
    ):
        self.config = config
        self.host = host
        self.port = config.profile.internal_port
        self.endpoint = endpoint.strip()
        self.access_token = access_token.strip()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._connection = None
        self._error: BaseException | None = None
        self._send_queue: Queue[dict[str, Any]] = Queue(maxsize=96)
        self._output = bytearray()
        self._output_lock = threading.Lock()
        self._played_output: deque[np.ndarray] = deque(maxlen=20)
        self._barge_in_candidate: deque[bytes] = deque(maxlen=BARGE_IN_CONFIRM_BLOCKS)
        self._last_output_at = 0.0
        self._last_cancel_at = 0.0
        self._speech_queue_path = config.home / "TrinityRuntime" / "voice" / "desktop_speech_queue.jsonl"
        self._ready_path = config.home / "TrinityRuntime" / "voice" / "desktop_eve_audio.ready"
        self._trinity_config_path = config.home / "core" / "config.json"
        self._speaker_check_at = 0.0
        self._desktop_output_enabled = True
        self._speech_queue_offset = 0

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
        self._remove_ready_marker()
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

            uri = self._connection_uri()
            with connect(uri, open_timeout=12, max_size=None, proxy=None) as connection:
                self._connection = connection
                self._speech_queue_path.parent.mkdir(parents=True, exist_ok=True)
                self._speech_queue_path.touch(exist_ok=True)
                self._speech_queue_offset = self._speech_queue_path.stat().st_size
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
                    self._write_ready_marker()
                    print("Eve Desktop-Audio bereit: Unterbrechen durch Sprechen ist aktiv.")
                    while not self._stop.is_set():
                        self._consume_speech_queue()
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
            self._remove_ready_marker()
            if sender:
                sender.join(timeout=2)

    def _connection_uri(self) -> str:
        raw = self.endpoint or f"ws://{self.host}:{self.port}/v1/realtime"
        parts = urlsplit(raw)
        path = parts.path or "/v1/realtime"
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        if self.access_token:
            query["access_token"] = self.access_token
        return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query), parts.fragment))

    def _write_ready_marker(self) -> None:
        try:
            self._ready_path.parent.mkdir(parents=True, exist_ok=True)
            self._ready_path.write_text(str(os.getpid()), encoding="utf-8")
        except OSError:
            LOGGER.debug("Eve-Bereitschaftsmarker konnte nicht geschrieben werden", exc_info=True)

    def _remove_ready_marker(self) -> None:
        try:
            self._ready_path.unlink(missing_ok=True)
        except OSError:
            LOGGER.debug("Eve-Bereitschaftsmarker konnte nicht entfernt werden", exc_info=True)

    def _consume_speech_queue(self) -> None:
        try:
            with self._speech_queue_path.open("r", encoding="utf-8") as handle:
                handle.seek(self._speech_queue_offset)
                lines = handle.readlines()
                self._speech_queue_offset = handle.tell()
        except OSError:
            return
        for line in lines:
            try:
                payload = json.loads(line)
            except (TypeError, ValueError):
                continue
            text = str(payload.get("text") or "").strip()
            if not text:
                continue
            self._queue_event({
                "type": "response.create",
                "response": {
                    "conversation": "none",
                    "input": [{
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": text}],
                    }],
                    "instructions": (
                        "Lies den bereitgestellten deutschen Text wortgetreu vor. "
                        "Gib ausschliesslich diesen Text aus."
                    ),
                    "output_modalities": ["audio"],
                    "max_output_tokens": 4096,
                    "metadata": {"trinity_action": "desktop_read_aloud"},
                },
            })

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
        if not self._desktop_speaker_selected():
            self._clear_output()
            outdata[:] = b"\x00" * wanted
            return
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

    def _desktop_speaker_selected(self) -> bool:
        now = time.monotonic()
        if now < self._speaker_check_at:
            return self._desktop_output_enabled
        self._speaker_check_at = now + 0.35
        try:
            config = json.loads(self._trinity_config_path.read_text(encoding="utf-8"))
            speaker = config.get("system", {}).get("speech_output", {})
            self._desktop_output_enabled = not speaker or str(
                speaker.get("kind") or "desktop"
            ).strip().lower() == "desktop"
        except (OSError, ValueError, TypeError):
            # A transient write/read race must not unexpectedly mute the active desktop.
            pass
        return self._desktop_output_enabled

    def _input_callback(self, indata, _frames, _time_info, status) -> None:
        if status:
            LOGGER.debug("Desktop-Audioeingabe: %s", status)
        microphone = bytes(indata)
        output_active = (time.monotonic() - self._last_output_at) < 0.18
        if not output_active:
            self._barge_in_candidate.clear()
            self._append_microphone(microphone)
            return
        if not self._should_forward_microphone(microphone):
            self._barge_in_candidate.clear()
            return

        # Acoustic loudspeaker echo can differ from the exact output samples and
        # occasionally looks like one distinct microphone block. Confirm a very
        # short run of speech before cancelling, while retaining those blocks as
        # VAD prefix. Four 32-ms blocks keep barge-in responsive (~128 ms).
        self._barge_in_candidate.append(microphone)
        if len(self._barge_in_candidate) < BARGE_IN_CONFIRM_BLOCKS:
            return
        candidate = tuple(self._barge_in_candidate)
        self._barge_in_candidate.clear()
        self._interrupt_playback_if_needed()
        for block in candidate:
            self._append_microphone(block)

    def _append_microphone(self, microphone: bytes) -> None:
        if not microphone or self._stop.is_set():
            return
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
        strongest_waveform = 0.0
        strongest_spectrum = 0.0
        spectrum = np.abs(np.fft.rfft(samples))
        spectrum_norm = float(np.linalg.norm(spectrum))
        for played in self._played_output:
            if played.size != samples.size:
                continue
            candidate = played.astype(np.float32)
            denominator = norm * float(np.linalg.norm(candidate))
            if denominator > 1.0:
                strongest_waveform = max(
                    strongest_waveform,
                    abs(float(np.dot(samples, candidate) / denominator)),
                )
            # Magnitude spectra remain comparable despite the acoustic delay and
            # phase shift introduced by loudspeakers, the room and the mic.
            candidate_spectrum = np.abs(np.fft.rfft(candidate))
            spectrum_denominator = spectrum_norm * float(np.linalg.norm(candidate_spectrum))
            if spectrum_denominator > 1.0:
                strongest_spectrum = max(
                    strongest_spectrum,
                    float(np.dot(spectrum, candidate_spectrum) / spectrum_denominator),
                )
        return strongest_waveform < 0.62 and strongest_spectrum < 0.90

    def _handle_event(self, raw: str | bytes) -> None:
        try:
            event = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        event_type = str(event.get("type") or "")
        if event_type == "input_audio_buffer.speech_started":
            self._clear_output()
        elif event_type == "response.output_audio.delta":
            if not self._desktop_speaker_selected():
                self._clear_output()
                return
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
        # Keep the recent playback fingerprint. The physical speaker tail still
        # reaches the microphone after the digital buffer has been cancelled;
        # clearing this history made every following response interrupt itself.
        self._last_output_at = 0.0
