"""Conservative policy decisions for the agent ecosystem."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


AUTO_ACTIONS = {"analyze", "summarize", "create_artifact", "read_file"}
APPROVAL_ACTIONS = {
    "move_file",
    "delete",
    "send_mail",
    "external_upload",
    "publish",
    "cloud_model",
    "activate_skill",
    "share_skill",
    "network_access",
}
DENY_ACTIONS = {"install_package", "system_command"}


@dataclass(frozen=True)
class PolicyDecision:
    action: str
    allowed: bool
    requires_approval: bool
    reason: str


class PolicyEngine:
    """Default-deny policy for dangerous actions; manifests remain the first gate."""

    def decide(
        self,
        action: str,
        allowed_tools: Optional[Iterable[str]] = None,
        allowed_paths: Optional[Iterable[str]] = None,
        path: str = "",
    ) -> PolicyDecision:
        normalized = str(action).strip().lower()
        if normalized in DENY_ACTIONS:
            return PolicyDecision(
                normalized,
                False,
                False,
                "Diese Aktion ist standardmaessig blockiert.",
            )
        if normalized in APPROVAL_ACTIONS:
            return PolicyDecision(
                normalized,
                True,
                True,
                "Diese Aktion verlangt eine explizite Freigabe.",
            )
        if normalized in AUTO_ACTIONS:
            if normalized == "create_artifact" and path and not self.path_allowed(path, allowed_paths):
                return PolicyDecision(
                    normalized,
                    True,
                    True,
                    "Der Zielpfad liegt ausserhalb der erlaubten Pfade.",
                )
            return PolicyDecision(
                normalized,
                True,
                False,
                "Lokale, risikoarme Aktion ist erlaubt.",
            )
        return PolicyDecision(
            normalized,
            False,
            False,
            "Unbekannte Aktion ist standardmaessig blockiert.",
        )

    @staticmethod
    def path_allowed(path: str, allowed_paths: Optional[Iterable[str]]) -> bool:
        roots = [Path(item).expanduser().resolve() for item in (allowed_paths or []) if item]
        if not roots:
            return False
        target = Path(path).expanduser().resolve()
        for root in roots:
            try:
                target.relative_to(root)
                return True
            except ValueError:
                continue
        return False
