"""Small HTTP bridge for Trinity companion clients on a trusted tailnet."""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from html import unescape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import url2pathname

from agent_catalog import build_agent_catalog, normalize_catalog_overrides
from bridge_audio import BridgeAudioTranscriber
from chat_attachments import attachment_kind
from chat_protocol import (
    append_chat_event,
    build_chat_request,
    enqueue_chat_request,
    load_chat_events,
    remove_chat_event,
)
from canvas_manager import CanvasManager
from configuration import load_config, save_config
from external_stt_feed import append_external_stt_event
from memory_store import MemoryStore
from runtime_reset import delete_session_summary
from platform_adapters import (
    find_codex_executable,
    find_opencode_executable,
    find_pi_executable,
)
from server_auth import ServerAuth
from tenant_context import tenant_history_path, tenant_memory_db_path, tenant_upload_dir
from trinity_paths import TrinityPaths
from unified_session import UnifiedSessionStore
from web_ui import render_web_ui
from workbench import WorkbenchManager
from workspace_manager import INBOX_WORKSPACE_ID, TrinityWorkspaceManager


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
# Zwei PDF-Anlagen mit jeweils bis zu 30 MB werden als Base64 übertragen.
# Dafür braucht der JSON-Request etwas mehr Platz als die reinen Dateien.
MAX_BODY_BYTES = 85 * 1024 * 1024
MAX_ATTACHMENT_BYTES = 30 * 1024 * 1024
MAX_EVENTS = 200
MAX_SETTINGS_TEXT_BYTES = 100 * 1024
SETTINGS_SECTIONS = {
    "llm", "apis", "persona", "image", "stt", "tts", "proactive", "system",
    "audio_routing", "telegram", "codex", "opencode", "pi", "comfyui",
    "companion", "server", "client", "control_plane", "harness_routing",
    "agent_catalog", "workbench",
}
QUIET_GET_LOG_PATHS = {
    "/health",
    "/events",
    "/payload",
    "/bubble",
    "/workspaces",
    "/dashboard",
    "/memory/graph",
}


def _verbose_bridge_get_logs():
    return str(os.environ.get("TRINITY_BRIDGE_VERBOSE_GETS", "")).strip().lower() in {
        "1", "true", "yes", "on"
    }


def _should_log_bridge_request(command, path, message):
    if _verbose_bridge_get_logs():
        return True
    if command != "GET":
        return True
    if urlparse(path).path not in QUIET_GET_LOG_PATHS:
        return True
    # Keep errors visible, but hide successful polling noise from the terminal.
    return '" 200 ' not in message


