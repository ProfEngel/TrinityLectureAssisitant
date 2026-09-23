"""Structured Microsoft Word control for macOS without UI coordinates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import platform
import subprocess


@dataclass(frozen=True)
class WordSelection:
    text: str

    @property
    def is_empty(self) -> bool:
        return not self.text.strip("\r\n\t ")


class MacOSWordController:
    """Use Word's AppleScript dictionary instead of keyboard automation."""

    application = "Microsoft Word"

    def create_document(self) -> str:
        return self._run(
            """
tell application "Microsoft Word"
    activate
    set docRef to make new document
    return name of docRef
end tell
"""
        )

    def insert_text(self, text: str) -> str:
        self._run(
            """
on run argv
    tell application "Microsoft Word"
        activate
        if (count of documents) is 0 then make new document
        type text selection text (item 1 of argv)
        return name of active document
    end tell
end run
""",
            text,
        )
        return "Der Text wurde an der aktuellen Cursorposition eingefuegt."

    def selection(self) -> WordSelection:
        text = self._run(
            """
tell application "Microsoft Word"
    if (count of documents) is 0 then error "Kein Word-Dokument ist geoeffnet."
    return content of selection
end tell
"""
        )
        return WordSelection(text=text)

    def replace_selection(self, text: str) -> str:
        self._require_selection()
        self._run(
            """
on run argv
    tell application "Microsoft Word"
        activate
        set content of selection to (item 1 of argv)
    end tell
end run
""",
            text,
        )
        return "Die markierte Auswahl wurde ersetzt."

    def format_selection(self, style: str) -> str:
        self._require_selection()
        scripts = {
            "bold": 'set bold of font object of selection to true',
            "italic": 'set italic of font object of selection to true',
            "normal": 'set style of selection to style normal',
            "heading1": 'set style of selection to style heading1',
            "heading2": 'set style of selection to style heading2',
            "title": 'set style of selection to style title',
            "subtitle": 'set style of selection to style subtitle',
            "bullets": 'set style of selection to style list bullet',
            "numbering": 'set style of selection to style list number',
        }
        command = scripts.get(style)
        if command is None:
            raise ValueError(f"Unbekanntes Word-Format: {style}")
        self._run(
            f"""
tell application "Microsoft Word"
    activate
    {command}
end tell
"""
        )
        return "Die markierte Auswahl wurde formatiert."

    def save_as(self, path: str | Path) -> str:
        target = Path(path).expanduser().resolve()
        self._run(
            """
on run argv
    tell application "Microsoft Word"
        activate
        if (count of documents) is 0 then error "Kein Word-Dokument ist geoeffnet."
        save as active document file name (item 1 of argv) file format format document default
    end tell
end run
""",
            str(target),
        )
        return str(target)

    def open_folder(self, path: str | Path) -> None:
        target = Path(path).expanduser().resolve()
        result = subprocess.run(
            ["/usr/bin/open", str(target)],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "unbekannter Fehler").strip()
            raise RuntimeError(f"Finder konnte den Ordner nicht oeffnen: {detail}")

    def _require_selection(self) -> WordSelection:
        selection = self.selection()
        if selection.is_empty:
            raise ValueError(
                "Bitte markiere zuerst den Text in Word, den ich bearbeiten soll."
            )
        return selection

    @staticmethod
    def _run(script: str, *arguments: str) -> str:
        result = subprocess.run(
            ["/usr/bin/osascript", "-", *arguments],
            input=script,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "unbekannter Fehler").strip()
            raise RuntimeError(f"Microsoft Word konnte die Aktion nicht ausfuehren: {detail}")
        return result.stdout.rstrip("\r\n")


def create_word_controller(platform_name: str | None = None):
    host = platform_name or platform.system()
    if host == "Darwin":
        return MacOSWordController()
    return None
