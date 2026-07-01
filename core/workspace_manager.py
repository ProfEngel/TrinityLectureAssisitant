"""Local workspace and session metadata for Trinity."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from configuration import load_config
from trinity_paths import TrinityPaths


INBOX_WORKSPACE_ID = "_inbox"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def session_name_prefix() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M_")


def _slug(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-_")
    return cleaned or fallback


def _read_json(path: Path, fallback: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(fallback)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


@dataclass(frozen=True)
class WorkspaceRecord:
    id: str
    title: str
    kind: str
    status: str
    path: Path
    pinned: bool = False

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
            "status": self.status,
            "pinned": self.pinned,
            "path": str(self.path),
        }


@dataclass(frozen=True)
class SessionRecord:
    id: str
    workspace_id: str
    title: str
    status: str
    summary_status: str
    path: Path
    pinned: bool = False

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "title": self.title,
            "status": self.status,
            "summary_status": self.summary_status,
            "pinned": self.pinned,
            "path": str(self.path),
        }


@dataclass(frozen=True)
class NoteRecord:
    id: str
    workspace_id: str
    title: str
    path: Path
    status: str = "active"

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "title": self.title,
            "status": self.status,
            "path": str(self.path),
        }


class TrinityWorkspaceManager:
    """Manage workspaces and quick sessions in the local TrinityRuntime."""

    def __init__(self, home: str | Path, config: dict | None = None):
        self.home = Path(home).expanduser().resolve()
        self.config = config if config is not None else load_config(self.home / "core" / "config.json")
        self.paths = TrinityPaths.from_config(self.home, self.config)
        self.root = self.paths.runtime_root / "workspaces"

    def ensure_layout(self) -> dict:
        self.paths.ensure_layout()
        self.root.mkdir(parents=True, exist_ok=True)
        inbox = self.root / INBOX_WORKSPACE_ID
        if not (inbox / "workspace.json").exists():
            self._write_workspace(
                INBOX_WORKSPACE_ID,
                {
                    "id": INBOX_WORKSPACE_ID,
                    "title": "Schnellsessions",
                    "kind": "inbox",
                    "status": "active",
                    "pinned": True,
                    "created_at": _now_iso(),
                    "updated_at": _now_iso(),
                    "default_summary_policy": "manual",
                    "tags": ["inbox", "quick"],
                },
            )
        (inbox / "sessions").mkdir(parents=True, exist_ok=True)
        (inbox / "notes").mkdir(parents=True, exist_ok=True)
        return {
            "runtime_root": str(self.paths.runtime_root),
            "workspaces_root": str(self.root),
            "inbox": INBOX_WORKSPACE_ID,
        }

    def create_workspace(self, title: str, kind: str = "custom", pinned: bool = False) -> WorkspaceRecord:
        self.ensure_layout()
        base = _slug(title, "workspace")
        workspace_id = base
        counter = 2
        while (self.root / workspace_id / "workspace.json").exists():
            workspace_id = f"{base}-{counter}"
            counter += 1
        data = {
            "id": workspace_id,
            "title": title.strip() or workspace_id,
            "kind": kind or "custom",
            "status": "active",
            "pinned": bool(pinned),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "default_summary_policy": "manual",
            "tags": [],
        }
        self._write_workspace(workspace_id, data)
        (self.root / workspace_id / "sessions").mkdir(parents=True, exist_ok=True)
        (self.root / workspace_id / "notes").mkdir(parents=True, exist_ok=True)
        return self._workspace_record(workspace_id)

    def list_workspaces(self) -> list[WorkspaceRecord]:
        self.ensure_layout()
        records = [
            self._workspace_record(path.name)
            for path in self.root.iterdir()
            if path.is_dir() and (path / "workspace.json").exists()
        ]
        return sorted(
            records,
            key=lambda item: (
                item.id != INBOX_WORKSPACE_ID,
                not item.pinned,
                item.title.casefold(),
            ),
        )

    def get_workspace(self, workspace_id: str) -> WorkspaceRecord:
        self.ensure_layout()
        if not (self.root / workspace_id / "workspace.json").exists():
            raise ValueError(f"Arbeitsraum nicht gefunden: {workspace_id}")
        (self.root / workspace_id / "sessions").mkdir(parents=True, exist_ok=True)
        (self.root / workspace_id / "notes").mkdir(parents=True, exist_ok=True)
        return self._workspace_record(workspace_id)

    def create_session(
        self,
        title: str | None = None,
        workspace_id: str = INBOX_WORKSPACE_ID,
        mode: str = "lecture",
    ) -> SessionRecord:
        self.ensure_layout()
        workspace = self.get_workspace(workspace_id)
        safe_title = (title or session_name_prefix()).strip() or session_name_prefix()
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        session_dir = workspace.path / "sessions" / session_id
        data = {
            "id": session_id,
            "workspace_id": workspace.id,
            "title": safe_title,
            "status": "active",
            "summary_status": "none",
            "mode": mode or "lecture",
            "started_at": _now_iso(),
            "ended_at": None,
            "last_opened_at": _now_iso(),
            "media_count": 0,
            "job_count": 0,
            "pinned": False,
            "tags": [],
        }
        _write_json(session_dir / "session.json", data)
        (session_dir / "media").mkdir(parents=True, exist_ok=True)
        (session_dir / "events.jsonl").touch(exist_ok=True)
        (session_dir / "transcript.md").touch(exist_ok=True)
        return self._session_record(session_dir)

    def list_sessions(
        self,
        workspace_id: str | None = None,
        limit: int | None = None,
    ) -> list[SessionRecord]:
        self.ensure_layout()
        session_dirs: Iterable[Path]
        if workspace_id:
            workspace = self.get_workspace(workspace_id)
            session_dirs = (workspace.path / "sessions").glob("*/session.json")
        else:
            session_dirs = self.root.glob("*/sessions/*/session.json")
        records = [self._session_record(path.parent) for path in session_dirs]
        records.sort(
            key=lambda item: _read_json(item.path / "session.json", {}).get("last_opened_at", ""),
            reverse=True,
        )
        return records[:limit] if limit else records

    def get_session(self, session_id: str) -> SessionRecord:
        self.ensure_layout()
        session_dir = self._find_session_dir(session_id)
        if session_dir is None:
            raise ValueError(f"Session nicht gefunden: {session_id}")
        return self._session_record(session_dir)

    def update_session_summary_status(self, session_id: str, status: str) -> SessionRecord:
        self.ensure_layout()
        session_dir = self._find_session_dir(session_id)
        if session_dir is None:
            raise ValueError(f"Session nicht gefunden: {session_id}")
        data = _read_json(session_dir / "session.json", {})
        data["summary_status"] = status or "none"
        data["updated_at"] = _now_iso()
        _write_json(session_dir / "session.json", data)
        return self._session_record(session_dir)

    def update_workspace_pinned(self, workspace_id: str, pinned: bool) -> WorkspaceRecord:
        self.ensure_layout()
        workspace = self.get_workspace(workspace_id)
        data = _read_json(workspace.path / "workspace.json", {})
        data["pinned"] = bool(pinned)
        data["updated_at"] = _now_iso()
        _write_json(workspace.path / "workspace.json", data)
        return self._workspace_record(workspace.id)

    def update_session_pinned(self, session_id: str, pinned: bool) -> SessionRecord:
        self.ensure_layout()
        session_dir = self._find_session_dir(session_id)
        if session_dir is None:
            raise ValueError(f"Session nicht gefunden: {session_id}")
        data = _read_json(session_dir / "session.json", {})
        data["pinned"] = bool(pinned)
        data["updated_at"] = _now_iso()
        _write_json(session_dir / "session.json", data)
        return self._session_record(session_dir)

    def move_session(self, session_id: str, target_workspace_id: str) -> SessionRecord:
        self.ensure_layout()
        target = self.get_workspace(target_workspace_id)
        current_dir = self._find_session_dir(session_id)
        if current_dir is None:
            raise ValueError(f"Session nicht gefunden: {session_id}")
        target_dir = target.path / "sessions" / session_id
        if current_dir == target_dir:
            return self._session_record(current_dir)
        if target_dir.exists():
            raise ValueError(f"Zielsession existiert bereits: {target_dir}")
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        current_dir.rename(target_dir)
        data = _read_json(target_dir / "session.json", {})
        data["workspace_id"] = target.id
        data["updated_at"] = _now_iso()
        data["last_opened_at"] = _now_iso()
        _write_json(target_dir / "session.json", data)
        return self._session_record(target_dir)

    def create_note(self, workspace_id: str, title: str | None = None, body: str = "") -> NoteRecord:
        self.ensure_layout()
        workspace = self.get_workspace(workspace_id)
        safe_title = (title or session_name_prefix() + "Notiz").strip() or session_name_prefix() + "Notiz"
        note_id = f"note_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        note_path = workspace.path / "notes" / f"{note_id}.md"
        heading = safe_title.lstrip("# ").strip() or note_id
        content = body.strip()
        if content:
            note_text = f"# {heading}\n\n{content}\n"
        else:
            note_text = f"# {heading}\n\n"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(note_text, encoding="utf-8")
        metadata = {
            "id": note_id,
            "workspace_id": workspace.id,
            "title": safe_title,
            "status": "active",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "path": str(note_path),
        }
        _write_json(workspace.path / "notes" / f"{note_id}.json", metadata)
        return NoteRecord(
            id=note_id,
            workspace_id=workspace.id,
            title=safe_title,
            status="active",
            path=note_path,
        )

    def list_notes(self, workspace_id: str | None = None, limit: int | None = None) -> list[NoteRecord]:
        self.ensure_layout()
        if workspace_id:
            workspace = self.get_workspace(workspace_id)
            note_files = (workspace.path / "notes").glob("*.json")
        else:
            note_files = self.root.glob("*/notes/*.json")
        records = [self._note_record(path) for path in note_files]
        records.sort(
            key=lambda item: _read_json(item.path.with_suffix(".json"), {}).get("updated_at", ""),
            reverse=True,
        )
        return records[:limit] if limit else records

    def _find_session_dir(self, session_id: str) -> Path | None:
        for path in self.root.glob("*/sessions/*/session.json"):
            if path.parent.name == session_id:
                return path.parent
        return None

    @staticmethod
    def _note_record(metadata_path: Path) -> NoteRecord:
        data = _read_json(metadata_path, {})
        path = Path(str(data.get("path") or metadata_path.with_suffix(".md")))
        return NoteRecord(
            id=str(data.get("id") or metadata_path.stem),
            workspace_id=str(data.get("workspace_id") or metadata_path.parent.parent.name),
            title=str(data.get("title") or metadata_path.stem),
            status=str(data.get("status") or "active"),
            path=path,
        )

    def _write_workspace(self, workspace_id: str, data: dict) -> None:
        workspace_dir = self.root / workspace_id
        _write_json(workspace_dir / "workspace.json", data)

    def _workspace_record(self, workspace_id: str) -> WorkspaceRecord:
        path = self.root / workspace_id
        data = _read_json(path / "workspace.json", {})
        return WorkspaceRecord(
            id=str(data.get("id") or workspace_id),
            title=str(data.get("title") or workspace_id),
            kind=str(data.get("kind") or "custom"),
            status=str(data.get("status") or "active"),
            pinned=bool(data.get("pinned", False)),
            path=path,
        )

    @staticmethod
    def _session_record(session_dir: Path) -> SessionRecord:
        data = _read_json(session_dir / "session.json", {})
        return SessionRecord(
            id=str(data.get("id") or session_dir.name),
            workspace_id=str(data.get("workspace_id") or INBOX_WORKSPACE_ID),
            title=str(data.get("title") or session_dir.name),
            status=str(data.get("status") or "active"),
            summary_status=str(data.get("summary_status") or "none"),
            pinned=bool(data.get("pinned", False)),
            path=session_dir,
        )
