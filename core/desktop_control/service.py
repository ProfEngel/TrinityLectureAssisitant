"""Policy-first planning and execution for desktop application actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import platform
import time
from pathlib import Path
from typing import Protocol

from policy_engine import PolicyEngine


class DesktopAction(str, Enum):
    OPEN_APPLICATION = "desktop_open_application"
    CLOSE_APPLICATION = "desktop_close_application"
    TYPE_TEXT = "desktop_type_text"
    SAVE_DOCUMENT = "desktop_save_document"
    FORMAT_DOCUMENT = "desktop_format_document"
    REPLACE_SELECTION = "desktop_replace_selection"


@dataclass(frozen=True)
class DesktopControlRequest:
    action: DesktopAction
    application: str
    text: str = ""
    path: str = ""
    structured_adapter_available: bool = False


@dataclass(frozen=True)
class DesktopControlPlan:
    allowed: bool
    requires_approval: bool
    strategy: str
    reason: str


@dataclass(frozen=True)
class DesktopControlResult:
    success: bool
    executed: bool
    message: str


class ApplicationController(Protocol):
    def open_application(self, application: str) -> str: ...

    def close_application(self, application: str) -> str: ...


class DesktopControlService:
    """Validate desktop actions before delegating to a native adapter."""

    def __init__(
        self,
        config: dict | None = None,
        policy: PolicyEngine | None = None,
        controller: ApplicationController | None = None,
        home: str | Path | None = None,
    ):
        self.config = config or {}
        self.policy = policy or PolicyEngine()
        self.controller = controller
        self.home = Path(home).resolve() if home else None

    def plan(self, request: DesktopControlRequest) -> DesktopControlPlan:
        if not bool(self.config.get("enabled", False)):
            return DesktopControlPlan(False, False, "none", "Desktopsteuerung ist deaktiviert.")

        policy = self.policy.decide(request.action.value)
        if not policy.allowed:
            return DesktopControlPlan(False, False, "none", policy.reason)

        application = request.application.strip()
        if not application:
            return DesktopControlPlan(False, False, "none", "Eine Zielanwendung ist erforderlich.")

        allowed_apps = {
            str(item).strip().casefold()
            for item in self.config.get("allowed_applications", [])
            if str(item).strip()
        }
        if not allowed_apps or application.casefold() not in allowed_apps:
            return DesktopControlPlan(
                False,
                False,
                "none",
                "Die Zielanwendung ist nicht freigegeben.",
            )

        if request.action in {
            DesktopAction.OPEN_APPLICATION,
            DesktopAction.CLOSE_APPLICATION,
        }:
            strategy = "native_application_api"
        elif request.structured_adapter_available:
            strategy = "structured_application_adapter"
        elif bool(self.config.get("allow_visible_ui_fallback", False)):
            strategy = "visible_ui_fallback"
        else:
            return DesktopControlPlan(
                False,
                False,
                "none",
                "Kein strukturierter Adapter vorhanden; sichtbare UI-Steuerung ist deaktiviert.",
            )

        return DesktopControlPlan(
            True,
            policy.requires_approval or bool(self.config.get("require_confirmation", True)),
            strategy,
            "Aktion ist geplant, aber noch nicht ausgefuehrt.",
        )

    def execute(
        self,
        request: DesktopControlRequest,
        *,
        confirmed: bool = False,
    ) -> DesktopControlResult:
        plan = self.plan(request)
        if not plan.allowed:
            return DesktopControlResult(False, False, plan.reason)
        if plan.requires_approval and not confirmed:
            return DesktopControlResult(
                False,
                False,
                "Bitte bestaetige die Desktopaktion ausdruecklich.",
            )
        if bool(self.config.get("dry_run", True)):
            return DesktopControlResult(
                True,
                False,
                f"Testlauf: {request.application} wurde nicht veraendert.",
            )
        if self.controller is None:
            return DesktopControlResult(
                False,
                False,
                "Fuer dieses System ist kein nativer App-Adapter aktiv.",
            )

        try:
            if request.action is DesktopAction.OPEN_APPLICATION:
                message = self.controller.open_application(request.application)
            elif request.action is DesktopAction.CLOSE_APPLICATION:
                message = self.controller.close_application(request.application)
            else:
                return DesktopControlResult(
                    False,
                    False,
                    "Diese Desktopaktion besitzt noch keinen Ausfuehrungsadapter.",
                )
        except (OSError, RuntimeError, ValueError) as exc:
            self._audit(request, "failed", str(exc))
            return DesktopControlResult(False, True, str(exc))

        self._audit(request, "completed", message)
        return DesktopControlResult(True, True, message)

    def _audit(self, request: DesktopControlRequest, status: str, message: str) -> None:
        if self.home is None:
            return
        path = self.home / "TrinityRuntime" / "audit" / "desktop_control.jsonl"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp": time.time(),
                "platform": platform.system(),
                "action": request.action.value,
                "application": request.application,
                "status": status,
                "message": message,
            }
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")
        except OSError:
            return
