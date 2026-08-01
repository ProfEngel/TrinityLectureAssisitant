"""OpenAI-compatible adapter from the voice pipeline into Trinity's text core."""

from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
import uuid
from collections.abc import Iterable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..interfaces import ConversationBackend
from ..language_policy import enforce_input_language, segment_for_speech


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
)


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

    def respond(self, text: str, *, session_id: str = "", turn_id: str = "") -> Iterable[str]:
        query = str(text or "").strip()
        if not query:
            return []
        mode, wakeword_variants = self._runtime_voice_policy()
        if mode == "lecture" and not _has_wakeword(query, wakeword_variants):
            self._append_transcript("Lecture (ohne Wakeword)", query)
            return []
        rejection = enforce_input_language(query)
        if rejection:
            return [rejection]
        request_id = turn_id or uuid.uuid4().hex
        with self._brain_lock:
            self._append_transcript("User", query)
            answer, _has_payload = self._ensure_brain().ask(
                query,
                str(self.transcript_path),
                text_mode=False,
                action_text=query,
                attachments=[],
            )
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
                    answer = " ".join(owner.backend.respond(prompt, turn_id=turn_id)).strip()
                    if body.get("stream"):
                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", "text/event-stream")
                        self.send_header("Cache-Control", "no-cache")
                        self.end_headers()
                        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
                        for segment in segment_for_speech(answer):
                            payload = {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": "trinity-core",
                                "choices": [{"index": 0, "delta": {"content": segment + " "}, "finish_reason": None}],
                            }
                            self.wfile.write(f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8"))
                            self.wfile.flush()
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
