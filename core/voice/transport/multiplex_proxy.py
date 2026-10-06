"""One upstream Eve session shared by independently selected input/output devices."""

from __future__ import annotations

import asyncio
import base64
import copy
import hmac
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from collections import deque

from ..input_selection import AudioInputSelection
from .auth_proxy import _token_from_request
try:
    from core.sound_deck import SoundDeck
except ImportError:
    from sound_deck import SoundDeck


class MultiplexingVoiceRouter:
    """Keep exactly one speech-to-speech pipeline open across device changes.

    Downstream realtime clients are transport peers, not upstream sessions.
    Audio input is accepted only from the selected microphone; generated audio
    is sent only to the selected speaker. G2 uses a loopback-only STT request
    against the same upstream Parakeet instance.
    """

    def __init__(self, host, port, upstream_port, tokens, config_path, *, stt_port=18768):
        self.host = str(host)
        self.port = int(port)
        self.upstream_port = int(upstream_port)
        self.tokens = tuple(dict.fromkeys(token for token in tokens if token))
        self.config_path = Path(config_path)
        self.selection = AudioInputSelection(
            self.config_path,
            self.config_path.parent.parent / "TrinityRuntime" / "voice" / "input_lease.json",
        )
        self.stt_port = int(stt_port)
        self._thread = None
        self._loop = None
        self._server = None
        self._http_server = None
        self._http_thread = None
        self._ready = threading.Event()
        self._error = None
        self._upstream = None
        self._clients = {}
        self._outboxes = {}
        self._session_created = None
        self._last_session_update = None
        self._send_lock = None
        self._transcribe_lock = None
        self._transcript_waiter = None
        self._transcript_item_id = None
        self._response_audio_seconds = 0.0
        self._response_first_audio_at = 0.0
        self._output_activity_started = False
        self._output_blocked_until = 0.0
        self._activity_heartbeat_at = 0.0
        self._last_audio_input_at = time.monotonic()
        self._response_chunks = deque()
        self._response_finished = False
        self._diagnostic_path = self.config_path.parent.parent / "TrinityRuntime/voice/diagnostic_events.jsonl"
        self._diagnostic_offset = self._diagnostic_path.stat().st_size if self._diagnostic_path.exists() else 0
        self.deck = SoundDeck(self.config_path.parent.parent)
        self._deck_revision = {}
        self._deck_active = False
        self._deck_activity_at = 0.0

    def _output_id(self):
        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
            target = config.get("system", {}).get("speech_output", {})
            return str(target.get("device_id") or "") if target.get("kind") != "none" else ""
        except (OSError, ValueError, TypeError):
            return ""

    def _input_id(self):
        return str(self.selection.current().get("device_id") or "")

    async def _send_upstream(self, event):
        if self._upstream is None:
            raise ConnectionError("Parakeet-Realtime ist nicht verbunden.")
        async with self._send_lock:
            # Trinity's transport-only setting is not part of upstream Realtime.
            wire = {key: value for key, value in event.items() if key != "trinity_allow_barge_in"}
            await self._upstream.send(json.dumps(wire, ensure_ascii=False))

    def _playback_tail_ms(self):
        return min(300_000, max(0, int((self._output_blocked_until - time.monotonic()) * 1000)))

    def _mask_input_echo(self, event):
        """Keep VAD time continuous while suppressing an acoustic answer echo.

        Input packets already in flight when playback begins can otherwise
        immediately cancel the very answer whose first audio just arrived.
        Explicit headphone clients may opt into interruption; buttons always work.
        """
        if event.get("type") != "input_audio_buffer.append":
            return event
        if (self._last_session_update or {}).get("trinity_allow_barge_in") is True:
            return event
        if not (self._output_activity_started or self._deck_active or self._playback_tail_ms()):
            return event
        encoded = event.get("audio")
        if not isinstance(encoded, str) or len(encoded) > 262_144:
            return None
        try:
            samples = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            return None
        return {**event, "audio": base64.b64encode(bytes(len(samples))).decode("ascii")}

    async def _keep_vad_clock_running(self):
        # Older Mac/Companion clients completely stop sending during playback.
        # Supply only silence through the SAME pipeline, not a second input/STT.
        if not self._upstream or not self._input_id():
            return
        if not (self._output_activity_started or self._deck_active or self._playback_tail_ms()):
            return
        elapsed = time.monotonic() - self._last_audio_input_at
        if elapsed < 0.20:
            return
        self._last_audio_input_at = time.monotonic()
        audio = base64.b64encode(bytes(6400)).decode("ascii")  # 200 ms, mono/16 kHz PCM16
        await self._send_upstream({"type": "input_audio_buffer.append", "audio": audio})

    def _enqueue(self, client, raw):
        """A stalled device must never stall Parakeet or the other device."""
        if client not in self._outboxes:
            queue = deque()
            ready = asyncio.Event()
            task = asyncio.create_task(self._write_client(client, queue, ready))
            self._outboxes[client] = (queue, ready, task)
        queue, ready, _task = self._outboxes[client]
        event = json.loads(raw)
        partial = event.get("type") in {
            "conversation.item.input_audio_transcription.delta",
            "conversation.item.input_audio_transcription.partial",
        }
        if partial:
            # Partials are cumulative snapshots, unlike PCM audio deltas.
            # Keep only the newest unsent snapshot for the same speech item.
            key = (event.get("type"), event.get("item_id"))
            for index in range(len(queue) - 1, -1, -1):
                if queue[index][0] == key:
                    del queue[index]
        else:
            key = None
        if len(queue) >= 512:
            # Never drop arbitrary PCM blocks (that corrupts speech). Disconnect
            # instead; the client's normal reconnect can replay the audio tail.
            self._clients.pop(client, None)
            self._drop_outbox(client)
            asyncio.create_task(client.close(code=1013, reason="Slow voice client; reconnect"))
            return
        queue.append((key, raw))
        ready.set()

    async def _write_client(self, client, queue, ready):
        try:
            while True:
                await ready.wait()
                while queue:
                    _key, raw = queue.popleft()
                    await asyncio.wait_for(client.send(raw), timeout=2)
                ready.clear()
        except asyncio.CancelledError:
            raise
        except Exception:
            self._clients.pop(client, None)
            await client.close(code=1013, reason="Slow or disconnected voice client")

    def _drop_outbox(self, client):
        state = self._outboxes.pop(client, None)
        if state:
            state[2].cancel()

    async def _reader(self, upstream):
        async for raw in upstream:
            try:
                event = json.loads(raw)
            except (TypeError, ValueError):
                continue
            event_type = str(event.get("type") or "")
            if event_type == "response.created":
                self._response_audio_seconds = 0.0
                self._response_first_audio_at = 0.0
                self._output_activity_started = False
                self._response_chunks.clear()
                self._response_finished = False
            if event_type in {"response.output_audio.delta", "response.audio.delta"}:
                encoded = str(event.get("delta") or "")
                self._response_audio_seconds += (len(encoded) * 3 / 4) / (24_000 * 2)
                self._response_chunks.append((self._response_audio_seconds, raw))
                while self._response_chunks and self._response_chunks[0][0] < self._response_audio_seconds - 30:
                    self._response_chunks.popleft()
                if not self._output_activity_started:
                    self._output_activity_started = True
                    self._response_first_audio_at = time.monotonic()
                    await self._notify_input_output_activity(True, 0)
                self._output_blocked_until = max(self._output_blocked_until,
                    self._response_first_audio_at + self._response_audio_seconds + 0.5)
            if event_type == "response.done" and self._output_activity_started:
                self._response_finished = True
                # The server can synthesize faster than the chosen speaker plays.
                # Keep the glasses deaf to acoustic playback, not merely to generation.
                cancelled = event.get("response", {}).get("status") in {"cancelled", "failed"}
                if cancelled:
                    self._output_blocked_until = time.monotonic() + 0.35
                    self._response_chunks.clear()
                hold_ms = self._playback_tail_ms()
                await self._notify_input_output_activity(False, hold_ms)
                self._output_activity_started = False
            if event_type == "session.created":
                self._session_created = event
            if event_type == "input_audio_buffer.speech_started" and self._transcript_waiter is not None:
                self._transcript_item_id = str(event.get("item_id") or "")
            if event_type == "conversation.item.input_audio_transcription.completed":
                waiter = self._transcript_waiter
                item_id = str(event.get("item_id") or "")
                if waiter is not None and not waiter.done() and (
                    self._transcript_item_id and item_id == self._transcript_item_id
                ):
                    waiter.set_result(str(event.get("transcript") or ""))
            output_id = self._output_id()
            input_id = self._input_id()
            audio_output = event_type.startswith("response.") and "audio" in event_type
            recipients = [
                client for client, device_id in tuple(self._clients.items())
                if device_id == output_id or (not audio_output and device_id == input_id)
            ]
            for client in recipients:
                self._enqueue(client, raw)

    async def _notify_input_output_activity(self, active, hold_ms):
        active = active or self._deck_active
        payload = json.dumps({"type": "trinity.output_activity", "active": active,
                              "hold_ms": hold_ms, "lease_ms": 8000})
        input_id = self._input_id()
        for client, device_id in tuple(self._clients.items()):
            if device_id != input_id:
                continue
            self._enqueue(client, payload)

    async def _supervise_upstream(self):
        import websockets

        while True:
            try:
                async with websockets.connect(
                    f"ws://127.0.0.1:{self.upstream_port}/v1/realtime",
                    max_size=None,
                ) as upstream:
                    self._upstream = upstream
                    self._session_created = None
                    await self._reader(upstream)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            finally:
                self._upstream = None
                self._output_blocked_until = 0.0
                self._session_created = None
                if self._output_activity_started:
                    await self._notify_input_output_activity(False, 0)
                    self._output_activity_started = False
                if self._transcript_waiter and not self._transcript_waiter.done():
                    self._transcript_waiter.set_exception(ConnectionError("Parakeet-Verbindung unterbrochen."))
                for client in tuple(self._clients):
                    self._drop_outbox(client)
                    try:
                        await client.close(code=1012, reason="Voice server reconnecting")
                    except Exception:
                        pass
                self._clients.clear()
            await asyncio.sleep(1.0)

    async def _handle_client(self, client):
        request = getattr(client, "request", None)
        path = getattr(request, "path", "/")
        headers = getattr(request, "headers", {})
        supplied = _token_from_request(path, headers)
        if self.tokens and not any(hmac.compare_digest(supplied, token) for token in self.tokens):
            await client.close(code=4401, reason="Unauthorized")
            return
        device_id = str((parse_qs(urlsplit(path).query).get("device_id") or [""])[0])[:160]
        if not device_id:
            await client.close(code=4403, reason="Device ID required")
            return
        if device_id not in {self._input_id(), self._output_id()}:
            await client.close(code=4403, reason="Select input or output first")
            return
        for peer, previous_device in tuple(self._clients.items()):
            if previous_device == device_id:
                self._clients.pop(peer, None)
                self._drop_outbox(peer)
                await peer.close(code=4409, reason="New connection for this device")
        self._clients[client] = device_id
        if self._session_created:
            await client.send(json.dumps(self._session_created, ensure_ascii=False))
        if device_id == self._input_id() and self._response_first_audio_at:
            remaining = self._response_audio_seconds - (time.monotonic() - self._response_first_audio_at) + 1.5
            if self._output_activity_started:
                await client.send(json.dumps({"type": "trinity.output_activity", "active": True, "hold_ms": 0}))
            elif remaining > 0:
                await client.send(json.dumps({"type": "trinity.output_activity", "active": False,
                                              "hold_ms": min(300_000, int(remaining * 1000))}))
        if device_id == self._output_id() and self._response_first_audio_at:
            elapsed = time.monotonic() - self._response_first_audio_at
            if elapsed < self._response_audio_seconds + 0.5:
                # A newly selected output receives the unheard PCM tail, then
                # continues with new deltas from the one upstream session.
                for end_seconds, audio_raw in tuple(self._response_chunks):
                    if end_seconds > elapsed - 0.25:
                        await client.send(audio_raw)
        try:
            async for raw in client:
                try:
                    event = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                event_type = str(event.get("type") or "")
                input_selected = device_id == self._input_id()
                output_selected = device_id == self._output_id()
                if event_type == "trinity.deck.ack":
                    if output_selected:
                        try:
                            self.deck.acknowledge(str(event.get("revision", "")), device_id, str(event.get("status", "")))
                        except Exception:
                            pass  # A deck storage failure must not drop voice.
                    continue
                if event_type.startswith("input_audio_buffer.") and not input_selected:
                    continue
                if event_type == "session.update":
                    if not input_selected:
                        continue
                    self._last_session_update = event
                elif event_type == "response.create" and not output_selected:
                    continue
                elif event_type == "response.cancel" and not (input_selected or output_selected):
                    continue
                elif event_type == "conversation.item.create" and not (input_selected or output_selected):
                    continue
                try:
                    if event_type == "response.cancel":
                        self._output_blocked_until = time.monotonic() + 0.35
                        self._output_activity_started = False
                        self._response_chunks.clear()
                        await self._notify_input_output_activity(False, 350)
                        try:
                            if self.deck.state().get("active"):
                                self.deck.toggle("", stop=True)
                        except Exception:
                            pass
                    event = self._mask_input_echo(event)
                    if event is None:
                        continue
                    if event_type == "input_audio_buffer.append":
                        self._last_audio_input_at = time.monotonic()
                    await self._send_upstream(event)
                    if event_type == "response.cancel" and input_selected and not output_selected:
                        # A G2 double tap stops the selected speaker's buffered
                        # playback as well as upstream generation. Existing
                        # Companion and Mac clients already flush on this event.
                        interrupted = json.dumps({"type": "input_audio_buffer.speech_started"})
                        for output_client, output_device in tuple(self._clients.items()):
                            if output_device == self._output_id():
                                try:
                                    await output_client.send(interrupted)
                                except Exception:
                                    self._clients.pop(output_client, None)
                        self._response_chunks.clear()
                        await self._notify_input_output_activity(False, 1500)
                except ConnectionError:
                    await client.close(code=1012, reason="Voice server unavailable")
                    break
        finally:
            self._clients.pop(client, None)
            self._drop_outbox(client)

    async def _watch_selection(self):
        while True:
            await asyncio.sleep(0.25)
            allowed = {self._input_id(), self._output_id()}
            try:
                await self._keep_vad_clock_running()
            except Exception:
                # Upstream can disappear between the availability check and
                # send. Its supervisor reconnects; this watcher must survive.
                pass
            self._relay_diagnostics(allowed)
            # The HTTP bridge and voice backend share only this tiny control DB,
            # not PCM or another model. Offline clients cannot hold a sound forever.
            try:
                state = await asyncio.to_thread(self.deck.state)
            except Exception:
                state = {"type": "trinity.deck", "revision": "deck-unavailable", "active": False,
                         "error": "DeckUI momentan nicht verfügbar."}
            active = bool(state.get("active") and state.get("playing"))
            if active != self._deck_active or active and time.monotonic() >= self._deck_activity_at:
                self._deck_active = active
                self._deck_activity_at = time.monotonic() + 2
                await self._notify_input_output_activity(active or self._output_activity_started,
                    max(350, self._playback_tail_ms()))
            # Renew short client leases during synthesis/playout. A lost end
            # event or reconnect must never leave a microphone blocked for minutes.
            if time.monotonic() >= self._activity_heartbeat_at:
                self._activity_heartbeat_at = time.monotonic() + 2
                await self._notify_input_output_activity(self._output_activity_started,
                    self._playback_tail_ms())
            for client, device_id in tuple(self._clients.items()):
                if device_id in allowed and self._deck_revision.get(client) != state.get("revision"):
                    self._deck_revision[client] = state.get("revision")
                    self._enqueue(client, json.dumps(state, ensure_ascii=False))
            self._deck_revision = {client: rev for client, rev in self._deck_revision.items() if client in self._clients}
            for client, device_id in tuple(self._clients.items()):
                if device_id not in allowed:
                    try:
                        await client.close(code=4409, reason="Voice moved to another device")
                    except Exception:
                        pass

    def _relay_diagnostics(self, allowed):
        try:
            with self._diagnostic_path.open("rb") as handle:
                if self._diagnostic_path.stat().st_size < self._diagnostic_offset:
                    self._diagnostic_offset = 0
                handle.seek(self._diagnostic_offset)
                for _ in range(50):
                    raw = handle.readline(4096)
                    if not raw or not raw.endswith(b"\n"):
                        break
                    self._diagnostic_offset = handle.tell()
                    try:
                        event = json.loads(raw)
                    except ValueError:
                        continue
                    if event.get("type") == "trinity.debug":
                        for client, device_id in tuple(self._clients.items()):
                            if device_id in allowed:
                                self._enqueue(client, json.dumps(event, ensure_ascii=False))
        except OSError:
            pass

    @staticmethod
    def _stt_session(create_response, previous=None):
        session = copy.deepcopy((previous or {}).get("session") or {})
        session.setdefault("type", "realtime")
        audio = session.setdefault("audio", {})
        incoming = audio.setdefault("input", {})
        incoming.setdefault("transcription", {"language": "de", "model": "parakeet-tdt"})
        detection = incoming.setdefault("turn_detection", {"type": "server_vad"})
        detection["create_response"] = bool(create_response)
        detection.setdefault("prefix_padding_ms", 320)
        detection.setdefault("silence_duration_ms", 420)
        return {"type": "session.update", "session": session}

    async def transcribe_g2(self, audio_base64):
        if self._input_id() == "none" or self.selection.current().get("kind") != "g2":
            raise PermissionError("Die G2 ist nicht als Mikrofon ausgewählt.")
        raw = base64.b64decode(str(audio_base64 or ""), validate=True)
        if not raw or len(raw) % 2 or len(raw) > 16_000 * 2 * 20:
            raise ValueError("G2-Audio muss 16-kHz-PCM mit höchstens 20 Sekunden sein.")
        async with self._transcribe_lock:
            previous = self._last_session_update
            waiter = self._loop.create_future()
            self._transcript_waiter = waiter
            self._transcript_item_id = None
            try:
                await self._send_upstream(self._stt_session(False, previous))
                await self._send_upstream({"type": "input_audio_buffer.append", "audio": audio_base64})
                # G2 already includes end silence; an extra tail ensures VAD closes.
                await self._send_upstream({"type": "input_audio_buffer.append", "audio": base64.b64encode(bytes(16_000 * 2)).decode("ascii")})
                transcript = await asyncio.wait_for(waiter, timeout=18)
                return {"ok": True, "text": transcript, "language": "de", "engine": "parakeet-shared"}
            finally:
                self._transcript_waiter = None
                self._transcript_item_id = None
                if self._upstream is not None:
                    await self._send_upstream(previous or self._stt_session(True))

    def _start_http(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def do_POST(self):  # noqa: N802
                if self.path != "/v1/audio/transcriptions":
                    self.send_error(404)
                    return
                supplied = self.headers.get("Authorization", "")
                if owner.tokens and not any(hmac.compare_digest(supplied, f"Bearer {token}") for token in owner.tokens):
                    self.send_error(401)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > 1_000_000:
                        raise ValueError("Ungültige Audio-Anfragegröße.")
                    payload = json.loads(self.rfile.read(length))
                    future = asyncio.run_coroutine_threadsafe(
                        owner.transcribe_g2(payload.get("audio_base64", "")), owner._loop
                    )
                    result = future.result(timeout=22)
                    status = 200
                except (ValueError, PermissionError) as exc:
                    status, result = 400, {"ok": False, "error": str(exc)}
                except Exception as exc:
                    status, result = 503, {"ok": False, "error": type(exc).__name__}
                data = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self._http_server = ThreadingHTTPServer(("127.0.0.1", self.stt_port), Handler)
        self._http_thread = threading.Thread(target=self._http_server.serve_forever, daemon=True)
        self._http_thread.start()

    def _run(self):
        import websockets

        async def main():
            self._loop = asyncio.get_running_loop()
            self._send_lock = asyncio.Lock()
            self._transcribe_lock = asyncio.Lock()
            self._start_http()
            self._server = await websockets.serve(self._handle_client, self.host, self.port, max_size=None)
            supervisor = asyncio.create_task(self._supervise_upstream())
            watcher = asyncio.create_task(self._watch_selection())
            self._ready.set()
            try:
                await self._server.wait_closed()
            finally:
                supervisor.cancel()
                watcher.cancel()
                await asyncio.gather(supervisor, watcher, return_exceptions=True)

        try:
            asyncio.run(main())
        except BaseException as exc:
            self._error = exc
            self._ready.set()

    def start(self, timeout=6.0):
        self._thread = threading.Thread(target=self._run, name="trinity-voice-router", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            raise TimeoutError("Eve-Router wurde nicht rechtzeitig bereit.")
        if self._error:
            raise RuntimeError(f"Eve-Router konnte nicht starten: {self._error}")

    def stop(self):
        if self._http_server:
            self._http_server.shutdown()
            self._http_server.server_close()
        if self._http_thread:
            self._http_thread.join(timeout=3)
        if self._loop and self._server and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._server.close)
        if self._thread:
            self._thread.join(timeout=5)
