"""OpenAI-compatible adapter from the voice pipeline into Trinity's text core."""

from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
import uuid
import queue
from collections.abc import Iterable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..interfaces import ConversationBackend
from ..language_policy import enforce_input_language, segment_for_speech
from ..textedit_commands import SPOKEN_HELP, command_for, unclear_dictation_request
from ..recent_context import RecentVoiceContext
from ..textedit_lease import TextEditVoiceLease
from ..input_selection import AudioInputSelection
from ..diagnostics import diagnostic
from ..desktop_commands import app_to_open, mail_navigation
try:
    from core.sound_deck import SoundDeck
except ImportError:
    from sound_deck import SoundDeck


DEFAULT_WAKEWORD_VARIANTS = (
    "trinity",
    "triniti",
    "trindy",
    "trinnity",
    "trinitiy",
    "trinitys",
    "trinitie",
    "drinity",
    "trinidi",
    "trenty",
    "trendy",
    "trinetti",
    "trinetty",
)

READ_ALOUD_PREFIX = "[[TRINITY_READ_ALOUD_V1]]\n"


def is_transport_compaction(text):
    return (str(text).startswith("Summarize the following conversation.  Return only the JSON object.")
            and "--- CONVERSATION START ---" in str(text))


def _normalize_wakeword_text(value: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    asciiish = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", asciiish.replace("ß", "ss")).strip()


def _bounded_levenshtein(left: str, right: str, max_distance: int) -> int:
    if left == right:
        return 0
    if abs(len(left) - len(right)) > max_distance:
        return max_distance + 1
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, start=1):
        current = [row]
        row_min = row
        for column, right_char in enumerate(right, start=1):
            current.append(min(
                current[column - 1] + 1,
                previous[column] + 1,
                previous[column - 1] + (left_char != right_char),
            ))
            row_min = min(row_min, current[-1])
        if row_min > max_distance:
            return max_distance + 1
        previous = current
    return previous[-1]


def _has_wakeword(text: str, variants: Iterable[str]) -> bool:
    normalized = _normalize_wakeword_text(text)
    if not normalized:
        return False
    compact = normalized.replace(" ", "")
    tokens = normalized.split()
    for raw_candidate in variants:
        candidate = _normalize_wakeword_text(raw_candidate).replace(" ", "")
        if len(candidate) < 5:
            if len(candidate) >= 2 and candidate in tokens:
                return True
            continue
        forms = {candidate}
        if candidate.endswith("y"):
            forms.update({f"{candidate[:-1]}i", f"{candidate[:-1]}ie"})
        if candidate.endswith("i"):
            forms.add(f"{candidate}e")
        if any(form in compact for form in forms):
            return True
        if not (candidate.startswith("trini") or candidate.startswith("drini")):
            continue
        for token in tokens:
            if len(token) < 5:
                continue
            for form in forms:
                distance = 1 if len(form) < 8 else 2
                if _bounded_levenshtein(token, form, distance) <= distance:
                    return True
    return False


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") in {"text", "input_text"}:
                parts.append(str(item.get("text") or ""))
        return " ".join(parts).strip()
    return str(content or "").strip()


