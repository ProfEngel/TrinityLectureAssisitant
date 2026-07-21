"""Safe setup helpers for Trinity's durable content vaults.

The content vault is deliberately separate from Trinity's runtime and the
local executable-agent pool. Setup is idempotent: it adds missing Phase-1
folders but never moves, renames, or overwrites existing user content.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Iterable, Optional


PHASE1_VAULT_DIRECTORIES = (
    "00 Noch zuordnen",
    "10 Aktive Projekte",
    "20 Wissen und Quellen",
    "30 Vorlagen und Bausteine",
    "40 Abgeschlossene Projekte",
    "50 Fertige Werke und Veröffentlichungen",
    "90 Inhaltsverzeichnis und Schlagwörter",
)

PROFILE_ALIASES = {
    "beruf": "BIZ",
    "biz": "BIZ",
    "privat": "PRIVAT",
    "private": "PRIVAT",
    "test": "TEST",
    "testbereich": "TEST",
}

IGNORED_TOP_LEVEL_ENTRIES = {".DS_Store", "desktop.ini", "Thumbs.db"}


def normalize_profile(value: object, platform_name: Optional[str] = None) -> str:
    """Return BIZ, PRIVAT, or TEST, with a platform-safe default."""

    normalized = str(value or "").strip().casefold()
    if normalized in PROFILE_ALIASES:
        return PROFILE_ALIASES[normalized]
    return "BIZ" if (platform_name or platform.system()) == "Windows" else "PRIVAT"


def profile_label(profile: object) -> str:
    return {"BIZ": "Beruf", "PRIVAT": "Privat", "TEST": "Testbereich"}[
        normalize_profile(profile)
    ]


def vault_name(profile: object) -> str:
    return {"BIZ": "BizVault", "PRIVAT": "BrainVault", "TEST": "TestVault"}[
        normalize_profile(profile)
    ]


def suggested_vault_root(
    profile: object,
    platform_name: Optional[str] = None,
) -> Path:
    """Suggest a sensible location while still requiring user confirmation."""

    host = platform_name or platform.system()
    normalized = normalize_profile(profile, host)
    if normalized == "TEST":
        return Path.home() / "Trinity-Testbereich"
    if normalized == "BIZ":
        for variable in ("OneDriveCommercial", "OneDrive"):
            value = os.environ.get(variable)
            if value:
                return Path(value).expanduser() / "BizVault"
        return Path.home() / "BizVault"
    if host == "Darwin":
        return (
            Path.home()
            / "Library"
            / "Mobile Documents"
            / "com~apple~CloudDocs"
            / "BrainVault"
        )
    return Path.home() / "BrainVault"


def inspect_content_vault(root: str | Path) -> dict:
    """Inspect only the top level so large Cloud Vaults are not downloaded."""

    root_path = Path(root).expanduser().resolve()
    if root_path.exists() and not root_path.is_dir():
        raise ValueError(f"Der Vault-Pfad ist keine Ordnerstruktur: {root_path}")

    entries = []
    if root_path.is_dir():
        entries = sorted(
            entry.name
            for entry in root_path.iterdir()
            if entry.name not in IGNORED_TOP_LEVEL_ENTRIES
        )
    expected = set(PHASE1_VAULT_DIRECTORIES)
    unclassified = [
        name
        for name in entries
        if name not in expected and name != "README.md"
    ]
    return {
        "root": str(root_path),
        "exists": root_path.is_dir(),
        "entry_count": len(entries),
        "entries": entries,
        "unclassified_entries": unclassified,
        "existing_directories": [
            name for name in PHASE1_VAULT_DIRECTORIES if (root_path / name).is_dir()
        ],
        "missing_directories": [
            name for name in PHASE1_VAULT_DIRECTORIES if not (root_path / name).is_dir()
        ],
    }


def validate_content_vault_location(
    root: str | Path,
    *,
    forbidden_roots: Iterable[str | Path] = (),
) -> Path:
    """Reject locations that would mix durable content with executable state."""

    root_path = Path(root).expanduser().resolve()
    for forbidden in forbidden_roots:
        if not forbidden:
            continue
        forbidden_path = Path(forbidden).expanduser().resolve()
        if _is_relative_to(root_path, forbidden_path) or _is_relative_to(
            forbidden_path, root_path
        ):
            raise ValueError(
                "Der Inhalts-Vault muss getrennt von Trinity-Installation und "
                f"Runtime liegen: {root_path}"
            )
    return root_path


def ensure_content_vault_layout(
    root: str | Path,
    *,
    profile: object,
    forbidden_roots: Iterable[str | Path] = (),
) -> dict:
    """Adopt an existing folder safely or create a new Phase-1 content vault."""

    root_path = validate_content_vault_location(root, forbidden_roots=forbidden_roots)
    before = inspect_content_vault(root_path)
    created_root = not before["exists"]
    root_path.mkdir(parents=True, exist_ok=True)

    created_directories = []
    for name in PHASE1_VAULT_DIRECTORIES:
        target = root_path / name
        if not target.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            created_directories.append(name)

    readme_path = root_path / "README.md"
    readme_created = _write_if_missing(readme_path, _vault_readme(profile))

    inventory_path = None
    inventory_created = False
    if before["unclassified_entries"]:
        inventory_path = (
            root_path
            / "90 Inhaltsverzeichnis und Schlagwörter"
            / "BESTAND_BEI_EINRICHTUNG.md"
        )
        inventory_created = _write_if_missing(
            inventory_path,
            _existing_inventory(profile, before["unclassified_entries"]),
        )

    return {
        "root": str(root_path),
        "profile": normalize_profile(profile),
        "vault_name": vault_name(profile),
        "created_root": created_root,
        "created_directories": created_directories,
        "readme_created": readme_created,
        "preserved_entries": before["unclassified_entries"],
        "inventory_path": str(inventory_path) if inventory_path else "",
        "inventory_created": inventory_created,
        "changed": bool(
            created_root or created_directories or readme_created or inventory_created
        ),
    }


def _vault_readme(profile: object) -> str:
    normalized = normalize_profile(profile)
    label = profile_label(normalized)
    name = vault_name(normalized)
    purpose = {
        "BIZ": "berufliche ",
        "PRIVAT": "private ",
        "TEST": "ausdrücklich freigegebene Test-",
    }[normalized]
    lines = [
        f"# {name} – {label}",
        "",
        f"Dieser Vault ist die dauerhafte Datenwahrheit für {purpose}Inhalte.",
        "",
        "## Hauptbereiche",
        "",
        "- `00 Noch zuordnen`: vorübergehender Eingang",
        "- `10 Aktive Projekte`: aktuell bearbeitete Vorhaben",
        "- `20 Wissen und Quellen`: Nachschlagewissen und Quellen",
        "- `30 Vorlagen und Bausteine`: wiederverwendbare Grundlagen",
        "- `40 Abgeschlossene Projekte`: vollständig archivierte Vorhaben",
        "- `50 Fertige Werke und Veröffentlichungen`: finale Fassungen",
        "- `90 Inhaltsverzeichnis und Schlagwörter`: Kataloge und Manifeste",
        "",
        "Nicht hierher gehören Trinity-Runtime, ausführbare Agenten, lokale",
        "RAG-/Graphify-Indizes, Caches, rohe technische Logs oder Secrets.",
        "",
    ]
    return "\n".join(lines)


def _existing_inventory(profile: object, entries: list[str]) -> str:
    lines = [
        "# Bestand bei der Trinity-Einrichtung",
        "",
        f"Profil: {profile_label(profile)}",
        "",
        "Trinity hat folgende bereits vorhandene Einträge erkannt und",
        "unverändert übernommen. Es wurde nichts verschoben, um bestehende",
        "Verknüpfungen und Arbeitsabläufe nicht zu beschädigen:",
        "",
    ]
    lines.extend(f"- `{name}`" for name in entries)
    lines.extend(
        [
            "",
            "Diese Einträge können später kontrolliert katalogisiert oder nach",
            "`00 Noch zuordnen` übernommen werden. RAG-, Graphify- und andere",
            "Suchindizes sind neu aufbaubar und nicht die Originaldaten.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False
