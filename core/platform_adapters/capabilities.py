import importlib.util
import os
import platform
import shutil
from pathlib import Path
from typing import Iterable, Optional, Set


CAPABILITY_LABELS = {
    "mail_automation": "lokale Mail-Automation",
    "codex_cli": "lokale Codex CLI",
    "native_macos_speech": "native macOS-Spracherkennung",
    "powerpoint_automation": "PowerPoint-Automation",
    "speech_input": "Whisper-Spracherkennung",
    "speech_output": "Sprachausgabe",
}


def detect_capabilities(system: Optional[str] = None) -> Set[str]:
    """Return capabilities available on the current operating system."""
    system_name = system or platform.system()
    capabilities = set()

    if find_codex_executable():
        capabilities.add("codex_cli")

    if _module_available("faster_whisper") and _module_available("sounddevice"):
        capabilities.add("speech_input")

    if system_name == "Darwin":
        if shutil.which("say"):
            capabilities.add("speech_output")
        if shutil.which("osascript"):
            capabilities.update({"mail_automation", "powerpoint_automation"})
        if all(
            _module_available(name)
            for name in ("Foundation", "Speech", "AVFoundation")
        ):
            capabilities.add("native_macos_speech")
    elif system_name == "Windows":
        if shutil.which("powershell.exe") or shutil.which("powershell"):
            capabilities.add("speech_output")
        if _module_available("win32com"):
            capabilities.add("powerpoint_automation")

    return capabilities


def capability_message(missing: Iterable[str], system: Optional[str] = None) -> str:
    system_name = system or platform.system()
    labels = [CAPABILITY_LABELS.get(item, item) for item in sorted(missing)]
    joined = ", ".join(labels)

    if system_name == "Windows" and "mail_automation" in missing:
        return (
            "Die lokale Mail-Automation ist auf Windows noch nicht aktiviert. "
            "Das neue Outlook benötigt dafür eine Microsoft-Graph-Anmeldung; "
            "klassisches Outlook kann später optional über COM angebunden werden."
        )

    return f"Diese Funktion ist auf {system_name} nicht verfügbar: {joined}."


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def find_codex_executable() -> Optional[str]:
    """Locate Codex even when a desktop launcher has a minimal PATH."""
    for name in ("codex", "codex.exe", "codex.cmd"):
        found = shutil.which(name)
        if found:
            return found

    candidates = [
        Path("/opt/homebrew/bin/codex"),
        Path("/usr/local/bin/codex"),
        Path.home() / ".local" / "bin" / "codex",
    ]

    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.extend(
            [
                Path(appdata) / "npm" / "codex.cmd",
                Path(appdata) / "npm" / "codex.exe",
            ]
        )

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.extend(
            [
                Path(local_appdata) / "npm" / "codex.cmd",
                Path(local_appdata) / "Programs" / "Codex" / "codex.exe",
            ]
        )

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None