class TrinityConversationBackend(ConversationBackend):
    """Route every voice turn through the normal Trinity brain and event store."""

    def __init__(self, home: str | Path):
        self.home = Path(home).expanduser().resolve()
        self.core_dir = self.home / "core"
        self.config_path = self.core_dir / "config.json"
        self.transcript_path = self.home / "TrinityRuntime" / "voice" / "voice_session.md"
        self.transcript_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.transcript_path.exists():
            self.transcript_path.write_text("# Trinity Voice Session\n\n", encoding="utf-8")
        self._brain = None
        self._brain_lock = threading.RLock()
        self._recent_context = RecentVoiceContext()
        self._context_path = self.transcript_path.with_name("voice_context.md")
        self._request_lock = threading.Lock()
        self._request_generation = 0
        self._textedit_dictation = False
        self._textedit_input_epoch = None

    def _desktop_microphone_selected(self) -> bool:
        """Never consume writing commands spoken through a Companion or G2."""
        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return False
        system = config.get("system", {})
        selection = AudioInputSelection(
            self.config_path, self.home / "TrinityRuntime" / "voice" / "input_lease.json"
        ).current()
        epoch = selection.get("updated_at")
        if self._textedit_input_epoch is not None and epoch != self._textedit_input_epoch:
            self._textedit_dictation = False
        self._textedit_input_epoch = epoch
        allowed_device = str(system.get("textedit_voice_device_id") or "").strip()
        self._textedit_dictation = TextEditVoiceLease(
            self.home / "TrinityRuntime" / "voice" / "textedit_lease.json"
        ).active(selection)
        return bool(allowed_device and selection.get("kind") == "desktop"
                    and selection.get("device_id") == allowed_device)

    def _runtime_voice_policy(self) -> tuple[str, tuple[str, ...]]:
        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            config = {}
        mode = str(config.get("system", {}).get("mode", "office") or "office").strip().lower()
        if mode == "chat":
            mode = "office"
        if mode not in {"lecture", "office"}:
            mode = "office"
        configured = config.get("persona", {}).get("trigger_variants") or DEFAULT_WAKEWORD_VARIANTS
        variants = tuple(str(item) for item in configured if str(item).strip())
        if "trinity" in variants:
            # Observed Parakeet renderings of the addressed name; do not make
            # ordinary words such as "trainiert" a broad wakeword.
            variants = tuple(dict.fromkeys((*variants, "trinetti", "trinetty", "trinny")))
        return mode, variants or DEFAULT_WAKEWORD_VARIANTS

    def _ensure_brain(self):
        if self._brain is None:
            import sys

            core = str(self.core_dir)
            if core not in sys.path:
                sys.path.insert(0, core)
            from brain import TrinityBrain

            self._brain = TrinityBrain()
        return self._brain

    def _append_transcript(self, role: str, text: str) -> None:
        self._recent_context.append(role, text)
        stamp = time.strftime("%H:%M:%S")
        with self.transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] [{role}]: {text.strip()}\n")

    def _append_chat_events(self, user_text: str, answer: str, request_id: str) -> None:
        import sys

        core = str(self.core_dir)
        if core not in sys.path:
            sys.path.insert(0, core)
        from chat_protocol import append_chat_event
        from memory_store import MemoryStore
        from tenant_context import tenant_history_path, tenant_memory_db_path
        from unified_session import UnifiedSessionStore

        session = UnifiedSessionStore(self.home).current()
        history = tenant_history_path(self.home)
        common = {
            "request_id": request_id,
            "source": "voice-runtime",
            "session_id": session.id,
            "session_name": session.title,
        }
        append_chat_event(history, {**common, "role": "user", "text": user_text})
        append_chat_event(history, {**common, "role": "assistant", "text": answer, "payload_html": ""})
        memory = MemoryStore(str(tenant_memory_db_path(self.home)))
        memory_session = memory.ensure_session(session.id, session.title)
        memory.add_message(memory_session, "user", user_text, {"source": "voice-runtime"})
        memory.add_message(
            memory_session,
            "assistant",
            answer,
            {"source": "voice-runtime", "request_id": request_id},
        )
        memory.remember(
            f"User: {user_text}\nTrinity: {answer}",
            source="voice-runtime",
            session_id=memory_session,
            weight=0.58,
            metadata={"request_id": request_id},
        )

    def respond_stream(self, text, *, turn_id=""):
        try:
            enabled = json.loads(self.config_path.read_text()).get("system", {}).get("voice_sentence_streaming", False)
        except (OSError, ValueError, AttributeError):
            enabled = False
        if not enabled:
            yield from self.respond(text, turn_id=turn_id)
            return
        from ..sentence_stream import StreamCancelled
        cancelled = threading.Event()
        output = queue.Queue(maxsize=8)
        done = object()
        def put(item):
            while not cancelled.is_set():
                try:
                    output.put(item, timeout=0.1)
                    return
                except queue.Full:
                    pass
            raise StreamCancelled()
        def run():
            emitted = False
            def emit(sentence):
                nonlocal emitted
                put(sentence)
                emitted = True
            try:
                result = self.respond(text, turn_id=turn_id, sentence_callback=emit,
                                      cancelled=cancelled.is_set)
                if not emitted:
                    for sentence in result:
                        put(sentence)
            except StreamCancelled as exc:
                from core.voice.request_scope import RequestExpired
                if isinstance(exc, RequestExpired) and not cancelled.is_set():
                    diagnostic(self.home, "LLM", "Zeitbudget überschritten; Modellanfrage beendet, keine Antwort gespeichert.")
                    if not emitted:
                        put("Das Modell antwortet gerade nicht rechtzeitig. Bitte versuche es noch einmal.")
                pass
            except Exception as exc:
                if not cancelled.is_set():
                    put(exc)
            finally:
                if not cancelled.is_set():
                    put(done)
        worker = threading.Thread(target=run, name="trinity-sentence-stream", daemon=True)
        worker.start()
        try:
            while True:
                try:
                    item = output.get(timeout=0.5)
                except queue.Empty:
                    # HTTP comments keep the transport alive and detect a
                    # disconnected listener even before the first sentence.
                    yield None
                    continue
                if item is done:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            cancelled.set()

    def respond(self, text: str, *, session_id: str = "", turn_id: str = "",
                sentence_callback=None, cancelled=lambda: False) -> Iterable[str]:
        query = str(text or "").strip()
        if not query:
            return []
        deck = SoundDeck(self.home)
        if deck.command(query) is not None:
            try:
                deck.execute_voice(query)
                diagnostic(self.home, "DeckUI", "Klangsteuerung ausgeführt.")
                return []
            except ValueError as exc:
                return [str(exc)]
        if is_transport_compaction(query):
            diagnostic(self.home, "Verlauf", "Interne Transport-Zusammenfassung abgefangen; keine Gesprächsfrage.")
            return []
        # Start/stop controls and wakeword-free listening turns also supersede
        # pending older answers; they must not leak into the next activity.
        with self._request_lock:
            self._request_generation += 1
            generation = self._request_generation
        if self._desktop_microphone_selected():
            if app_to_open(query) or mail_navigation(query):
                self._textedit_dictation = False
                TextEditVoiceLease(self.home / "TrinityRuntime" / "voice" / "textedit_lease.json").update("", False, None)
                return []
            command = command_for(query, dictating=self._textedit_dictation)
            if command in {"window_capture_on", "window_capture_off", "dictation_invalid"}:
                return []
            if command is None and not self._textedit_dictation and unclear_dictation_request(query):
                diagnostic(self.home, "Diktat", "Startbefehl unklar; kein Schreibmodus gestartet.")
                return ["Startbefehl nicht sicher erkannt. Sag bitte nur: Diktat starten."]
            if command == "dictation_start":
                # Recognition alone is not confirmation: TextEdit/focus or
                # Accessibility may fail on the Mac. Wait for its live lease.
                return []
            if command == "dictation_stop":
                self._textedit_dictation = False
                TextEditVoiceLease(self.home / "TrinityRuntime" / "voice" / "textedit_lease.json").update(
                    "", False, None)
                return []
            if command in {"summarize", "revise", "write_notes"}:
                self._textedit_dictation = False
                TextEditVoiceLease(self.home / "TrinityRuntime" / "voice" / "textedit_lease.json").update("", False, None)
                return []
            if self._textedit_dictation:
                # The Mac writes completed STT chunks directly into TextEdit.
                # Do not send dictated prose to the LLM or persistent memory.
                return []
            if command == "help":
                return segment_for_speech(SPOKEN_HELP)
            if command == "show_help":
                return []
            if command == "help_insert":
                return []
            if command == "insert_last":
                return []
            if command == "delete_thoughts":
                return []
            if command in {"summarize", "revise", "accept_revision", "confirm_delete_thoughts", "close_draft"}:
                # The Mac handles these against a verified TextEdit document.
                return []
        else:
            self._textedit_dictation = False
        mode, wakeword_variants = self._runtime_voice_policy()
        if mode == "lecture" and not _has_wakeword(query, wakeword_variants):
            diagnostic(self.home, "Wakeword", "Vortrag-Modus: kein Wakeword erkannt. Für direkten Dialog Büro/Konversation wählen.")
            self._append_transcript("Lecture (ohne Wakeword)", query)
            return []
        rejection = enforce_input_language(query)
        if rejection:
            return [rejection]
        request_id = turn_id or uuid.uuid4().hex
        # New questions supersede queued requests, not the permanent memory.
        with self._brain_lock:
            if cancelled() or generation != self._request_generation:
                return []
            self._append_transcript("User", query)
            self._context_path.write_text(self._recent_context.render(), encoding="utf-8")
            self._context_path.chmod(0o600)
            desktop_image_available = None
            from visual_source import visual_output
            visual_selection = visual_output(self.home)
            if visual_selection.get("kind") == "desktop":
                from desktop_context import wait_for_requested_desktop
                from ..window_request import wants_window
                if wants_window(query):
                    diagnostic(self.home, "Fenster", "Warte kurz auf die angeforderte Aufnahme vom Mac.")
                    available = wait_for_requested_desktop(self.home, query, visual_selection.get("device_id", ""))
                    desktop_image_available = available
                    diagnostic(self.home, "Fenster", "Bild angekommen." if available else "Kein aktuelles Bild angekommen; Gespräch bleibt möglich.")
            started = time.monotonic()
            def stale():
                return cancelled() or generation != self._request_generation
            def emit(sentence):
                from ..sentence_stream import StreamCancelled
                if stale():
                    raise StreamCancelled()
                sentence_callback(sentence)
            diagnostic(self.home, "LLM", "Antwort wird berechnet.")
            from core.voice.request_scope import request_scope
            from ..sentence_stream import StreamCancelled
            try:
                with request_scope(stale) as scope:
                    answer, _has_payload = self._ensure_brain().ask(
                        query,
                        str(self._context_path),
                        text_mode=False,
                        action_text=query,
                        attachments=[],
                        voice_budget=True,
                        desktop_image_available=desktop_image_available,
                        **({"sentence_callback": emit, "cancelled": scope.stale} if sentence_callback else {}),
                    )
                    scope.check()
            except StreamCancelled:
                if stale():
                    diagnostic(self.home, "LLM", "Alte oder getrennte Antwort beendet; kein Memory-Schreibzugriff.")
                    return []
                raise
            if stale():
                diagnostic(self.home, "LLM", "Antwort durch neuere Frage ersetzt.")
                return []
            diagnostic(self.home, "LLM", f"Antwort fertig nach {time.monotonic() - started:.1f} s; {len(answer)} Zeichen. Jetzt TTS.")
            self._append_transcript("Trinity", answer)
            self._append_chat_events(query, answer, request_id)
        return segment_for_speech(answer)


