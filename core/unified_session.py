"""One server-authoritative active conversation for every Trinity instance."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from configuration import load_config
from trinity_paths import TrinityPaths
from workspace_manager import INBOX_WORKSPACE_ID, SessionRecord, TrinityWorkspaceManager


_SESSION_LOCK = threading.RLock()


class UnifiedSessionStore:
    """Persist and resolve the single active session shared by all channels.

    Archived sessions remain regular workspace records.  Only the pointer to the
    currently active conversation is unique and server-owned; client supplied
    session IDs are treated as hints and never split the live conversation.
    """

    def __init__(self, home: str | Path, config: dict | None = None):
        self.home = Path(home).expanduser().resolve()
        self.config = config if config is not None else load_config(self.home / "core" / "config.json")
        self.paths = TrinityPaths.from_config(self.home, self.config)
        self.manager = TrinityWorkspaceManager(self.home, self.config)
        self.pointer_path = self.paths.runtime_root / "sessions" / "active_session.json"

    @property
    def profile(self) -> str:
        return self.paths.profile

    def current(self, create: bool = True) -> SessionRecord | None:
        with _SESSION_LOCK:
            stored = self._read_pointer()
            session_id = str(stored.get("session_id") or "").strip()
            if session_id:
                try:
                    return self.manager.get_session(session_id)
                except ValueError:
                    pass

            active = next(
                (item for item in self.manager.list_sessions(limit=200) if item.status == "active"),
                None,
            )
            if active is not None:
                self.activate(active, source="runtime-recovery")
                return active
            if not create:
                return None

            created = self.manager.create_session(
                title="Gemeinsame Trinity-Sitzung",
                workspace_id=INBOX_WORKSPACE_ID,
                mode=str(self.config.get("system", {}).get("mode") or "chat"),
            )
            self.activate(created, source="runtime-start")
            return created

    def activate(self, session: SessionRecord | str, source: str = "client") -> SessionRecord:
        with _SESSION_LOCK:
            record = self.manager.get_session(session) if isinstance(session, str) else session
            payload = {
                "schema_version": 1,
                "profile": self.profile,
                "session_id": record.id,
                "session_name": record.title,
                "workspace_id": record.workspace_id,
                "source": str(source or "client")[:80],
            }
            self.pointer_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.pointer_path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, self.pointer_path)
            return record

    def as_dict(self) -> dict:
        record = self.current()
        return {
            "id": record.id,
            "title": record.title,
            "workspace_id": record.workspace_id,
            "status": record.status,
            "profile": self.profile,
        }

    def canonicalize(self, request: dict | None, source: str = "runtime") -> dict:
        canonical = dict(request or {})
        session = self.current()
        supplied_id = str(canonical.get("session_id") or "").strip()
        supplied_name = str(canonical.get("session_name") or "").strip()
        if supplied_id and supplied_id != session.id:
            canonical["client_session_id"] = supplied_id
        if supplied_name and supplied_name != session.title:
            canonical["client_session_name"] = supplied_name[:160]
        canonical["session_id"] = session.id
        canonical["session_name"] = session.title
        canonical["profile"] = self.profile
        canonical.setdefault("source", source)
        return canonical

    def _read_pointer(self) -> dict:
        try:
            data = json.loads(self.pointer_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict) or str(data.get("profile") or "") != self.profile:
            return {}
        return data