def _json_response(handler, status, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header(
        "Access-Control-Allow-Headers",
        "Content-Type, Authorization, X-Trinity-Profile",
    )
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(data)


def _html_response(handler, status, content):
    data = content.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length > MAX_BODY_BYTES:
        raise ValueError("Request ist zu groß.")
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _is_relative_to(path, root):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _local_path_value(raw_path):
    value = unquote(str(raw_path or ""))
    if value.startswith("file://"):
        parsed = urlparse(value)
        value = url2pathname(parsed.path)
    if re.match(r"^/[A-Za-z]:[\\/]", value):
        value = value[1:]
    return value


class TrinityBridge:
    def __init__(self, home, token="", auth_enabled=False):
        self.home = Path(home).resolve()
        self.core_dir = self.home / "core"
        self.memory_dir = self.home / "memory"
        self.upload_dir = self.memory_dir / "companion_uploads"
        self.history_path = self.memory_dir / "classic_chat_history.jsonl"
        self.command_path = self.core_dir / "cmd.txt"
        self.stt_feed_path = self.core_dir / "ios_stt_feed.jsonl"
        self.payload_path = self.core_dir / "payload.html"
        self.config_path = self.core_dir / "config.json"
        self.bubble_payload_path = self.core_dir / "bubble_payload.html"
        self.state_path = self.core_dir / "state.txt"
        self.token = token or ""
        self.auth_enabled = bool(auth_enabled)
        self.auth = ServerAuth(self.home) if self.auth_enabled else None
        self._lock = threading.Lock()
        self._session_close_lock = threading.Lock()
        self._summary_jobs = set()
        self._audio_transcriber = None
        self._canvas_status_cache = (0.0, {})
        self.sessions = UnifiedSessionStore(self.home, load_config(self.config_path))
        self.workbench = WorkbenchManager(self.home)

    @property
    def profile(self):
        return self.sessions.profile

    def current_session(self):
        return self.sessions.as_dict()

    def instance_state(self):
        paths = TrinityPaths.from_config(self.home, load_config(self.config_path))
        rag_meta_path = self.home / "RAG" / "index" / "meta.json"
        try:
            rag_meta = json.loads(rag_meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            rag_meta = {}
        rag_profile = str(rag_meta.get("profile") or "").strip().upper()
        if not rag_meta:
            rag_scope = "NOT_BUILT"
        elif rag_profile == paths.profile:
            rag_scope = paths.profile
        else:
            rag_scope = "LEGACY_UNSCOPED"
        return {
            "profile": paths.profile,
            "session": self.current_session(),
            "knowledge": {
                "vault_root": str(paths.vault_root),
                "vault_available": paths.vault_root.is_dir(),
                "runtime_root": str(paths.runtime_root),
                "rag_index_scope": rag_scope,
                "rag_sources": list(rag_meta.get("sources") or []),
                "graphify_index_scope": "NOT_BUILT",
            },
        }

    def validate_client_profile(self, value):
        expected = str(value or "").strip().upper()
        if expected and expected != self.profile:
            raise PermissionError(
                f"Profil verwechselt: Client erwartet {expected}, diese Trinity ist {self.profile}."
            )

    @property
    def media_roots(self):
        return [
            self.home / "gen_images",
            self.core_dir,
            self.home / "agents" / "comfyui_agent" / "media",
            self.home / "memory",
        ]

    @staticmethod
    def _bearer_token(handler, query=None):
        header = handler.headers.get("Authorization", "")
        if header.lower().startswith("bearer "):
            return header[7:].strip()
        if query is not None:
            return query.get("token", [""])[0]
        return ""

    @staticmethod
    def is_loopback_request(handler):
        """Return whether the HTTP request originates on this computer."""
        address = str(getattr(handler, "client_address", ("",))[0]).strip().lower()
        return address in {"127.0.0.1", "::1", "localhost"}

    def current_user(self, handler, query=None):
        """Return an authenticated tenant, or ``None`` for legacy token mode."""
        if not self.auth_enabled:
            # The browser UI opened on the same computer must not depend on a
            # token stored in one particular browser profile. Remote clients
            # remain protected by the configured bearer token.
            if self.is_loopback_request(handler):
                return {}
            return {} if self.check_auth(handler, query) else None
        return self.auth.authenticate(self._bearer_token(handler, query))

    def check_auth(self, handler, query=None):
        if self.auth_enabled:
            return self.current_user(handler, query) is not None
        if not self.token:
            return True
        return self._bearer_token(handler, query) == self.token

    @staticmethod
    def _tenant_id(user):
        return str((user or {}).get("id") or "")

    def history_path_for(self, user=None):
        return tenant_history_path(self.home, self._tenant_id(user))

    def upload_dir_for(self, user=None):
        return tenant_upload_dir(self.home, self._tenant_id(user))

    def send_message(self, payload, user=None):
        text = str(payload.get("text", "")).strip()
        attachments = self._save_attachments(payload.get("attachments", []), user=user)
        if not text and attachments:
            text = "Bitte analysiere die beigefügten Anlagen."
        if not text:
            raise ValueError("Text oder Anlage darf nicht leer sein.")

        request = build_chat_request(text, attachments, history_recorded=True)
        request["source"] = str(payload.get("source", "ios") or "ios")[:64]
        request["session_id"] = str(payload.get("session_id", "")).strip()
        request["session_name"] = str(payload.get("session_name", "")).strip()[:160]
        request["privacy_mode"] = str(payload.get("privacy_mode", "local")).strip() or "local"
        request["silent"] = not bool(payload.get("speak", False))
        request["allow_tts"] = bool(payload.get("speak", False))
        request["tenant_id"] = self._tenant_id(user)
        request = self.sessions.canonicalize(request, source=request["source"])
        history_path = self.history_path_for(user)

        with self._lock:
            append_chat_event(
                history_path,
                {
                    "request_id": request["request_id"],
                    "role": "user",
                    "source": request["source"],
                    "text": text,
                    "attachments": attachments,
                    "session_id": request["session_id"],
                    "session_name": request["session_name"],
                    "privacy_mode": request["privacy_mode"],
                },
            )
            enqueue_chat_request(self.core_dir, request)

        return {
            "ok": True,
            "request_id": request["request_id"],
            "accepted_at": time.time(),
            "profile": self.profile,
            "session": self.current_session(),
        }

    def send_stt(self, payload, user=None):
        text = str(payload.get("text", "")).strip()
        if not text:
            raise ValueError("STT-Text darf nicht leer sein.")
        is_final = bool(payload.get("is_final", False))
        source = str(payload.get("source") or "ios-stt").strip().lower()
        if source not in {"ios-stt", "g2-stt"}:
            source = "ios-stt"
        canonical = self.sessions.canonicalize(payload, source=source)
        event = append_external_stt_event(
            self.stt_feed_path,
            {
                "source": source,
                "text": text,
                "is_final": is_final,
                "speak": bool(payload.get("speak", False)),
                "session_id": canonical["session_id"],
                "session_name": canonical["session_name"],
                "privacy_mode": str(payload.get("privacy_mode", "local")).strip() or "local",
                "tenant_id": self._tenant_id(user),
            },
        )
        if is_final:
            append_chat_event(
                self.history_path_for(user),
                {
                    "request_id": event["event_id"],
                    "role": "user",
                    "source": source,
                    "text": text,
                    "session_id": event["session_id"],
                    "session_name": event.get("session_name", ""),
                    "privacy_mode": event["privacy_mode"],
                },
            )
        return {
            "ok": True,
            "event_id": event["event_id"],
            "accepted_at": event["timestamp"],
            "profile": self.profile,
            "session": self.current_session(),
        }

    def transcribe_audio(self, payload, user=None):
        if not isinstance(payload, dict):
            raise ValueError("Audio-Transkription erwartet ein Objekt.")
        route = str(payload.get("route") or "stt").strip().lower()
        if route not in {"none", "stt", "message"}:
            raise ValueError("Audio-Route muss none, stt oder message sein.")

        with self._lock:
            if self._audio_transcriber is None:
                config = load_config(self.config_path)
                model_name = str(config.get("stt", {}).get("model") or "small")
                self._audio_transcriber = BridgeAudioTranscriber(model_name=model_name)

        result = self._audio_transcriber.transcribe(
            payload.get("audio_base64"),
            sample_rate=payload.get("sample_rate", 16_000),
            language=payload.get("language", "de"),
            quality=payload.get("quality", "balanced"),
        )
        text = str(result.get("text") or "").strip()
        response = {"ok": True, **result, "route": route, "routed": False}
        if not text or route == "none":
            return response

        common = {
            "text": text,
            "session_id": str(payload.get("session_id") or "").strip(),
            "session_name": str(payload.get("session_name") or "").strip()[:160],
            "privacy_mode": str(payload.get("privacy_mode") or "local").strip() or "local",
            "speak": bool(payload.get("speak", False)),
        }
        if route == "message":
            routed = self.send_message({**common, "source": "g2-conversation"}, user=user)
        else:
            routed = self.send_stt(
                {**common, "source": "g2-stt", "is_final": True},
                user=user,
            )
        response.update({"routed": True, "request": routed})
        return response

    def end_session(self, payload, user=None):
        session_id = str(payload.get("session_id", "")).strip()
        session_name = str(payload.get("session_name", "")).strip()[:160]
        display_session_id = str(payload.get("display_session_id", "")).strip()
        display_session_name = str(payload.get("display_session_name", "")).strip()[:160]
        wait = bool(payload.get("wait", False) or payload.get("blocking", False))
        include_unscoped = bool(payload.get("include_unscoped", False))
        started_at = float(payload.get("started_at", 0) or 0)
        ended_at = float(payload.get("ended_at", 0) or 0)
        if not session_id:
            raise ValueError("session_id fehlt.")

        history_path = self.history_path_for(user)
        events = [
            event
            for event in load_chat_events(history_path, limit=5000)
            if (
                str(event.get("session_id") or "") == session_id
                or (include_unscoped and not str(event.get("session_id") or "").strip())
            )
            and str(event.get("role") or "") in {"user", "assistant"}
            and str(event.get("text") or "").strip()
            and (not started_at or float(event.get("timestamp", 0) or 0) >= started_at)
            and (not ended_at or float(event.get("timestamp", 0) or 0) <= ended_at)
        ]
        if not events:
            self._set_session_summary_status(session_id, "empty")
            return {
                "ok": True,
                "created": False,
                "message": "Keine Inhalte fuer diese Session gefunden.",
            }

        self._set_session_summary_status(session_id, "queued")
        transcript_path = self._write_session_transcript(session_id, session_name, events)
        if wait:
            record = self._create_session_summary_record(
                transcript_path=transcript_path,
                session_id=session_id,
                session_name=session_name,
                display_session_id=display_session_id,
                display_session_name=display_session_name,
                history_path=history_path,
                user=user,
            )
            return {
                "ok": True,
                "accepted": False,
                "created": True,
                "event": record,
                "summary": record.get("text", ""),
                "summary_path": (record.get("attachments") or [{}])[0].get("path", ""),
                "memory_id": record.get("metadata", {}).get("memory_id", ""),
            }

        job_key = f"{self._tenant_id(user)}:{session_id}"
        with self._lock:
            if job_key in self._summary_jobs:
                return {
                    "ok": True,
                    "accepted": True,
                    "created": False,
                    "job_id": job_key,
                    "message": "Session-Summary laeuft bereits im Hintergrund.",
                }
            self._summary_jobs.add(job_key)

        thread = threading.Thread(
            target=self._run_session_summary_job,
            args=(
                job_key,
                transcript_path,
                session_id,
                session_name,
                display_session_id,
                display_session_name,
                history_path,
                user,
            ),
            name=f"trinity-session-summary-{session_id[:12]}",
            daemon=True,
        )
        thread.start()
        return {
            "ok": True,
            "accepted": True,
            "created": False,
            "job_id": job_key,
            "message": "Session-Summary wird im Hintergrund erstellt.",
        }

    def close_session(self, payload, user=None):
        """Close the canonical session, queue its summary, and activate one replacement."""
        if not isinstance(payload, dict):
            raise ValueError("Session-Abschluss erwartet ein Objekt.")
        with self._session_close_lock:
            current = self.sessions.current()
            requested_id = str(payload.get("session_id") or current.id).strip()
            if requested_id != current.id:
                raise ValueError(
                    "Nur die aktuell aktive gemeinsame Session kann geschlossen werden."
                )

            manager = TrinityWorkspaceManager(str(self.home), load_config(self.config_path))
            closing = manager.get_session(current.id)
            summary = self.end_session(
                {
                    **payload,
                    "session_id": closing.id,
                    "session_name": closing.title,
                    "display_session_id": "",
                    "display_session_name": "",
                    "wait": bool(payload.get("wait", False)),
                },
                user=user,
            )
            summary_status = (
                "complete"
                if summary.get("created")
                else "queued"
                if summary.get("accepted")
                else "empty"
            )
            closed = manager.close_session(closing.id, summary_status=summary_status)
            replacement_title = str(
                payload.get("replacement_title") or payload.get("next_title") or ""
            ).strip()
            replacement = manager.create_session(
                replacement_title or None,
                workspace_id=str(
                    payload.get("workspace_id") or closing.workspace_id or INBOX_WORKSPACE_ID
                ),
                mode=str(payload.get("mode") or "chat"),
            )
            self.sessions.activate(
                replacement,
                source=str(payload.get("source") or "session-close"),
            )
            return {
                "ok": True,
                "profile": self.profile,
                "summary": summary,
                "closed_session": closed.as_dict(),
                "session": replacement.as_dict(),
                "active_session": self.current_session(),
            }

    def _set_session_summary_status(self, session_id, status):
        try:
            manager = TrinityWorkspaceManager(str(self.home), load_config(self.config_path))
            manager.update_session_summary_status(str(session_id), str(status))
        except (OSError, ValueError):
            # Legacy/unscoped sessions do not necessarily have workspace metadata.
            pass

    def _create_session_summary_record(
        self,
        *,
        transcript_path,
        session_id,
        session_name,
        history_path,
        display_session_id="",
        display_session_name="",
        user=None,
    ):
        summary_result = self._run_session_summary_agent(
            transcript_path=transcript_path,
            session_id=session_id,
            session_name=session_name,
            user=user,
        )
        summary = str(summary_result.get("summary") or "").strip()
        if not summary:
            raise RuntimeError(
                summary_result.get("search_context")
                or "Session-Summary konnte nicht erstellt werden."
            )
        if not summary_result.get("memory_id"):
            summary_result["memory_id"] = self._remember_session_summary(
                summary=summary,
                session_id=session_id,
                session_name=session_name,
                summary_path=summary_result.get("summary_path"),
                transcript_path=transcript_path,
                user=user,
            )

        raw_summary_path = str(summary_result.get("summary_path") or "").strip()
        source_summary_path = Path(raw_summary_path).resolve() if raw_summary_path else None
        summary_path = self._write_session_summary_copy(
            session_id=session_id,
            session_name=session_name,
            summary=summary,
            fallback_path=source_summary_path,
        )
        html_payload = str(summary_result.get("html_payload") or "")
        if html_payload:
            self.payload_path.write_text(html_payload, encoding="utf-8")

        attachments = []
        if summary_path and summary_path.is_file():
            attachments.append(
                {
                    "name": summary_path.name,
                    "path": str(summary_path),
                    "kind": "summary",
                    "mime": "text/markdown",
                    "size": summary_path.stat().st_size,
                }
            )

        visible_session_id = str(display_session_id or session_id)
        visible_session_name = str(display_session_name or session_name)
        record = append_chat_event(
            history_path,
            {
                "request_id": f"session-summary-{session_id}",
                "role": "assistant",
                "source": "session-summary",
                "text": summary,
                "payload_html": html_payload,
                "attachments": attachments,
                "session_id": visible_session_id,
                "session_name": visible_session_name,
                "metadata": {
                    "memory_id": summary_result.get("memory_id", ""),
                    "summary_path": str(summary_path) if summary_path else "",
                    "source_summary_path": str(source_summary_path) if source_summary_path else "",
                    "transcript_path": str(transcript_path),
                    "original_session_id": session_id,
                    "original_session_name": session_name,
                    "background": True,
                },
            },
        )
        self._set_session_summary_status(session_id, "complete")
        return record

    def _write_session_summary_copy(
        self,
        *,
        session_id,
        session_name,
        summary,
        fallback_path,
    ):
        try:
            manager = TrinityWorkspaceManager(str(self.home), load_config(self.config_path))
            session = manager.get_session(str(session_id))
            target = session.path / "summary.md"
            target.write_text(
                f"# Session-Summary – {session_name or session.title}\n\n{summary.strip()}\n",
                encoding="utf-8",
            )
            return target.resolve()
        except (OSError, ValueError):
            return fallback_path

    def _run_session_summary_job(
        self,
        job_key,
        transcript_path,
        session_id,
        session_name,
        display_session_id,
        display_session_name,
        history_path,
        user=None,
    ):
        try:
            self._create_session_summary_record(
                transcript_path=transcript_path,
                session_id=session_id,
                session_name=session_name,
                display_session_id=display_session_id,
                display_session_name=display_session_name,
                history_path=history_path,
                user=user,
            )
        except Exception as exc:  # pylint: disable=broad-except
            self._set_session_summary_status(session_id, "failed")
            append_chat_event(
                history_path,
                {
                    "request_id": f"session-summary-error-{session_id}",
                    "role": "assistant",
                    "source": "session-summary",
                    "text": f"Session-Summary konnte nicht erstellt werden: {exc}",
                    "session_id": str(display_session_id or session_id),
                    "session_name": str(display_session_name or session_name),
                    "metadata": {
                        "background": True,
                        "error": str(exc),
                        "transcript_path": str(transcript_path),
                        "original_session_id": session_id,
                        "original_session_name": session_name,
                    },
                },
            )
        finally:
            with self._lock:
                self._summary_jobs.discard(job_key)

    def get_mode(self):
        config = self._read_config()
        mode = str(config.get("system", {}).get("mode", "office") or "office")
        if mode not in {"office", "lecture", "chat"}:
            mode = "office"
        return {"ok": True, "mode": mode}

    def set_mode(self, payload):
        mode = str(payload.get("mode", "")).strip().lower()
        if mode not in {"office", "lecture", "chat"}:
            raise ValueError("Modus muss office, lecture oder chat sein.")
        with self._lock:
            config = self._read_config()
            config.setdefault("system", {})["mode"] = mode
            self.core_dir.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return {"ok": True, "mode": mode, "updated_at": time.time()}

    def get_runtime(self):
        config = load_config(self.config_path)
        system = config.get("system", {})
        return {
            "ok": True,
            "mode": str(system.get("mode", "lecture") or "lecture"),
            "microphone_enabled": bool(system.get("microphone_enabled", True)),
            "audio_capture_mode": str(system.get("audio_capture_mode", "mic_only") or "mic_only"),
            "tts_enabled": bool(system.get("tts_enabled", True)),
        }

    def canvas_status(self, max_age=2.0):
        checked_at, cached = self._canvas_status_cache
        if cached and time.monotonic() - checked_at < max_age:
            return dict(cached)
        status = CanvasManager(self.home).status(timeout=0.2)
        public_status = {
            "enabled": status["enabled"],
            "running": status["running"],
            "state": status["state"],
            "message": status["message"],
            "url": status["url"],
            "http_status": status["http_status"],
        }
        self._canvas_status_cache = (time.monotonic(), public_status)
        return dict(public_status)

    def dashboard(self, user=None):
        """Return lightweight dashboard data for Agents and Control pages."""

        config = load_config(self.config_path)
        try:
            catalog = build_agent_catalog(self.home, config)
        except Exception:
            catalog = []

        agents = [
            {
                "id": record.agent_id,
                "name": record.name,
                "tier": record.tier,
                "kind": "external" if record.tier in {"brainvault", "shared", "personal", "staging"} else "trinity",
                "kind_label": (
                    "BrainVault-Erweiterung"
                    if record.tier in {"brainvault", "shared", "personal", "staging"}
                    else "Trinity-Kernagent"
                ),
                "status": record.runtime_status,
                "quality": record.quality_status,
                "enabled": bool(record.enabled),
                "preferred_harness": record.preferred_harness,
                "description": record.description,
                "rights": ", ".join(record.allowed_tools[:5]) or "keine speziellen Rechte",
                "allowed_tools": record.allowed_tools,
                "allowed_paths": record.allowed_paths,
                "requires_approval": record.requires_approval,
                "risk_level": record.risk_level,
                "path": record.path,
                "parent_agent": record.parent_agent,
                "job_total": int(record.job_total),
                "job_open": int(record.job_open),
                "job_failed": int(record.job_failed),
            }
            for record in catalog
        ]
        try:
            manager = TrinityWorkspaceManager(str(self.home), config)
            workspaces = manager.list_workspaces()
            sessions = manager.list_sessions(limit=12)
            notes = manager.list_notes(limit=12)
        except Exception:
            workspaces, sessions, notes = [], [], []

        events = load_chat_events(self.history_path_for(user), limit=MAX_EVENTS)
        payload_events = [
            event for event in events
            if event.get("payload_html") or event.get("attachments")
        ]
        runtime = self.get_runtime()
        runtime.pop("ok", None)
        return {
            "ok": True,
            "runtime": runtime,
            "agents": {
                "total": len(agents),
                "enabled": sum(1 for item in agents if item["enabled"] or item["status"] == "active"),
                "running_jobs": sum(item["job_open"] for item in agents),
                "failed_jobs": sum(item["job_failed"] for item in agents),
                "items": agents,
            },
            "jobs": {
                "open": sum(item["job_open"] for item in agents),
                "failed": sum(item["job_failed"] for item in agents),
                "total": sum(item["job_total"] for item in agents),
                "recent": self._recent_jobs(),
            },
            "canvas": self.canvas_status(),
            "control": {
                "workspaces": len(workspaces),
                "sessions": len(sessions),
                "notes": len(notes),
                "memory_db": str(self.memory_dir / "trinity_memory.sqlite3"),
                "history_events": len(events),
                "payload_results": len(payload_events),
                "latest_session": sessions[0].title if sessions else "",
                "latest_result": str(payload_events[-1].get("text") or payload_events[-1].get("source") or "")[:140] if payload_events else "",
            },
        }

    def update_agent_display(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Agenten-Update erwartet ein Objekt.")
        agent_id = str(payload.get("id") or payload.get("agent_id") or "").strip()
        if not agent_id:
            raise ValueError("agent_id fehlt.")
        display_name = str(payload.get("display_name") or payload.get("name") or "").strip()
        if len(display_name) > 120:
            raise ValueError("Anzeigename ist zu lang.")
        with self._lock:
            config = load_config(self.config_path)
            agents = config.setdefault("agent_catalog", {}).setdefault("agents", {})
            entry = agents.setdefault(agent_id, {})
            if display_name:
                entry["display_name"] = display_name
            else:
                entry.pop("display_name", None)
            config["agent_catalog"]["agents"] = normalize_catalog_overrides(agents)
            save_config(self.config_path, config)
        return {"ok": True, "agent_id": agent_id, "display_name": display_name}

    def workspace_state(self, workspace_id=None, session_limit=80):
        manager = TrinityWorkspaceManager(str(self.home), load_config(self.config_path))
        workspaces = manager.list_workspaces()
        selected_workspace = str(workspace_id or "").strip()
        if selected_workspace:
            manager.get_workspace(selected_workspace)
        else:
            selected_workspace = INBOX_WORKSPACE_ID
        sessions = manager.list_sessions(limit=max(1, min(int(session_limit or 80), 250)))
        notes = manager.list_notes(limit=80)
        return {
            "ok": True,
            "inbox": INBOX_WORKSPACE_ID,
            "selected_workspace_id": selected_workspace,
            "active_session": self.current_session(),
            "profile": self.profile,
            "workspaces": [item.as_dict() for item in workspaces],
            "sessions": [item.as_dict() for item in sessions],
            "notes": [item.as_dict() for item in notes],
        }

    def create_workspace(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Arbeitsraum-Erstellung erwartet ein Objekt.")
        title = str(payload.get("title") or payload.get("name") or "").strip()
        if not title:
            raise ValueError("Arbeitsraum braucht einen Namen.")
        manager = TrinityWorkspaceManager(str(self.home), load_config(self.config_path))
        workspace = manager.create_workspace(
            title,
            kind=str(payload.get("kind") or "custom"),
            pinned=bool(payload.get("pinned", False)),
        )
        return {"ok": True, "workspace": workspace.as_dict()}

    def update_workspace(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Arbeitsraum-Update erwartet ein Objekt.")
        workspace_id = str(payload.get("workspace_id") or payload.get("id") or "").strip()
        if not workspace_id:
            raise ValueError("workspace_id fehlt.")
        manager = TrinityWorkspaceManager(str(self.home), load_config(self.config_path))
        workspace = manager.update_workspace(
            workspace_id,
            title=payload.get("title") if "title" in payload else None,
            pinned=bool(payload.get("pinned")) if "pinned" in payload else None,
            status=payload.get("status") if "status" in payload else None,
        )
        return {"ok": True, "workspace": workspace.as_dict()}

    def create_session(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Session-Erstellung erwartet ein Objekt.")
        title = str(payload.get("title") or payload.get("name") or "").strip()
        workspace_id = str(payload.get("workspace_id") or INBOX_WORKSPACE_ID).strip() or INBOX_WORKSPACE_ID
        manager = TrinityWorkspaceManager(str(self.home), load_config(self.config_path))
        session = manager.create_session(
            title or None,
            workspace_id=workspace_id,
            mode=str(payload.get("mode") or "lecture"),
        )
        self.sessions = UnifiedSessionStore(self.home, load_config(self.config_path))
        self.sessions.activate(session, source=str(payload.get("source") or "client"))
        return {"ok": True, "session": session.as_dict(), "active_session": self.current_session()}

    def activate_session(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Session-Aktivierung erwartet ein Objekt.")
        session_id = str(payload.get("session_id") or payload.get("id") or "").strip()
        if not session_id:
            raise ValueError("session_id fehlt.")
        session = self.sessions.activate(session_id, source=str(payload.get("source") or "client"))
        return {"ok": True, "session": session.as_dict(), "active_session": self.current_session()}

    def update_session(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Session-Update erwartet ein Objekt.")
        session_id = str(payload.get("session_id") or payload.get("id") or "").strip()
        if not session_id:
            raise ValueError("session_id fehlt.")
        manager = TrinityWorkspaceManager(str(self.home), load_config(self.config_path))
        session = manager.update_session(
            session_id,
            title=payload.get("title") if "title" in payload else None,
            status=payload.get("status") if "status" in payload else None,
            summary_status=payload.get("summary_status") if "summary_status" in payload else None,
            pinned=bool(payload.get("pinned")) if "pinned" in payload else None,
            workspace_id=payload.get("workspace_id") if "workspace_id" in payload else None,
            mode=payload.get("mode") if "mode" in payload else None,
        )
        return {"ok": True, "session": session.as_dict()}

    def delete_session(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Session-Loeschen erwartet ein Objekt.")
        session_id = str(payload.get("session_id") or payload.get("id") or "").strip()
        if not session_id:
            raise ValueError("session_id fehlt.")
        manager = TrinityWorkspaceManager(str(self.home), load_config(self.config_path))
        was_active = session_id == self.current_session()["id"]
        delete_session_summary(self.home, session_id)
        result = manager.delete_session(session_id, archive=bool(payload.get("archive", False)))
        if not bool(payload.get("archive", False)):
            result["memory"] = MemoryStore(
                self.memory_dir / "trinity_memory.sqlite3"
            ).delete_session(session_id)
        if was_active:
            try:
                self.sessions.pointer_path.unlink()
            except OSError:
                pass
            replacement = self.sessions.current()
            result["active_session"] = self.current_session()
            result["replacement_session_id"] = replacement.id
        return {"ok": True, **result}

    def delete_session_summary_record(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Summary-Loeschen erwartet ein Objekt.")
        session_id = str(payload.get("session_id") or payload.get("id") or "").strip()
        if not session_id:
            raise ValueError("session_id fehlt.")
        return {"ok": True, **delete_session_summary(self.home, session_id)}

    def list_memory_records(self, limit=50):
        store = MemoryStore(self.memory_dir / "trinity_memory.sqlite3")
        return {"ok": True, "memories": store.list_memories(limit=max(1, min(int(limit), 200)))}

    def memory_graph(self, limit=90, user=None):
        tenant_id = self._tenant_id(user)
        database_path = (
            tenant_memory_db_path(self.home, tenant_id)
            if tenant_id
            else self.memory_dir / "trinity_memory.sqlite3"
        )
        graph = MemoryStore(database_path).graph_data(
            limit=max(1, min(int(limit), 150))
        )
        return {"ok": True, "profile": self.profile, **graph}

    def delete_memory_record(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Memory-Loeschen erwartet ein Objekt.")
        memory_id = str(payload.get("memory_id") or payload.get("id") or "").strip()
        if not memory_id:
            raise ValueError("memory_id fehlt.")
        deleted = MemoryStore(self.memory_dir / "trinity_memory.sqlite3").delete_memory(memory_id)
        return {"ok": True, "memory_id": memory_id, "deleted": deleted}

    def delete_event(self, payload, user=None):
        if not isinstance(payload, dict):
            raise ValueError("Nachrichten-Loeschen erwartet ein Objekt.")
        event_id = str(payload.get("event_id") or payload.get("id") or "").strip()
        if not event_id:
            raise ValueError("event_id fehlt.")
        removed = remove_chat_event(self.history_path_for(user), event_id)
        if not removed:
            raise ValueError("Nachricht wurde nicht gefunden.")
        return {"ok": True, "event_id": event_id, "deleted": True}

    def import_offline_events(self, payload, user=None):
        if not isinstance(payload, dict):
            raise ValueError("Offline-Sync erwartet ein Objekt.")
        incoming = payload.get("events")
        if not isinstance(incoming, list):
            raise ValueError("events fehlt.")

        history_path = self.history_path_for(user)
        existing_ids = {
            str(event.get("client_event_id") or event.get("event_id") or "")
            for event in load_chat_events(history_path, limit=5000)
        }
        imported = []
        for event in incoming[:200]:
            if not isinstance(event, dict):
                continue
            client_event_id = str(event.get("event_id") or event.get("eventId") or "").strip()
            if client_event_id and client_event_id in existing_ids:
                continue
            role = str(event.get("role") or "").strip().lower()
            if role not in {"user", "assistant", "transcript"}:
                continue
            text = str(event.get("text") or "").strip()
            if not text:
                continue
            source = str(event.get("source") or "companion-offline").strip()[:80]
            if source not in {
                "companion-offline",
                "companion-offline-stt",
                "apple-foundation-offline",
            }:
                source = "companion-offline"
            supplied_session_id = str(event.get("session_id") or event.get("sessionId") or "").strip()
            canonical = self.sessions.canonicalize(event, source=source)
            session_id = canonical["session_id"]
            session_name = canonical["session_name"]
            record = append_chat_event(
                history_path,
                {
                    "role": role,
                    "source": source,
                    "text": text,
                    "session_id": session_id,
                    "session_name": session_name,
                    "client_event_id": client_event_id or None,
                    "offline_synced": True,
                    "original_session_id": supplied_session_id or None,
                    "profile": self.profile,
                },
            )
            imported.append(record)
            if client_event_id:
                existing_ids.add(client_event_id)
        return {"ok": True, "imported": len(imported), "events": imported}

    def _recent_jobs(self, limit=8):
        db_path = self.memory_dir / "jobs.sqlite3"
        if not db_path.is_file():
            return []
        try:
            with sqlite3.connect(db_path) as conn:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
                select_columns = [
                    name for name in ("job_id", "route", "status", "created_at", "updated_at", "title")
                    if name in columns
                ]
                if not select_columns:
                    return []
                order = "updated_at" if "updated_at" in columns else ("created_at" if "created_at" in columns else "rowid")
                rows = conn.execute(
                    f"SELECT {', '.join(select_columns)} FROM jobs ORDER BY {order} DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
        except sqlite3.Error:
            return []
        return [dict(zip(select_columns, row)) for row in rows]

    def set_runtime(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Laufzeitwerte muessen ein Objekt sein.")
        with self._lock:
            config = load_config(self.config_path)
            system = config.setdefault("system", {})
            if "mode" in payload:
                mode = str(payload["mode"] or "").strip().lower()
                if mode not in {"office", "lecture", "chat"}:
                    raise ValueError("Modus muss office, lecture oder chat sein.")
                system["mode"] = mode
            for key in ("microphone_enabled", "tts_enabled"):
                if key in payload:
                    system[key] = bool(payload[key])
            if "audio_capture_mode" in payload:
                mode = str(payload["audio_capture_mode"] or "").strip().lower()
                if mode not in {"mic_only", "mic_and_system"}:
                    raise ValueError("Audioquelle muss mic_only oder mic_and_system sein.")
                system["audio_capture_mode"] = mode
            save_config(self.config_path, config)
        result = self.get_runtime()
        result["updated_at"] = time.time()
        return result

    def can_manage_settings(self, handler, user):
        """Settings are local-only without a token and admin-only with accounts."""
        if self.auth_enabled:
            return bool(user and user.get("role") == "admin")
        if self.token:
            return True
        return self.is_loopback_request(handler)

    def can_manage_workspaces(self, handler, user):
        """Workspace/session changes are user actions, not privileged settings."""
        return user is not None

    def get_web_settings(self):
        return {
            "ok": True,
            "config": load_config(self.config_path),
            "files": {
                "soul": self._read_text_file(self.core_dir / "Soul.md"),
                "user": self._read_text_file(self.core_dir / "User.md"),
            },
        }

    def get_prompts(self):
        config = self._read_config()
        persona = config.get("persona", {})
        if not isinstance(persona, dict):
            persona = {}
        return {
            "ok": True,
            "soul": self._read_text_file(self.core_dir / "Soul.md"),
            "user": self._read_text_file(self.core_dir / "User.md"),
            "agent_name": str(persona.get("agent_name") or "Trinity"),
            "trigger_variants": list(persona.get("trigger_variants") or []),
        }

    def save_prompts(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Prompts erwarten ein Objekt.")
        self.core_dir.mkdir(parents=True, exist_ok=True)
        for name, value in {"Soul.md": payload.get("soul"), "User.md": payload.get("user")}.items():
            if value is None:
                continue
            encoded = str(value).encode("utf-8")
            if len(encoded) > MAX_SETTINGS_TEXT_BYTES:
                raise ValueError(f"{name} ist zu gross.")
            (self.core_dir / name).write_text(str(value), encoding="utf-8")
        return self.get_prompts()

    def save_web_settings(self, payload):
        if not isinstance(payload, dict) or not isinstance(payload.get("config"), dict):
            raise ValueError("Einstellungen muessen ein Konfigurationsobjekt enthalten.")
        incoming = payload["config"]
        config = load_config(self.config_path)
        for section in SETTINGS_SECTIONS:
            value = incoming.get(section)
            if isinstance(value, dict):
                if section == "harness_routing":
                    config[section] = value
                else:
                    self._merge_settings_section(config.setdefault(section, {}), value)

        self.core_dir.mkdir(parents=True, exist_ok=True)
        for name, value in {"Soul.md": payload.get("soul"), "User.md": payload.get("user")}.items():
            if value is None:
                continue
            encoded = str(value).encode("utf-8")
            if len(encoded) > MAX_SETTINGS_TEXT_BYTES:
                raise ValueError(f"{name} ist zu gross.")
            (self.core_dir / name).write_text(str(value), encoding="utf-8")

        save_config(self.config_path, config)
        return self.get_web_settings()

    def test_harness(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Harness-Test erwartet ein Objekt.")
        harness_id = str(payload.get("harness") or "").strip().lower()
        if harness_id not in {"trinity", "codex", "pi", "opencode"}:
            raise ValueError("Unbekanntes Harness.")

        if harness_id == "trinity":
            return {
                "ok": True,
                "harness": "trinity",
                "found": True,
                "message": "Trinity ist die integrierte Control Plane.",
            }

        config = load_config(self.config_path)
        raw_executable = str(
            payload.get("executable")
            or config.get(harness_id, {}).get("executable")
            or harness_id
        ).strip()
        resolved = self._resolve_harness_executable(harness_id, raw_executable)
        label = {
            "trinity": "Trinity",
            "codex": "Codex",
            "pi": "Pi",
            "opencode": "OpenCode",
        }[harness_id]
        if not resolved:
            return {
                "ok": False,
                "harness": harness_id,
                "found": False,
                "message": f"{label} wurde nicht gefunden.",
            }

        if harness_id == "pi":
            return {
                "ok": True,
                "harness": harness_id,
                "found": True,
                "path": resolved,
                "message": "Pi-Wrapper gefunden. Kein Testauftrag wurde ausgefuehrt.",
            }

        command = [resolved, "--version"]
        use_shell = os.name == "nt" and str(resolved).casefold().endswith((".cmd", ".bat"))
        run_command = subprocess.list2cmdline(command) if use_shell else command
        try:
            completed = subprocess.run(
                run_command,
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
                shell=use_shell,
            )
        except Exception as exc:  # pylint: disable=broad-except
            return {
                "ok": False,
                "harness": harness_id,
                "found": True,
                "path": resolved,
                "message": str(exc),
            }

        output = (completed.stdout or completed.stderr or "").strip()
        return {
            "ok": completed.returncode == 0,
            "harness": harness_id,
            "found": True,
            "path": resolved,
            "returncode": completed.returncode,
            "output": output[:1200],
            "message": (
                f"{label} ist erreichbar."
                if completed.returncode == 0
                else f"{label} antwortete mit Code {completed.returncode}."
            ),
        }

    def _save_attachments(self, attachments, user=None):
        saved = []
        if not isinstance(attachments, list):
            raise ValueError("attachments muss eine Liste sein.")
        upload_dir = self.upload_dir_for(user)
        upload_dir.mkdir(parents=True, exist_ok=True)
        for item in attachments:
            if not isinstance(item, dict):
                continue
            raw_name = str(item.get("name") or "anlage").strip()
            name = Path(raw_name).name or "anlage"
            mime = str(item.get("mime") or mimetypes.guess_type(name)[0] or "")
            data_b64 = str(item.get("data_base64") or "")
            if not data_b64:
                continue
            try:
                data = base64.b64decode(data_b64, validate=True)
            except ValueError as exc:
                raise ValueError(f"Anlage `{name}` ist nicht gültig base64-kodiert.") from exc
            if len(data) > MAX_ATTACHMENT_BYTES:
                raise ValueError(
                    f"Anlage `{name}` ist größer als {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB."
                )
            target = upload_dir / f"{uuid.uuid4().hex}_{name}"
            target.write_bytes(data)
            kind = item.get("kind") or attachment_kind(target)
            if kind is None:
                target.unlink(missing_ok=True)
                raise ValueError(f"Nicht unterstützte Anlage: {name}")
            saved.append(
                {
                    "name": name,
                    "path": str(target),
                    "kind": kind,
                    "mime": mime or mimetypes.guess_type(name)[0] or "application/octet-stream",
                    "size": len(data),
                }
            )
        return saved

    def _write_session_transcript(self, session_id, session_name, events):
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", session_id).strip("._") or uuid.uuid4().hex
        transcript_dir = self.memory_dir / "session_transcripts"
        transcript_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = transcript_dir / f"Session_{safe_id}.md"
        lines = [
            f"# Trinity Session {session_name or session_id}",
            "",
            f"- Session-ID: `{session_id}`",
            f"- Erstellt: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        for event in events:
            timestamp = float(event.get("timestamp", 0) or 0)
            stamp = time.strftime("%H:%M:%S", time.localtime(timestamp)) if timestamp else "--:--:--"
            role = str(event.get("role") or "event")
            source = str(event.get("source") or "unknown")
            text = str(event.get("text") or "").strip()
            lines.append(f"[{stamp}] {role} ({source}): {text}")
        transcript_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return transcript_path

    def _run_session_summary_agent(self, transcript_path, session_id, session_name, user=None):
        agent_path = self.home / "agents" / "session_summarizer_agent" / "script.py"
        if not agent_path.is_file():
            raise RuntimeError("Session-Summarizer-Agent nicht gefunden.")
        spec = importlib.util.spec_from_file_location("trinity_session_summarizer_agent", agent_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Session-Summarizer-Agent konnte nicht geladen werden.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        from brain import TrinityBrain

        tenant_id = self._tenant_id(user)
        result = module.execute(
            "session abschließen",
            context={
                "brain": TrinityBrain(),
                "transcript_file": str(transcript_path),
                "session_id": session_id,
                "session_name": session_name,
                "tenant_id": tenant_id,
            },
        )
        if not isinstance(result, dict):
            raise RuntimeError("Session-Summarizer-Agent lieferte kein Ergebnis.")
        if result.get("memory_id"):
            return result

        summary = str(result.get("summary") or "").strip()
        if summary:
            result["memory_id"] = self._remember_session_summary(
                summary=summary,
                session_id=session_id,
                session_name=session_name,
                summary_path=result.get("summary_path"),
                transcript_path=transcript_path,
                user=user,
            )
        return result

    def _remember_session_summary(self, *, summary, session_id, session_name, summary_path, transcript_path, user=None):
        tenant_id = self._tenant_id(user)
        store = MemoryStore(
            str(tenant_memory_db_path(self.home, tenant_id))
            if tenant_id
            else str(self.memory_dir / "trinity_memory.sqlite3")
        )
        store.ensure_session(session_id, session_name or "Trinity Session")
        return store.remember(
            summary,
            tags=["session", "summary", "trinity"],
            kind="session-summary",
            source="session-summary-agent",
            session_id=session_id,
            weight=0.82,
            baked=True,
            metadata={
                "summary_path": str(summary_path or ""),
                "transcript_file": str(transcript_path),
                "session_name": session_name,
            },
        )

    def events_since(
        self,
        after=0.0,
        limit=MAX_EVENTS,
        user=None,
        access_token="",
        include_payload_html=True,
        session_id="",
    ):
        events = []
        target_session_id = str(session_id or "").strip()
        for event in load_chat_events(
            self.history_path_for(user),
            limit=5000 if target_session_id else max(limit * 3, MAX_EVENTS),
        ):
            timestamp = float(event.get("timestamp", 0) or 0)
            if timestamp <= after:
                continue
            event_session_id = str(event.get("session_id") or "").strip()
            if target_session_id and event_session_id != target_session_id:
                continue
            cleaned = dict(event)
            payload_html = str(cleaned.get("payload_html") or "")
            if payload_html and not cleaned.get("attachments"):
                cleaned["attachments"] = self.attachments_from_payload(
                    payload_html,
                    user=user,
                )
            if cleaned.get("payload_html") and include_payload_html:
                cleaned["payload_html"] = self.rewrite_html(
                    cleaned["payload_html"], user=user, access_token=access_token
                )
            elif not include_payload_html:
                # Mobile clients load the current payload independently. Avoid
                # repeatedly sending old, potentially very large sandbox HTML.
                cleaned["has_payload"] = bool(cleaned.get("payload_html"))
                cleaned.pop("payload_html", None)
            if cleaned.get("attachments"):
                cleaned["attachments"] = self.rewrite_attachments(
                    cleaned["attachments"], user=user, access_token=access_token
                )
            events.append(cleaned)
        return events[-limit:]

    def attachments_from_payload(self, html, user=None):
        """Expose local image/audio/video payload files as regular media attachments."""
        attachments = []
        seen = set()
        pattern = re.compile(
            r"<(img|audio|video)\b[^>]*?\bsrc\s*=\s*(['\"])([^'\"]+)\2",
            re.IGNORECASE,
        )
        for match in pattern.finditer(str(html or "")):
            tag = match.group(1).lower()
            raw_path = unescape(match.group(3))
            try:
                media_path = self.media_path_from_query(raw_path, user=user)
            except (OSError, PermissionError, ValueError):
                continue
            key = str(media_path)
            if key in seen:
                continue
            seen.add(key)
            mime = mimetypes.guess_type(media_path.name)[0] or {
                "img": "image/png",
                "audio": "audio/mpeg",
                "video": "video/mp4",
            }[tag]
            attachments.append(
                {
                    "name": media_path.name,
                    "path": key,
                    "kind": attachment_kind(media_path) or tag,
                    "mime": mime,
                    "size": media_path.stat().st_size,
                }
            )
        return attachments

    def latest_payload(self, user=None, access_token="", after=0.0):
        if user:
            for event in reversed(load_chat_events(self.history_path_for(user), limit=MAX_EVENTS * 4)):
                html = str(event.get("payload_html") or "")
                if html:
                    timestamp = float(event.get("timestamp", 0) or 0)
                    if timestamp <= after:
                        return {"html": "", "timestamp": timestamp}
                    return {
                        "html": self.rewrite_html(html, user=user, access_token=access_token),
                        "timestamp": timestamp,
                    }
            return {"html": "", "timestamp": 0.0}
        timestamp = self._mtime(self.payload_path)
        if timestamp <= after:
            return {"html": "", "timestamp": timestamp}
        try:
            html = self.payload_path.read_text(encoding="utf-8")
        except OSError:
            html = ""
        return {
            "html": self.rewrite_html(html, user=user, access_token=access_token),
            "timestamp": timestamp,
        }

    def latest_bubble(self):
        try:
            html = self.bubble_payload_path.read_text(encoding="utf-8")
        except OSError:
            html = ""
        color = self._bubble_color()
        title = {
            "red": "Kritischer Hinweis",
            "yellow": "Hinweis",
            "blue": "Übungsaufgabe",
            "green": "Info",
        }.get(color, "Heartbeat")
        headings = re.findall(r"<h[12][^>]*>(.*?)</h[12]>", html, re.IGNORECASE | re.DOTALL)
        if headings:
            parsed_title = re.sub(r"<[^>]+>", " ", unescape(headings[-1]))
            parsed_title = re.sub(r"\s+", " ", parsed_title).strip()
            if parsed_title:
                title = parsed_title[:120]
        markers = list(re.finditer(r"<!--\s*KEEP_OPEN\s*-->", html, re.IGNORECASE))
        detail_html = html[markers[-1].start():] if markers else html
        return {
            "html": self.rewrite_html(html),
            "detail_html": self.rewrite_html(detail_html),
            "timestamp": self._mtime(self.bubble_payload_path),
            "color": color,
            "title": title,
        }

    def media_path_from_query(self, raw_path, user=None):
        if not raw_path:
            raise ValueError("Kein Medienpfad angegeben.")
        value = _local_path_value(raw_path)
        path = Path(value).expanduser().resolve()
        for root in self.media_roots:
            if _is_relative_to(path, root):
                if path.is_file():
                    if user and not self._user_can_access_media(path, user):
                        raise PermissionError("Medium gehört nicht zu diesem Trinity-Account.")
                    return path
                raise FileNotFoundError(path)
        raise PermissionError("Medienpfad ist nicht freigegeben.")

    def rewrite_html(self, html, user=None, access_token=""):
        if not html:
            return ""

        def replace(match):
            quote_char = match.group(1)
            url = match.group(2)
            try:
                path = self.media_path_from_query(url, user=user)
            except (OSError, PermissionError, ValueError):
                return match.group(0)
            return f"{quote_char}{self.media_url(path, access_token=access_token)}{quote_char}"

        return re.sub(r"(['\"])(file://[^'\"]+)\1", replace, html)

    def media_url(self, path, access_token=""):
        url = f"/media?path={quote(str(path), safe='')}"
        if access_token:
            url += f"&token={quote(access_token, safe='')}"
        elif self.token:
            url += f"&token={quote(self.token, safe='')}"
        return url

    def rewrite_attachments(self, attachments, user=None, access_token=""):
        if not isinstance(attachments, list):
            return []
        rewritten = []
        for item in attachments:
            if not isinstance(item, dict):
                continue
            cleaned = {key: value for key, value in item.items() if key != "path"}
            raw_path = str(item.get("path") or "")
            if raw_path:
                try:
                    media_path = self.media_path_from_query(raw_path, user=user)
                    cleaned["media_url"] = self.media_url(media_path, access_token=access_token)
                except (OSError, PermissionError, ValueError):
                    pass
            rewritten.append(cleaned)
        return rewritten

    def _user_can_access_media(self, path, user):
        """Only serve a server user's uploads or files referenced by their history."""
        path = Path(path).resolve()
        if _is_relative_to(path, self.upload_dir_for(user)):
            return True
        for event in load_chat_events(self.history_path_for(user), limit=MAX_EVENTS * 8):
            for item in event.get("attachments", []):
                if str(item.get("path") or "") == str(path):
                    return True
            payload_html = str(event.get("payload_html") or "")
            if str(path) in payload_html or path.as_uri() in payload_html:
                return True
        return False

    @staticmethod
    def _mtime(path):
        try:
            return Path(path).stat().st_mtime
        except OSError:
            return 0.0

    def _bubble_color(self):
        try:
            state = self.state_path.read_text(encoding="utf-8").strip().lower()
        except OSError:
            state = ""
        if state.startswith("bubble_"):
            color = state.split("_", 1)[1]
            if color in {"red", "yellow", "blue", "green"}:
                return color
        return "blue"

    def _read_config(self):
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _merge_settings_section(target, incoming):
        for key, value in incoming.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                TrinityBridge._merge_settings_section(target[key], value)
            else:
                target[key] = value

    @staticmethod
    def _resolve_harness_executable(harness_id, raw_value):
        value = os.path.expandvars(os.path.expanduser(str(raw_value or harness_id).strip()))
        if os.path.dirname(value):
            path = os.path.abspath(value)
            return path if os.path.isfile(path) else ""
        finders = {
            "codex": find_codex_executable,
            "pi": find_pi_executable,
            "opencode": find_opencode_executable,
        }
        if value.casefold() in {harness_id, f"{harness_id}.exe", f"{harness_id}.cmd"}:
            finder = finders.get(harness_id)
            return finder() if finder else ""
        return shutil.which(value) or ""

    @staticmethod
    def _read_text_file(path):
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""


def make_handler(bridge):
    class Handler(BaseHTTPRequestHandler):
        server_version = "TrinityBridge/0.1"

        def log_message(self, fmt, *args):
            try:
                message = fmt % args
                if _should_log_bridge_request(self.command, self.path, message):
                    print(f"[bridge] {self.address_string()} - {message}")
            except (BrokenPipeError, OSError):
                # A detached desktop launcher can outlive its original stdout.
                # Logging must never prevent an otherwise valid HTTP response.
                pass

        def do_OPTIONS(self):  # noqa: N802
            _json_response(self, 200, {"ok": True})

        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path in {"/", "/web"}:
                _html_response(self, 200, render_web_ui(auth_enabled=bridge.auth_enabled))
                return
            if parsed.path == "/auth/status":
                _json_response(
                    self,
                    200,
                    bridge.auth.status() if bridge.auth_enabled else {"ok": True, "enabled": False},
                )
                return
            user = bridge.current_user(self, query=query if parsed.path == "/media" else None)
            if user is None:
                _json_response(self, 401, {"ok": False, "error": "unauthorized"})
                return
            try:
                bridge.validate_client_profile(self.headers.get("X-Trinity-Profile", ""))
                if parsed.path == "/health":
                    _json_response(
                        self,
                        200,
                        {
                            "ok": True,
                            "name": "Trinity Bridge",
                            "time": time.time(),
                            "history": bridge.history_path_for(user).exists(),
                            "user": user or None,
                            **bridge.instance_state(),
                        },
                    )
                elif parsed.path == "/events":
                    after = float(query.get("after", ["0"])[0] or 0)
                    try:
                        limit = int(query.get("limit", [str(MAX_EVENTS)])[0] or MAX_EVENTS)
                    except (TypeError, ValueError):
                        limit = MAX_EVENTS
                    limit = max(1, min(limit, MAX_EVENTS))
                    include_payload_html = str(
                        query.get("include_payload_html", ["1"])[0]
                    ).strip().lower() not in {"0", "false", "no"}
                    _json_response(
                        self,
                        200,
                        {
                            "ok": True,
                            "events": bridge.events_since(
                                after,
                                limit=limit,
                                user=user,
                                access_token=bridge._bearer_token(self, query),
                                include_payload_html=include_payload_html,
                                session_id=bridge.current_session()["id"],
                            ),
                            **bridge.instance_state(),
                        },
                    )
                elif parsed.path == "/session/current":
                    _json_response(self, 200, {"ok": True, **bridge.instance_state()})
                elif parsed.path == "/workspaces":
                    try:
                        session_limit = int(query.get("session_limit", ["80"])[0] or 80)
                    except (TypeError, ValueError):
                        session_limit = 80
                    _json_response(
                        self,
                        200,
                        bridge.workspace_state(
                            workspace_id=query.get("workspace_id", [""])[0],
                            session_limit=session_limit,
                        ),
                    )
                elif parsed.path == "/payload":
                    after = float(query.get("after", ["0"])[0] or 0)
                    _json_response(
                        self,
                        200,
                        {
                            "ok": True,
                            **bridge.latest_payload(
                                user=user,
                                access_token=bridge._bearer_token(self, query),
                                after=after,
                            ),
                        },
                    )
                elif parsed.path == "/bubble":
                    _json_response(self, 200, {"ok": True, **bridge.latest_bubble()})
                elif parsed.path == "/mode":
                    _json_response(self, 200, bridge.get_mode())
                elif parsed.path == "/runtime":
                    _json_response(self, 200, bridge.get_runtime())
                elif parsed.path == "/dashboard":
                    _json_response(self, 200, bridge.dashboard(user=user))
                elif parsed.path == "/workbench/catalog":
                    config = load_config(bridge.config_path)
                    if not config.get("workbench", {}).get("enabled", True):
                        raise PermissionError("Die Trinity-Werkstatt ist deaktiviert.")
                    _json_response(
                        self,
                        200,
                        bridge.workbench.catalog(config, bridge.profile),
                    )
                elif parsed.path == "/workbench/job":
                    job_id = str(query.get("job_id", [""])[0] or "").strip()
                    if not job_id:
                        raise ValueError("Eine Job-ID wird benötigt.")
                    _json_response(
                        self,
                        200,
                        {"ok": True, "job": bridge.workbench.public_job(job_id)},
                    )
                elif parsed.path == "/prompts":
                    if not bridge.can_manage_settings(self, user):
                        raise PermissionError(
                            "Prompts sind nur lokal oder fuer Administratoren verfuegbar."
                        )
                    _json_response(self, 200, bridge.get_prompts())
                elif parsed.path == "/settings":
                    if not bridge.can_manage_settings(self, user):
                        raise PermissionError(
                            "Einstellungen sind nur lokal oder fuer Administratoren verfuegbar."
                        )
                    _json_response(self, 200, bridge.get_web_settings())
                elif parsed.path == "/memory":
                    if not bridge.can_manage_settings(self, user):
                        raise PermissionError(
                            "Memory ist nur lokal oder fuer Administratoren verfuegbar."
                        )
                    limit = int(query.get("limit", ["50"])[0] or 50)
                    _json_response(self, 200, bridge.list_memory_records(limit))
                elif parsed.path == "/memory/graph":
                    if not bridge.can_manage_settings(self, user):
                        raise PermissionError(
                            "Memory-Graph ist nur lokal oder fuer Administratoren verfuegbar."
                        )
                    limit = int(query.get("limit", ["90"])[0] or 90)
                    _json_response(self, 200, bridge.memory_graph(limit, user=user))
                elif parsed.path == "/media":
                    path = bridge.media_path_from_query(
                        query.get("path", [""])[0], user=user
                    )
                    data = path.read_bytes()
                    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    _json_response(self, 404, {"ok": False, "error": "not found"})
            except PermissionError as exc:
                _json_response(self, 403, {"ok": False, "error": str(exc)})
            except Exception as exc:  # pylint: disable=broad-except
                _json_response(self, 400, {"ok": False, "error": str(exc)})

        def do_POST(self):  # noqa: N802
            parsed = urlparse(self.path)
            try:
                if bridge.auth_enabled and parsed.path == "/auth/login":
                    payload = _read_json(self)
                    _json_response(
                        self,
                        200,
                        {
                            "ok": True,
                            **bridge.auth.login(payload.get("username"), payload.get("password")),
                        },
                    )
                    return
                if bridge.auth_enabled and parsed.path == "/auth/register":
                    payload = _read_json(self)
                    _json_response(
                        self,
                        201,
                        {
                            "ok": True,
                            **bridge.auth.register_first_admin(
                                payload.get("username"), payload.get("password")
                            ),
                        },
                    )
                    return
            except PermissionError as exc:
                _json_response(self, 403, {"ok": False, "error": str(exc)})
                return
            except (ValueError, KeyError) as exc:
                _json_response(self, 400, {"ok": False, "error": str(exc)})
                return

            user = bridge.current_user(self)
            if user is None:
                _json_response(self, 401, {"ok": False, "error": "unauthorized"})
                return
            try:
                bridge.validate_client_profile(self.headers.get("X-Trinity-Profile", ""))
                if parsed.path == "/message":
                    _json_response(self, 200, bridge.send_message(_read_json(self), user=user))
                elif parsed.path == "/workbench/run":
                    config = load_config(bridge.config_path)
                    if not config.get("workbench", {}).get("enabled", True):
                        raise PermissionError("Die Trinity-Werkstatt ist deaktiviert.")
                    _json_response(
                        self,
                        202,
                        bridge.workbench.submit(
                            _read_json(self), config, bridge.profile
                        ),
                    )
                elif parsed.path == "/stt":
                    _json_response(self, 200, bridge.send_stt(_read_json(self), user=user))
                elif parsed.path == "/audio/transcribe":
                    _json_response(self, 200, bridge.transcribe_audio(_read_json(self), user=user))
                elif parsed.path == "/session/end":
                    _json_response(self, 200, bridge.end_session(_read_json(self), user=user))
                elif parsed.path == "/session/close":
                    if not bridge.can_manage_workspaces(self, user):
                        raise PermissionError(
                            "Sessions schliessen ist nur fuer angemeldete oder lokale Clients verfuegbar."
                        )
                    _json_response(self, 200, bridge.close_session(_read_json(self), user=user))
                elif parsed.path == "/workspace/create":
                    if not bridge.can_manage_workspaces(self, user):
                        raise PermissionError(
                            "Arbeitsraeume erstellen ist nur fuer angemeldete oder lokale Clients verfuegbar."
                        )
                    _json_response(self, 200, bridge.create_workspace(_read_json(self)))
                elif parsed.path == "/workspace/update":
                    if not bridge.can_manage_workspaces(self, user):
                        raise PermissionError(
                            "Arbeitsraeume aendern ist nur fuer angemeldete oder lokale Clients verfuegbar."
                        )
                    _json_response(self, 200, bridge.update_workspace(_read_json(self)))
                elif parsed.path == "/session/create":
                    if not bridge.can_manage_workspaces(self, user):
                        raise PermissionError(
                            "Sessions erstellen ist nur fuer angemeldete oder lokale Clients verfuegbar."
                        )
                    _json_response(self, 200, bridge.create_session(_read_json(self)))
                elif parsed.path == "/session/update":
                    if not bridge.can_manage_workspaces(self, user):
                        raise PermissionError(
                            "Sessions aendern ist nur fuer angemeldete oder lokale Clients verfuegbar."
                        )
                    _json_response(self, 200, bridge.update_session(_read_json(self)))
                elif parsed.path == "/session/activate":
                    if not bridge.can_manage_workspaces(self, user):
                        raise PermissionError(
                            "Sessions aktivieren ist nur fuer angemeldete oder lokale Clients verfuegbar."
                        )
                    _json_response(self, 200, bridge.activate_session(_read_json(self)))
                elif parsed.path == "/session/delete":
                    if not bridge.can_manage_workspaces(self, user):
                        raise PermissionError(
                            "Sessions loeschen ist nur fuer angemeldete oder lokale Clients verfuegbar."
                        )
                    _json_response(self, 200, bridge.delete_session(_read_json(self)))
                elif parsed.path == "/session/delete-summary":
                    if not bridge.can_manage_workspaces(self, user):
                        raise PermissionError(
                            "Summaries loeschen ist nur fuer angemeldete oder lokale Clients verfuegbar."
                        )
                    _json_response(
                        self,
                        200,
                        bridge.delete_session_summary_record(_read_json(self)),
                    )
                elif parsed.path == "/memory/delete":
                    if not bridge.can_manage_settings(self, user):
                        raise PermissionError(
                            "Memory ist nur lokal oder fuer Administratoren verfuegbar."
                        )
                    _json_response(self, 200, bridge.delete_memory_record(_read_json(self)))
                elif parsed.path == "/event/delete":
                    _json_response(self, 200, bridge.delete_event(_read_json(self), user=user))
                elif parsed.path == "/offline/events":
                    _json_response(self, 200, bridge.import_offline_events(_read_json(self), user=user))
                elif parsed.path == "/mode":
                    _json_response(self, 200, bridge.set_mode(_read_json(self)))
                elif parsed.path == "/runtime":
                    _json_response(self, 200, bridge.set_runtime(_read_json(self)))
                elif parsed.path == "/agent/update":
                    if not bridge.can_manage_settings(self, user):
                        raise PermissionError(
                            "Agentenanzeigenamen sind nur lokal oder fuer Administratoren aenderbar."
                        )
                    _json_response(self, 200, bridge.update_agent_display(_read_json(self)))
                elif parsed.path == "/prompts":
                    if not bridge.can_manage_settings(self, user):
                        raise PermissionError(
                            "Prompts sind nur lokal oder fuer Administratoren verfuegbar."
                        )
                    _json_response(self, 200, bridge.save_prompts(_read_json(self)))
                elif parsed.path == "/settings":
                    if not bridge.can_manage_settings(self, user):
                        raise PermissionError(
                            "Einstellungen sind nur lokal oder fuer Administratoren verfuegbar."
                        )
                    _json_response(self, 200, bridge.save_web_settings(_read_json(self)))
                elif parsed.path == "/harness/test":
                    if not bridge.can_manage_settings(self, user):
                        raise PermissionError(
                            "Harness-Tests sind nur lokal oder fuer Administratoren verfuegbar."
                        )
                    _json_response(self, 200, bridge.test_harness(_read_json(self)))
                elif bridge.auth_enabled and parsed.path == "/auth/users":
                    payload = _read_json(self)
                    created = bridge.auth.create_user(
                        user,
                        payload.get("username"),
                        payload.get("password"),
                        payload.get("role", "user"),
                    )
                    _json_response(self, 201, {"ok": True, "user": created})
                else:
                    _json_response(self, 404, {"ok": False, "error": "not found"})
            except PermissionError as exc:
                _json_response(self, 403, {"ok": False, "error": str(exc)})
            except RuntimeError as exc:
                _json_response(self, 409, {"ok": False, "error": str(exc)})
            except Exception as exc:  # pylint: disable=broad-except
                _json_response(self, 400, {"ok": False, "error": str(exc)})

    return Handler


def run_bridge(home, host=DEFAULT_HOST, port=DEFAULT_PORT, token="", auth_enabled=False):
    bridge = TrinityBridge(home, token=token, auth_enabled=auth_enabled)
    server = ThreadingHTTPServer((host, int(port)), make_handler(bridge))
    print(f"Trinity Bridge läuft auf http://{host}:{port}")
    if host in {"0.0.0.0", "::"}:
        print("Hinweis: Für Tailscale erreichbar. Nutze --auth oder mindestens --token.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTrinity Bridge beendet.")
    finally:
        server.server_close()
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Trinity HTTP Bridge starten.")
    parser.add_argument("--home", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--token", default=os.environ.get("TRINITY_BRIDGE_TOKEN", ""))
    parser.add_argument("--auth", action="store_true", help="Passwort-Accounts und getrennte Nutzerbereiche aktivieren")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return run_bridge(args.home, host=args.host, port=args.port, token=args.token, auth_enabled=args.auth)


if __name__ == "__main__":
    raise SystemExit(main())