class TrinityConversationHTTPServer:
    """Expose a local-only Chat Completions endpoint to speech-to-speech."""

    def __init__(self, backend: ConversationBackend, host: str, port: int, token: str):
        self.backend = backend
        self.host = host
        self.port = int(port)
        self.token = token
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "TrinityVoiceBackend/1"

            def log_message(self, _format: str, *_args: Any) -> None:
                return

            def _json(self, status: int, payload: dict[str, Any]) -> None:
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _authorized(self) -> bool:
                expected = owner.token
                if not expected:
                    return True
                return self.headers.get("Authorization", "") == f"Bearer {expected}"

            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/health":
                    self._json(HTTPStatus.OK, {"ok": True, "backend": type(owner.backend).__name__})
                    return
                if self.path.rstrip("/") == "/v1/models":
                    self._json(HTTPStatus.OK, {"object": "list", "data": [{"id": "trinity-core", "object": "model"}]})
                    return
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

            def do_POST(self) -> None:  # noqa: N802
                if self.path.rstrip("/") != "/v1/chat/completions":
                    self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                    return
                if not self._authorized():
                    self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    body = json.loads(self.rfile.read(length).decode("utf-8"))
                    messages = body.get("messages") or []
                    user_message = next(
                        (item for item in reversed(messages) if isinstance(item, dict) and item.get("role") == "user"),
                        {},
                    )
                    prompt = _message_text(user_message.get("content"))
                    turn_id = str(body.get("user") or uuid.uuid4().hex)
                    # Playback of an existing answer bypasses the LLM, wakeword gate and memory.
                    if prompt.startswith(READ_ALOUD_PREFIX):
                        answer = prompt[len(READ_ALOUD_PREFIX):].strip()[:12000]
                    elif not body.get("stream"):
                        answer = " ".join(owner.backend.respond(prompt, turn_id=turn_id)).strip()
                    if body.get("stream"):
                        streaming_started = True
                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                        self.send_header("Cache-Control", "no-cache")
                        self.end_headers()
                        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
                        segments = (segment_for_speech(answer) if prompt.startswith(READ_ALOUD_PREFIX)
                                    else getattr(owner.backend, "respond_stream", owner.backend.respond)(prompt, turn_id=turn_id))
                        try:
                            for segment in segments:
                                import select
                                import socket
                                if select.select([self.connection], [], [], 0)[0]:
                                    if not self.connection.recv(1, socket.MSG_PEEK):
                                        raise BrokenPipeError("Voice listener disconnected")
                                if segment is None:
                                    self.wfile.write(b": trinity-pending\n\n")
                                    self.wfile.flush()
                                    continue
                                payload = {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": "trinity-core",
                                    "choices": [{"index": 0, "delta": {"content": segment + " "}, "finish_reason": None}],
                                }
                                self.wfile.write(f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8"))
                                self.wfile.flush()
                        finally:
                            if hasattr(segments, "close"):
                                segments.close()
                        self.wfile.write(b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n')
                        self.wfile.write(b"data: [DONE]\n\n")
                        self.wfile.flush()
                        return
                    self._json(HTTPStatus.OK, {
                        "id": f"chatcmpl-{uuid.uuid4().hex}",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": "trinity-core",
                        "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    })
                except Exception as exc:  # return a protocol error without leaking secrets
                    safe = re.sub(r"(?i)(token|key|authorization)\s*[:=]\s*\S+", r"\1=<redacted>", str(exc))
                    if getattr(owner.backend, "home", None):
                        diagnostic(owner.backend.home, "Fehler", f"Antwort abgebrochen: {type(exc).__name__}")
                    if locals().get("streaming_started"):
                        self.close_connection = True
                        return  # never append a second HTTP response to an SSE stream
                    self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": {"message": safe, "type": "trinity_backend_error"}})

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, name="trinity-voice-backend", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=3)
        self._server = None
        self._thread = None
