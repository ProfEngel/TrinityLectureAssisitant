"""Local full-duplex client for Trinity's OpenAI-compatible realtime voice server."""

from __future__ import annotations

import base64
import json
import logging
import math
import os
import platform
import threading
import time
import uuid
from collections import deque
from queue import Empty, Full, Queue
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np

from .config import VoiceConfig
from .device_identity import desktop_device_id


LOGGER = logging.getLogger(__name__)
SAMPLE_RATE = 16_000
BLOCK_SAMPLES = 512
OUTPUT_SAMPLE_RATE = 24_000
OUTPUT_BLOCK_SAMPLES = 768  # 32 ms, matching the 16-kHz input callback duration
VIRTUAL_SAMPLE_RATE = 48_000
VIRTUAL_BLOCK_SAMPLES = 1_536
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
        self._echo_lock = threading.Lock()
        self._barge_in_candidate: deque[bytes] = deque(maxlen=BARGE_IN_CONFIRM_BLOCKS)
        self._last_output_at = 0.0
        self._last_cancel_at = 0.0
        self._last_partial_log_at = 0.0
        self._window_client_id = "mac-voice:" + uuid.uuid4().hex
        self._window_sequence = 0
        self._window_capture_lock = threading.Lock()
        self._speech_queue_path = config.home / "TrinityRuntime" / "voice" / "desktop_speech_queue.jsonl"
        self._textedit_command_path = config.home / "TrinityRuntime" / "voice" / "textedit_transcripts.jsonl"
        self._ready_path = config.home / "TrinityRuntime" / "voice" / "desktop_eve_audio.ready"
        self._trinity_config_path = config.home / "core" / "config.json"
        self._speaker_check_at = 0.0
        self._desktop_output_enabled = True
        self._desktop_input_enabled = True
        self._remote_speaker_url = ""
        self._remote_input_url = ""
        self._remote_speaker_token = ""
        self._remote_speaker_id = ""
        self._remote_speaker_thread: threading.Thread | None = None
        self._last_route_state = None
        self._system_stream = None
        self._virtual_stream = None
        self._system_audio_enabled = False
        self._broadcast_enabled = False
        self._system_blocks: deque[bytes] = deque(maxlen=4)
        self._system_lock = threading.Lock()
        self._virtual_mic = bytearray()
        self._virtual_eve = bytearray()
        self._virtual_lock = threading.Lock()
        self._routing_check_at = 0.0
        try:
            app_config = json.loads(self._trinity_config_path.read_text(encoding="utf-8"))
            client = app_config.get("client", {})
            if client.get("enabled") and client.get("server_url"):
                self._remote_speaker_url = str(client["server_url"]).rstrip("/") + "/speaker"
                self._remote_input_url = str(client["server_url"]).rstrip("/") + "/audio/input"
                self._remote_speaker_token = str(client.get("token") or "")
                profile = str(app_config.get("system", {}).get("profile") or "PRIVAT").lower()
                self._remote_speaker_id = desktop_device_id(config.home, profile)
                self._desktop_output_enabled = False
                self._desktop_input_enabled = False
        except (OSError, ValueError, TypeError):
            pass
        self._speech_queue_offset = 0

    def start(self, timeout: float = 20.0) -> None:
        if self._remote_speaker_url:
            self._remote_speaker_thread = threading.Thread(
                target=self._poll_remote_speaker,
                name="trinity-remote-speaker",
                daemon=True,
            )
            self._remote_speaker_thread.start()
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
        if self._remote_speaker_thread:
            self._remote_speaker_thread.join(timeout=3)
        self._remote_speaker_thread = None
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
                    },
                    "output": {"format": {"type": "audio/pcm", "rate": OUTPUT_SAMPLE_RATE}},
                },
            },
        }

    def _run(self) -> None:
        try:
            import sounddevice as sd
            from websockets.sync.client import connect
        except BaseException as exc:
            self._error = exc
            self._ready.set()
            LOGGER.exception("Lokaler Eve-Audioclient konnte nicht starten")
            return

        while not self._stop.is_set():
            if self._remote_speaker_url and not self._desktop_connection_selected():
                # Another device owns the single GPU voice slot. Stay alive so
                # the desktop can reclaim it without restarting Trinity.
                self._ready.set()
                self._stop.wait(0.25)
                continue
            sender: threading.Thread | None = None
            session_stop = threading.Event()
            try:
                with connect(self._connection_uri(), open_timeout=12, max_size=None, proxy=None) as connection:
                    self._connection = connection
                    self._speech_queue_path.parent.mkdir(parents=True, exist_ok=True)
                    self._speech_queue_path.touch(exist_ok=True)
                    self._speech_queue_offset = self._speech_queue_path.stat().st_size
                    connection.send(json.dumps(self._session_update(), ensure_ascii=False))
                    sender = threading.Thread(
                        target=self._send_loop,
                        args=(connection, session_stop),
                        name="trinity-local-eve-sender",
                        daemon=True,
                    )
                    sender.start()
                    # Separate streams avoid a CoreAudio deadlock when input
                    # and output devices have different native sample rates.
                    with sd.RawOutputStream(
                        samplerate=OUTPUT_SAMPLE_RATE,
                        dtype="int16",
                        channels=1,
                        blocksize=OUTPUT_BLOCK_SAMPLES,
                        callback=self._output_callback,
                    ) as output_stream, sd.RawInputStream(
                        samplerate=SAMPLE_RATE,
                        dtype="int16",
                        channels=1,
                        blocksize=BLOCK_SAMPLES,
                        callback=self._input_callback,
                    ) as input_stream:
                        self._ready.set()
                        self._write_ready_marker()
                        print("Eve Desktop-Audio bereit: Unterbrechen durch Sprechen ist aktiv.")
                        while not self._stop.is_set() and (
                            not self._remote_speaker_url or self._desktop_connection_selected()
                        ):
                            self._sync_optional_streams(sd)
                            if not input_stream.active or not output_stream.active:
                                raise RuntimeError("CoreAudio-Stream gestoppt; Mikrofon und Ausgabe werden neu verbunden.")
                            self._consume_speech_queue()
                            try:
                                raw = connection.recv(timeout=0.1)
                            except TimeoutError:
                                continue
                            if raw is None:
                                break
                            self._handle_event(raw)
                        if not self._stop.is_set() and (
                            not self._remote_speaker_url or self._desktop_connection_selected()
                        ):
                            raise RuntimeError("Realtime-Verbindung wurde unerwartet geschlossen.")
            except BaseException as exc:
                if not self._ready.is_set():
                    self._error = exc
                    self._ready.set()
                    LOGGER.exception("Lokaler Eve-Audioclient beendet")
                    return
                if not self._remote_speaker_url:
                    self._error = exc
                    LOGGER.exception("Lokaler Eve-Audioclient beendet")
                    return
                LOGGER.warning("Eve-Voice-Verbindung wird erneut versucht: %s", exc)
            finally:
                self._close_optional_streams()
                session_stop.set()
                self._connection = None
                self._remove_ready_marker()
                if sender:
                    sender.join(timeout=2)
            self._stop.wait(0.5)
            if sender:
                sender.join(timeout=2)

    def _connection_uri(self) -> str:
        raw = self.endpoint or f"ws://{self.host}:{self.port}/v1/realtime"
        parts = urlsplit(raw)
        path = parts.path or "/v1/realtime"
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        if self.access_token:
            query["access_token"] = self.access_token
        if self._remote_speaker_id:
            query["device_id"] = self._remote_speaker_id
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
                        "content": [{"type": "input_text", "text": "[[TRINITY_READ_ALOUD_V1]]\n" + text}],
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

    def _send_loop(self, connection, session_stop=None) -> None:
        while not self._stop.is_set() and not (session_stop and session_stop.is_set()):
            try:
                event = self._send_queue.get(timeout=0.1)
            except Empty:
                continue
            try:
                connection.send(json.dumps(event, ensure_ascii=False))
            except Exception:
                # A remote server restart invalidates this socket, not the
                # desktop client. Let _run reconnect instead of shutting down
                # the entire Mac app and leaving its menu controls stranded.
                if session_stop:
                    session_stop.set()
                try:
                    connection.close()
                except Exception:
                    pass
                return

    @staticmethod
    def _blackhole_device(sd, name: str, direction: str):
        channel_key = "max_input_channels" if direction == "input" else "max_output_channels"
        return next((index for index, device in enumerate(sd.query_devices())
                     if name.casefold() in str(device["name"]).casefold() and device[channel_key] >= 2), None)

    def _sync_optional_streams(self, sd) -> None:
        now = time.monotonic()
        if now < self._routing_check_at:
            return
        self._routing_check_at = now + 0.75
        try:
            from PySide6.QtCore import QSettings
            settings = QSettings("Trinity", "RemoteClientSurface")
            settings.sync()
            hear_mac = settings.value("hearMacAudio", False, type=bool)
            broadcast = settings.value("broadcastTrinity", False, type=bool)
        except Exception:
            hear_mac = broadcast = False

        if not hear_mac and self._system_stream:
            self._system_stream.close()
            self._system_stream = None
        if not broadcast and self._virtual_stream:
            self._virtual_stream.close()
            self._virtual_stream = None
        self._system_audio_enabled = bool(hear_mac and self._system_stream)
        self._broadcast_enabled = bool(broadcast and self._virtual_stream)

        if hear_mac and self._system_stream is None:
            device = self._blackhole_device(sd, "BlackHole 16ch", "input")
            if device is not None:
                try:
                    stream = sd.RawInputStream(
                        device=device, samplerate=VIRTUAL_SAMPLE_RATE, channels=2, dtype="int16",
                        blocksize=VIRTUAL_BLOCK_SAMPLES, callback=self._system_audio_callback,
                    )
                    stream.start()
                    self._system_stream = stream
                    self._system_audio_enabled = True
                    LOGGER.info("Mac-Systemton wird über BlackHole 16ch empfangen")
                except Exception as exc:
                    LOGGER.warning("BlackHole 16ch nicht startbereit: %s", exc)

        if broadcast and self._virtual_stream is None:
            device = self._blackhole_device(sd, "BlackHole 2ch", "output")
            if device is not None:
                try:
                    stream = sd.RawOutputStream(
                        device=device, samplerate=VIRTUAL_SAMPLE_RATE, channels=2, dtype="int16",
                        blocksize=VIRTUAL_BLOCK_SAMPLES, callback=self._virtual_output_callback,
                    )
                    stream.start()
                    self._virtual_stream = stream
                    self._broadcast_enabled = True
                    LOGGER.info("Trinity und Mac-Mikrofon werden an BlackHole 2ch gesendet")
                except Exception as exc:
                    LOGGER.warning("BlackHole 2ch nicht startbereit: %s", exc)

    def _close_optional_streams(self):
        self._system_audio_enabled = False
        self._broadcast_enabled = False
        for name in ("_system_stream", "_virtual_stream"):
            stream = getattr(self, name)
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
                setattr(self, name, None)
        with self._system_lock:
            self._system_blocks.clear()
        with self._virtual_lock:
            self._virtual_mic.clear()
            self._virtual_eve.clear()

    def _system_audio_callback(self, indata, frames, _time_info, status):
        if status:
            LOGGER.debug("Mac-Systemton: %s", status)
        samples = np.frombuffer(indata, dtype=np.int16)
        if samples.size != frames * 2 or frames % 3:
            return
        mono = samples.reshape(frames, 2).astype(np.int32).mean(axis=1)
        block = mono.reshape(-1, 3).mean(axis=1).astype(np.int16).tobytes()
        with self._system_lock:
            self._system_blocks.append(block)

    def _push_virtual_audio(self, pcm: bytes, target: bytearray, multiplier: int):
        samples = np.frombuffer(pcm, dtype=np.int16)
        expanded = np.repeat(samples, multiplier).tobytes()
        with self._virtual_lock:
            target.extend(expanded)
            maximum = VIRTUAL_SAMPLE_RATE * SAMPLE_BYTES * 2
            if len(target) > maximum:
                del target[:-maximum]

    def _virtual_output_callback(self, outdata, frames, _time_info, status):
        if status:
            LOGGER.debug("BlackHole-2ch-Ausgabe: %s", status)
        wanted = frames * SAMPLE_BYTES
        with self._virtual_lock:
            microphone = bytes(self._virtual_mic[:wanted])
            eve = bytes(self._virtual_eve[:wanted])
            del self._virtual_mic[:wanted]
            del self._virtual_eve[:wanted]
        microphone = microphone.ljust(wanted, b"\x00")
        eve = eve.ljust(wanted, b"\x00")
        mixed = np.clip(
            np.frombuffer(microphone, dtype=np.int16).astype(np.int32)
            + np.frombuffer(eve, dtype=np.int16).astype(np.int32),
            -32768, 32767,
        ).astype(np.int16)
        outdata[:] = np.repeat(mixed[:, None], 2, axis=1).tobytes()

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

        if self._broadcast_enabled:
            self._push_virtual_audio(outgoing, self._virtual_eve, 2)

        output_samples = np.frombuffer(outgoing, dtype=np.int16).copy()
        if np.any(output_samples):
            # Echo fingerprints must use the microphone's 16-kHz frame size.
            reference = np.interp(
                np.linspace(0, output_samples.size - 1, BLOCK_SAMPLES),
                np.arange(output_samples.size), output_samples,
            ).astype(np.float32)
            with self._echo_lock:
                self._played_output.append(reference)
            self._last_output_at = time.monotonic()

    def _desktop_speaker_selected(self) -> bool:
        if self._remote_speaker_url:
            return self._desktop_output_enabled
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

    def _desktop_connection_selected(self) -> bool:
        return self._desktop_output_enabled or self._desktop_input_enabled

    def _poll_remote_speaker(self) -> None:
        headers = {"Accept": "application/json"}
        if self._remote_speaker_token:
            headers["Authorization"] = f"Bearer {self._remote_speaker_token}"
        while not self._stop.is_set():
            try:
                request = Request(self._remote_speaker_url, headers=headers)
                with urlopen(request, timeout=2) as response:
                    speaker = json.load(response)
                self._desktop_output_enabled = (
                    bool(speaker.get("ok"))
                    and str(speaker.get("device_id") or "") == self._remote_speaker_id
                )
                selected_input = {}
                try:
                    with urlopen(Request(self._remote_input_url, headers=headers), timeout=2) as response:
                        selected_input = json.load(response)
                    self._desktop_input_enabled = (
                        bool(selected_input.get("ok"))
                        and str(selected_input.get("device_id") or "") == self._remote_speaker_id
                    )
                except HTTPError as exc:
                    # Older servers couple the microphone to the speaker.
                    self._desktop_input_enabled = self._desktop_output_enabled if exc.code == 404 else False
                except Exception:
                    self._desktop_input_enabled = False
                route_state = (self._desktop_input_enabled, self._desktop_output_enabled)
                if route_state != self._last_route_state:
                    self._last_route_state = route_state
                    input_label = "Mac" if route_state[0] else str(selected_input.get("label") or "anderes Gerät")
                    output_label = "Mac" if route_state[1] else str(speaker.get("label") or "anderes Gerät")
                    print(f"Trinity Audio: Mikrofon {input_label} · Ausgabe {output_label}", flush=True)
            except Exception:
                self._desktop_output_enabled = False
                self._desktop_input_enabled = False
            self._stop.wait(1.5)

    def _input_callback(self, indata, _frames, _time_info, status) -> None:
        microphone = bytes(indata)
        if self._broadcast_enabled:
            self._push_virtual_audio(microphone, self._virtual_mic, 3)
        if not self._desktop_input_enabled:
            return
        if status:
            LOGGER.debug("Desktop-Audioeingabe: %s", status)
        if self._system_audio_enabled and time.monotonic() - self._last_output_at > 0.7:
            with self._system_lock:
                system = self._system_blocks.pop() if self._system_blocks else b""
                self._system_blocks.clear()
            if len(system) == len(microphone):
                mixed = (np.frombuffer(microphone, dtype=np.int16).astype(np.int32)
                         + np.frombuffer(system, dtype=np.int16).astype(np.int32))
                microphone = np.clip(mixed, -32768, 32767).astype(np.int16).tobytes()
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
        # CoreAudio input and output callbacks run on separate threads. Take
        # an immutable snapshot before FFT work; iterating the live deque can
        # raise and permanently abort the microphone callback.
        with self._echo_lock:
            played_snapshot = tuple(self._played_output)
        for played in played_snapshot:
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

    def _capture_requested_window(self, transcript):
        from .window_request import wants_window, fingerprint
        if (platform.system() != "Darwin" or not self._remote_speaker_url
                or not self._desktop_output_enabled or not wants_window(transcript)):
            return
        if not self._window_capture_lock.acquire(blocking=False):
            print("Fenster: Aufnahme läuft bereits; keine parallele Aufnahme.", flush=True)
            return
        def capture():
            try:
                from PySide6.QtCore import QSettings
                from mac_window_vision import foreground_pid, capture_window_jpeg
                self._window_sequence += 1
                payload = {"client_id": self._window_client_id,
                           "device_id": self._remote_speaker_id,
                           "sequence": self._window_sequence, "active": False,
                           "request_fingerprint": fingerprint(transcript)}
                if QSettings("Trinity", "RemoteClientSurface").value("windowOnDemand", True, type=bool):
                    try:
                        print("Fenster: gezielte Aufnahme für diese Bildschirmfrage.", flush=True)
                        image, title = capture_window_jpeg(foreground_pid())
                        payload.update(active=True, image_base64=base64.b64encode(image).decode(), title=title)
                    except Exception as exc:
                        print(f"Fensteraufnahme fehlgeschlagen: {exc}", flush=True)
                else:
                    print("Fensteraufnahme ist unter Datenschutz ausgeschaltet.", flush=True)
                endpoint = self._remote_speaker_url.rsplit("/", 1)[0] + "/desktop/context"
                if not self._desktop_output_enabled:
                    return
                headers = {"Content-Type": "application/json",
                           "Authorization": "Bearer " + self._remote_speaker_token,
                           "X-Trinity-Profile": self._remote_speaker_id.split(":")[1].upper()}
                request = Request(endpoint, data=json.dumps(payload).encode(), headers=headers, method="POST")
                with urlopen(request, timeout=3) as response:
                    result = json.load(response)
                print(f"Fenster: Server bestätigt Aufnahme={bool(result.get('has_image'))}.", flush=True)
            except Exception as exc:
                print(f"Fensterübertragung fehlgeschlagen: {type(exc).__name__}", flush=True)
            finally:
                self._window_capture_lock.release()
        threading.Thread(target=capture, name="trinity-window-on-demand", daemon=True).start()

    def _handle_event(self, raw: str | bytes) -> None:
        try:
            event = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        event_type = str(event.get("type") or "")
        if event_type == "trinity.debug":
            print(f"Server · {event.get('stage', '')}: {event.get('message', '')}", flush=True)
        elif event_type == "input_audio_buffer.speech_started":
            self._clear_output()
            print("Trinity hört Sprache vom ausgewählten Mikrofon.", flush=True)
        elif event_type == "conversation.item.input_audio_transcription.delta":
            now = time.monotonic()
            if now - self._last_partial_log_at >= 0.5:
                self._last_partial_log_at = now
                print(f"Du (live): {str(event.get('delta') or '')[:300]}", flush=True)
        elif event_type == "conversation.item.input_audio_transcription.completed":
            transcript = str(event.get("transcript") or "").strip()
            if transcript:
                print(f"Du: {transcript[:500]}", flush=True)
                self._capture_requested_window(transcript)
                if self._desktop_input_enabled:
                    try:
                        self._textedit_command_path.parent.mkdir(parents=True, exist_ok=True)
                        line = json.dumps({"text": transcript, "at": time.time()}, ensure_ascii=False) + "\n"
                        descriptor = os.open(
                            self._textedit_command_path,
                            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
                            0o600,
                        )
                        try:
                            os.write(descriptor, line.encode("utf-8"))
                        finally:
                            os.close(descriptor)
                    except OSError as exc:
                        LOGGER.warning("TextEdit-Sprachereignis konnte nicht gespeichert werden: %s", exc)
        elif event_type in {"response.output_audio_transcript.done", "response.output_text.done"}:
            transcript = str(event.get("transcript") or event.get("text") or "").strip()
            if transcript:
                print(f"Trinity: {transcript[:500]}", flush=True)
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
                first_chunk = not self._output and time.monotonic() - self._last_output_at > 0.5
                self._output.extend(audio)
            if first_chunk:
                print("Eve-Audio vom Server empfangen · Wiedergabe auf dem Mac.", flush=True)
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
