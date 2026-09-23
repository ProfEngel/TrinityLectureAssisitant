"""Open and gracefully close a small allowlist of desktop applications."""

from __future__ import annotations

import json
import re
from pathlib import Path

from desktop_control import DesktopAction, DesktopControlRequest, DesktopControlService
from platform_adapters.desktop_applications import create_application_controller


PRIORITY = 120
ROOT = Path(__file__).resolve().parents[2]
LAST_APPLICATION_PATH = ROOT / "TrinityRuntime" / "desktop_control" / "last_application.json"

APPLICATIONS = {
    "Microsoft Word": ("microsoft word", "word"),
    "Microsoft Excel": ("microsoft excel", "excel"),
    "OpenCode": ("opencode", "open code"),
    "ChatGPT": ("chatgpt", "chat gpt"),
    "Mail": ("apple mail", "mail app", "mail"),
    "Finder": ("finder",),
    "Google Chrome": ("google chrome", "chrome"),
}
OPEN_MARKERS = ("öffne", "oeffne", "starte", "mach auf")
CLOSE_MARKERS = ("schließe", "schliesse", "beende", "mach zu")
PRONOUN_TARGETS = ("diese app", "die app", "diese anwendung", "das programm")


def can_handle(query: str) -> bool:
    return _intent(query) is not None


def execute(query: str, context: dict | None = None) -> dict:
    intent = _intent(query)
    if intent is None:
        return _answer("Ich konnte keine freigegebene App-Aktion erkennen.")
    action, application = intent
    config = dict((context or {}).get("full_config", {}).get("desktop_control", {}))
    service = DesktopControlService(
        config=config,
        controller=create_application_controller(),
        home=ROOT,
    )
    result = service.execute(
        DesktopControlRequest(action=action, application=application),
        confirmed=True,
    )
    if result.success and result.executed:
        if action is DesktopAction.OPEN_APPLICATION:
            _remember_application(application)
        elif _last_application() == application:
            LAST_APPLICATION_PATH.unlink(missing_ok=True)
    return _answer(result.message)


def _intent(query: str):
    text = " ".join(str(query or "").casefold().split())
    action = None
    if any(marker in text for marker in CLOSE_MARKERS):
        action = DesktopAction.CLOSE_APPLICATION
    elif any(marker in text for marker in OPEN_MARKERS):
        action = DesktopAction.OPEN_APPLICATION
    if action is None:
        return None

    for application, aliases in APPLICATIONS.items():
        if any(_contains_alias(text, alias) for alias in aliases):
            return action, application
    if action is DesktopAction.CLOSE_APPLICATION and any(
        marker in text for marker in PRONOUN_TARGETS
    ):
        application = _last_application()
        if application in APPLICATIONS:
            return action, application
    return None


def _contains_alias(text: str, alias: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text))


def _remember_application(application: str) -> None:
    LAST_APPLICATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAST_APPLICATION_PATH.write_text(
        json.dumps({"application": application}, ensure_ascii=True),
        encoding="utf-8",
    )


def _last_application() -> str:
    try:
        value = json.loads(LAST_APPLICATION_PATH.read_text(encoding="utf-8"))
        return str(value.get("application") or "")
    except (OSError, ValueError, TypeError):
        return ""


def _answer(message: str) -> dict:
    return {
        "has_payload": False,
        "html_payload": "",
        "search_context": "",
        "direct_answer": message,
    }
