"""Native application lifecycle adapters without coordinate automation."""

from __future__ import annotations

import platform
import subprocess


class MacOSApplicationController:
    """Open and gracefully quit trusted macOS applications."""

    def open_application(self, application: str) -> str:
        result = subprocess.run(
            ["/usr/bin/open", "-a", application],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "unbekannter Fehler").strip()
            raise RuntimeError(f"{application} konnte nicht geoeffnet werden: {detail}")
        return f"{application} wurde geoeffnet."

    def close_application(self, application: str) -> str:
        trusted_name = application.replace("\\", "\\\\").replace('"', '\\"')
        if application == "Finder":
            script = 'tell application "Finder" to close every window'
            success_message = "Alle Finder-Fenster wurden geschlossen."
        else:
            script = f'tell application "{trusted_name}" to quit'
            success_message = (
                f"{application} wurde zum Beenden aufgefordert. "
                "Ein Dialog fuer ungespeicherte Dokumente bleibt sichtbar."
            )
        result = subprocess.run(
            [
                "/usr/bin/osascript",
                "-e",
                script,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "unbekannter Fehler").strip()
            raise RuntimeError(f"{application} konnte nicht beendet werden: {detail}")
        return success_message


def create_application_controller(platform_name: str | None = None):
    host = platform_name or platform.system()
    if host == "Darwin":
        return MacOSApplicationController()
    return None
