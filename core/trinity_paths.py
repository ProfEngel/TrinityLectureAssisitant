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
    "harnesses/goose",
    "harnesses/future",
    "workspaces",
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

@dataclass(frozen=True)
class TrinityPaths:
    """Runtime and vault roots plus convenience layout helpers."""

    home: Path
    runtime_root: Path
    vault_root: Path
    profile: str

    @classmethod
    def from_config(
        cls,
        home: str | Path,
        config: Optional[dict] = None,
        platform_name: Optional[str] = None,
    ) -> "TrinityPaths":
        home_path = Path(home).expanduser().resolve()
        control = (config or {}).get("control_plane", {})
        profile = str((config or {}).get("system", {}).get("profile", "PRIVAT")).upper()
        if profile not in {"BIZ", "PRIVAT", "TEST"}:
            profile = "PRIVAT"
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
                default_vault_root(platform_name=platform_name, profile=profile),
            ),
            profile=profile,
        )

    def ensure_layout(self) -> dict:
        """Create the expected local runtime folders.

        The synchronized BrainVault is only an external agent pool now. Updates
        must not recreate the older TrinityVault folders such as 00_registry or
        03_results inside the user's cloud folder.
        """

        for relative in RUNTIME_DIRS:
            (self.runtime_root / relative).mkdir(parents=True, exist_ok=True)
        return self.summary()

    def separation_warnings(self) -> list[str]:
        warnings: list[str] = []
        if _is_relative_to(self.runtime_root, self.vault_root):
            warnings.append("Runtime liegt innerhalb des synchronisierten Inhalts-Vaults.")
        if _is_relative_to(self.vault_root, self.runtime_root):
            warnings.append("Inhalts-Vault liegt innerhalb der lokalen Runtime.")
        if _looks_like_cloud_sync(self.runtime_root):
            warnings.append("Runtime liegt in einem Cloud-Ordner; aktive Jobs müssen lokal bleiben.")
        if self.profile != "TEST" and not _looks_like_cloud_sync(self.vault_root):
            warnings.append(
                "Inhalts-Vault liegt nicht in einem erkennbaren Cloud-Ordner; "
                "Synchronisation und Sicherung bitte prüfen."
            )
        return warnings

    def summary(self) -> dict:
        return {
            "home": str(self.home),
            "runtime_root": str(self.runtime_root),
            "vault_root": str(self.vault_root),
            "profile": self.profile,
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


def default_vault_root(
    platform_name: Optional[str] = None,
    profile: Optional[str] = None,
) -> Path:
    host = platform_name or platform.system()
    normalized_profile = str(profile or ("BIZ" if host == "Windows" else "PRIVAT")).upper()
    if normalized_profile == "TEST":
        return Path.home() / "Trinity-Testbereich"
    if normalized_profile == "BIZ":
        for variable in ("OneDriveCommercial", "OneDrive"):
            value = os.environ.get(variable)
            if value:
                return Path(value).expanduser() / "BizVault"
        return Path.home() / "BizVault"
    candidate = (
        Path.home()
        / "Library"
        / "Mobile Documents"
        / "com~apple~CloudDocs"
        / "BrainVault"
    )
    if candidate.exists() or candidate.parent.exists():
        return candidate
    return Path.home() / "BrainVault"


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


def _looks_like_cloud_sync(path: Path) -> bool:
    rendered = "/".join(path.parts).casefold()
    markers = (
        "mobile documents",
        "clouddocs",
        "onedrive",
        "dropbox",
        "google drive",
        "googledrive",
        "sharepoint",
    )
    return any(marker in rendered for marker in markers)
