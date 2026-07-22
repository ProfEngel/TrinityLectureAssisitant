"""Recoverable reset and deletion helpers for Trinity's operational memory."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

try:
    from .configuration import load_config
    from .canvas_manager import default_canvas_install_dir
    from .memory_store import MemoryStore
    from .trinity_paths import TrinityPaths
    from .unified_session import UnifiedSessionStore
    from .workspace_manager import TrinityWorkspaceManager
except ImportError:  # Direct execution with core/ on sys.path.
    from configuration import load_config
    from canvas_manager import default_canvas_install_dir
    from memory_store import MemoryStore
    from trinity_paths import TrinityPaths
    from unified_session import UnifiedSessionStore
    from workspace_manager import TrinityWorkspaceManager


PROTECTED_CONTENT = ("core/config.json", "core/Soul.md", "core/User.md", "RAG", "Vault")


def _recovery_root() -> Path:
    configured = str(os.environ.get("TRINITY_RECOVERY_ROOT") or "").strip()
    return Path(configured).expanduser().resolve() if configured else Path.home() / "Trinity-Recovery"


def _count_files(path: Path) -> int:
    return sum(1 for item in path.rglob("*") if item.is_file()) if path.exists() else 0


def operational_status(home: str | Path) -> dict:
    home = Path(home).expanduser().resolve()
    config = load_config(home / "core" / "config.json")
    paths = TrinityPaths.from_config(home, config)
    memory_dir = home / "memory"
    manager = TrinityWorkspaceManager(home, config)
    store = MemoryStore(memory_dir / "trinity_memory.sqlite3")
    with store.connect() as db:
        database = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("sessions", "messages", "memories", "memory_tags", "memory_edges")
        }
    return {
        "profile": paths.profile,
        "memory_files": _count_files(memory_dir),
        "workspaces": len(manager.list_workspaces()),
        "runtime_sessions": len(manager.list_sessions()),
        "database": database,
        "protected": list(PROTECTED_CONTENT),
    }


def reset_operational_memory(
    home: str | Path,
    *,
    backup: bool = True,
    include_generated: bool = False,
    include_canvas: bool = False,
) -> dict:
    """Reset conversations and memory while never touching Vault, RAG or prompts."""

    home = Path(home).expanduser().resolve()
    config = load_config(home / "core" / "config.json")
    paths = TrinityPaths.from_config(home, config)
    before = operational_status(home)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    recovery = _recovery_root() / f"reset-{paths.profile.lower()}-{timestamp}"

    targets = {
        "memory": home / "memory",
        "workspaces": paths.runtime_root / "workspaces",
        "sessions": paths.runtime_root / "sessions",
        "archive": paths.runtime_root / "archive",
        "artifacts": paths.runtime_root / "artifacts",
        "runtime_memory": paths.runtime_root / "memory",
    }
    if include_generated:
        targets["generated_media"] = home / "gen_images"
    if include_canvas:
        targets["canvas"] = paths.runtime_root / "canvas"
        canvas_settings = config.get("canvas", {})
        configured_canvas = str(canvas_settings.get("install_dir") or "").strip()
        canvas_install_dir = (
            Path(configured_canvas).expanduser().resolve()
            if configured_canvas
            else default_canvas_install_dir()
        )
        legacy_canvas_data = canvas_install_dir / "data"
        if legacy_canvas_data.resolve() != targets["canvas"].resolve():
            targets["canvas_legacy_data"] = legacy_canvas_data

    if backup:
        recovery.mkdir(parents=True, exist_ok=False)
        for name, source in targets.items():
            if source.is_dir():
                shutil.copytree(source, recovery / name)
            elif source.is_file():
                (recovery / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, recovery / name)
        (recovery / "RESET_MANIFEST.json").write_text(
            json.dumps(
                {
                    "created_at": timestamp,
                    "profile": paths.profile,
                    "home": str(home),
                    "runtime_root": str(paths.runtime_root),
                    "before": before,
                    "include_generated": include_generated,
                    "include_canvas": include_canvas,
                    "targets": {name: str(path) for name, path in targets.items()},
                    "protected": list(PROTECTED_CONTENT),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    for target in targets.values():
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()

    (home / "memory").mkdir(parents=True, exist_ok=True)
    paths.ensure_layout()
    MemoryStore(home / "memory" / "trinity_memory.sqlite3")
    TrinityWorkspaceManager(home, config).ensure_layout()
    active = UnifiedSessionStore(home, config).current(create=True)
    after = operational_status(home)
    return {
        "ok": True,
        "profile": paths.profile,
        "backup": str(recovery) if backup else "",
        "before": before,
        "after": after,
        "active_session": active.as_dict() if active else None,
        "protected": list(PROTECTED_CONTENT),
    }


def delete_session_summary(home: str | Path, session_id: str) -> dict:
    home = Path(home).expanduser().resolve()
    config = load_config(home / "core" / "config.json")
    manager = TrinityWorkspaceManager(home, config)
    session = manager.get_session(session_id)
    removed = []
    for path in (
        session.path / "summary.md",
        home / "memory" / "summaries" / f"Summary_{session_id}.md",
        home / "memory" / "summaries" / f"Summary_Session_{session_id}.md",
    ):
        if path.is_file():
            path.unlink()
            removed.append(str(path))
    store = MemoryStore(home / "memory" / "trinity_memory.sqlite3")
    memory_count = store.delete_session_memories(session_id, kinds=("session-summary", "summary"))
    manager.update_session_summary_status(session_id, "none")
    return {"session_id": session_id, "removed_files": removed, "removed_memories": memory_count}
