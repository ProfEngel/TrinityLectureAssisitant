"""Resolve Trinity runtime and vault locations without mixing their duties."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


RUNTIME_DIRS = (
    "gateway",
    "jobs/queue",
    "jobs/active",
    "jobs/workspaces",
    "jobs/finished",
    "jobs/failed",
    "harnesses/codex",
    "harnesses/pi",
    "harnesses/opencode",
    "harnesses/future",
    "sessions",
    "logs",
    "cache",
    "containers",
    "databases",
    "memory",
    "temp",
    "secrets",
    "locks",
)

VAULT_DIRS = (
    "00_registry/policies",
    "00_registry/releases",
    "00_registry/model_profiles",
    "01_agents",
    "02_projects",
    "03_results",
    "04_templates",
    "05_knowledge",
    "06_audit",
    "07_exports",
    "99_archive",
)


@dataclass(frozen=True)
class TrinityPaths:
    """Runtime and vault roots plus convenience layout helpers."""

    home: Path
    runtime_root: Path
    vault_root: Path

    @classmethod
    def from_config(
        cls,
        home: str | Path,
        config: Optional[dict] = None,
        platform_name: Optional[str] = None,
    ) -> "TrinityPaths":
        home_path = Path(home).expanduser().resolve()
        control = (config or {}).get("control_plane", {})
        runtime_value = control.get("runtime_root") or os.environ.get("TRINITY_RUNTIME")
        vault_value = control.get("vault_root") or os.environ.get("TRINITY_VAULT")
        return cls(
            home=home_path,
            runtime_root=_resolve_path(
                runtime_value,
                default_runtime_root(platform_name=platform_name, home=home_path),
            ),
            vault_root=_resolve_path(
                vault_value,
                default_vault_root(platform_name=platform_name),
            ),
        )

    def ensure_layout(self) -> dict:
        """Create the expected local runtime and synced vault folders."""

        for relative in RUNTIME_DIRS:
            (self.runtime_root / relative).mkdir(parents=True, exist_ok=True)
        for relative in VAULT_DIRS:
            (self.vault_root / relative).mkdir(parents=True, exist_ok=True)
        return self.summary()

    def separation_warnings(self) -> list[str]:
        warnings: list[str] = []
        if _is_relative_to(self.runtime_root, self.vault_root):
            warnings.append("Runtime liegt innerhalb des synchronisierten TrinityVault.")
        if _is_relative_to(self.vault_root, self.runtime_root):
            warnings.append("TrinityVault liegt innerhalb der lokalen Runtime.")
        if _looks_like_icloud(self.runtime_root):
            warnings.append("Runtime liegt in iCloud; aktive Jobs sollten lokal bleiben.")
        if not _looks_like_icloud(self.vault_root):
            warnings.append("TrinityVault liegt nicht in iCloud; Synchronisation ist nicht garantiert.")
        return warnings

    def summary(self) -> dict:
        return {
            "home": str(self.home),
            "runtime_root": str(self.runtime_root),
            "vault_root": str(self.vault_root),
            "warnings": self.separation_warnings(),
        }


def default_runtime_root(platform_name: Optional[str] = None, home: Optional[str | Path] = None) -> Path:
    if home:
        return Path(home).expanduser().resolve() / "TrinityRuntime"
    host = platform_name or platform.system()
    if host == "Windows":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base).expanduser() / "Trinity" / "TrinityRuntime"
        return Path.home() / "AppData" / "Local" / "Trinity" / "TrinityRuntime"
    if host == "Linux":
        base = os.environ.get("XDG_DATA_HOME")
        if base:
            return Path(base).expanduser() / "trinity" / "TrinityRuntime"
        return Path.home() / ".local" / "share" / "trinity" / "TrinityRuntime"
    return Path.home() / "Trinity_Assistant" / "TrinityRuntime"


def default_vault_root(platform_name: Optional[str] = None) -> Path:
    host = platform_name or platform.system()
    if host == "Windows":
        return Path.home() / "BrainVault" / "MainHub" / "TrinityVault"
    candidate = (
        Path.home()
        / "Library"
        / "Mobile Documents"
        / "com~apple~CloudDocs"
        / "BrainVault"
        / "MainHub"
        / "TrinityVault"
    )
    if candidate.parent.exists():
        return candidate
    return Path.home() / "BrainVault" / "MainHub" / "TrinityVault"


def _resolve_path(value: object, fallback: Path) -> Path:
    if value:
        return Path(str(value)).expanduser().resolve()
    return fallback.expanduser().resolve()


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _looks_like_icloud(path: Path) -> bool:
    return "Mobile Documents" in path.parts or "CloudDocs" in path.parts
