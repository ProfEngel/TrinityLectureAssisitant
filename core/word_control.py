"""Policy and path checks for structured Microsoft Word operations."""

from __future__ import annotations

import json
from pathlib import Path
import platform
import time

from policy_engine import PolicyEngine


class WordControlService:
    def __init__(self, config: dict, controller, home: str | Path):
        self.config = config or {}
        self.controller = controller
        self.home = Path(home).resolve()
        self.policy = PolicyEngine()

    def available(self) -> tuple[bool, str]:
        if not bool(self.config.get("enabled", False)):
            return False, "Desktopsteuerung ist deaktiviert."
        allowed = {
            str(item).strip().casefold()
            for item in self.config.get("allowed_applications", [])
        }
        if "microsoft word" not in allowed:
            return False, "Microsoft Word ist nicht fuer die Desktopsteuerung freigegeben."
        if self.controller is None:
            return False, "Der strukturierte Word-Adapter ist auf diesem System noch nicht verfuegbar."
        return True, ""

    def modify(self, action: str, operation) -> str:
        available, reason = self.available()
        if not available:
            raise RuntimeError(reason)
        policy = self.policy.decide(action)
        if not policy.allowed:
            raise RuntimeError(policy.reason)
        if bool(self.config.get("dry_run", True)):
            return "Testlauf: Das Word-Dokument wurde nicht veraendert."
        result = operation()
        self._audit(action, "completed", str(result))
        return str(result)

    def save(self, target: str | Path, allowed_roots: list[str | Path]) -> str:
        available, reason = self.available()
        if not available:
            raise RuntimeError(reason)
        path = Path(target).expanduser().resolve()
        roots = [Path(item).expanduser().resolve() for item in allowed_roots if str(item)]
        if not PolicyEngine.path_allowed(str(path), [str(item) for item in roots]):
            raise ValueError("Der Zielpfad liegt ausserhalb der freigegebenen Ablage.")
        if path.exists():
            raise FileExistsError(
                "Die Datei existiert bereits. Bitte nenne einen anderen Dateinamen; "
                "Trinity ueberschreibt nicht still."
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        if bool(self.config.get("dry_run", True)):
            return "Testlauf: Das Word-Dokument wurde nicht gespeichert."
        result = self.controller.save_as(path)
        self._audit("desktop_save_document", "completed", result, path=str(path))
        return result

    def _audit(self, action: str, status: str, message: str, path: str = "") -> None:
        target = self.home / "TrinityRuntime" / "audit" / "desktop_control.jsonl"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp": time.time(),
                "platform": platform.system(),
                "action": action,
                "application": "Microsoft Word",
                "status": status,
                "message": message,
            }
            if path:
                entry["path"] = path
            with target.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")
        except OSError:
            return
