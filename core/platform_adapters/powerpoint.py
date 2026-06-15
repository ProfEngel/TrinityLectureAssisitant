import platform
import shutil
import subprocess
from typing import Optional, Tuple


MACOS_COMMANDS = {
    "start": (
        'tell application "Microsoft PowerPoint" to run slide show '
        "slide show settings of active presentation"
    ),
    "stop": (
        'tell application "Microsoft PowerPoint" to exit slide show '
        "slide show view of slide show window 1"
    ),
    "previous": (
        'tell application "Microsoft PowerPoint" to go to previous slide '
        "slide show view of slide show window 1"
    ),
    "next": (
        'tell application "Microsoft PowerPoint" to go to next slide '
        "slide show view of slide show window 1"
    ),
}


class PowerPointController:
    def is_available(self) -> bool:
        return False

    def perform(self, action: str) -> Tuple[bool, str]:
        return False, "PowerPoint-Automation ist auf diesem System nicht verfügbar."


class MacOSPowerPointController(PowerPointController):
    def is_available(self) -> bool:
        return shutil.which("osascript") is not None

    def perform(self, action: str) -> Tuple[bool, str]:
        command = MACOS_COMMANDS.get(action)
        if not command:
            return False, f"Unbekannte PowerPoint-Aktion: {action}"
        if not self.is_available():
            return False, "Der macOS-Befehl osascript wurde nicht gefunden."

        result = subprocess.run(
            ["osascript", "-e", command],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode != 0:
            return False, (result.stderr or result.stdout).strip()
        return True, ""


class WindowsPowerPointController(PowerPointController):
    def is_available(self) -> bool:
        try:
            import win32com.client  # noqa: F401
        except ImportError:
            return False
        return True

    def perform(self, action: str) -> Tuple[bool, str]:
        if not self.is_available():
            return False, "pywin32 ist nicht installiert."

        pythoncom = None
        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            app = win32com.client.Dispatch("PowerPoint.Application")
            if action == "start":
                if app.Presentations.Count < 1:
                    return False, "In PowerPoint ist keine Präsentation geöffnet."
                app.ActivePresentation.SlideShowSettings.Run()
            else:
                if app.SlideShowWindows.Count < 1:
                    return False, "In PowerPoint läuft aktuell keine Bildschirmpräsentation."
                view = app.SlideShowWindows(1).View
                if action == "next":
                    view.Next()
                elif action == "previous":
                    view.Previous()
                elif action == "stop":
                    view.Exit()
                else:
                    return False, f"Unbekannte PowerPoint-Aktion: {action}"
        except Exception as exc:
            return False, str(exc)
        finally:
            if pythoncom is not None:
                pythoncom.CoUninitialize()
        return True, ""


def create_powerpoint_controller(
    system: Optional[str] = None,
) -> PowerPointController:
    system_name = system or platform.system()
    if system_name == "Darwin":
        return MacOSPowerPointController()
    if system_name == "Windows":
        return WindowsPowerPointController()
    return PowerPointController()
