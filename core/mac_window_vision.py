"""Explicit, consent-based capture of the foreground macOS application window."""

from __future__ import annotations

import os
import io
import subprocess
import tempfile
from pathlib import Path


def foreground_pid() -> int | None:
    # NSWorkspace can lag behind a tray popup in a long-lived Qt process.
    # The accessibility focus reflects the actual currently selected app.
    try:
        try:
            from .textedit_accessibility import focused_app_pid
        except ImportError:
            from textedit_accessibility import focused_app_pid
        pid = focused_app_pid()
        if pid:
            return pid
    except Exception:
        pass
    try:
        from AppKit import NSWorkspace

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return int(app.processIdentifier()) if app else None
    except Exception:
        return None


def is_textedit_pid(pid: int | None) -> bool:
    """Only the known TextEdit bundle is allowed for voice-driven writing."""
    if not pid:
        return False
    try:
        from AppKit import NSRunningApplication

        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(int(pid))
        return bool(app and app.bundleIdentifier() == "com.apple.TextEdit")
    except Exception:
        return False


def choose_window(windows, pid: int | None):
    """Window lists are front-to-back; never silently capture our own UI."""
    if not pid or pid == os.getpid():
        return None
    for item in windows:
        bounds = item.get("kCGWindowBounds") or {}
        if (item.get("kCGWindowOwnerPID") == pid
                and item.get("kCGWindowLayer") == 0
                and bounds.get("Width", 0) >= 200
                and bounds.get("Height", 0) >= 150):
            return item
    return None


def window_descriptor(pid: int | None):
    try:
        import Quartz
    except ImportError as exc:
        raise RuntimeError("macOS-Fenstererfassung ist nicht verfügbar (PyObjC/Quartz fehlt).") from exc
    windows = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID,
    )
    return choose_window(windows, pid)


def capture_window(pid: int | None) -> tuple[Path, str]:
    item = window_descriptor(pid)
    if not item:
        raise RuntimeError("Kein aktives Fenster gefunden. Bitte zuerst das gewünschte Programm öffnen.")
    descriptor, name = tempfile.mkstemp(prefix="trinity-window-", suffix=".png")
    os.close(descriptor)
    path = Path(name)
    try:
        result = subprocess.run(
            ["/usr/sbin/screencapture", "-x", "-l", str(item["kCGWindowNumber"]), str(path)],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if result.returncode or not path.is_file() or path.stat().st_size < 1024:
            raise RuntimeError("Fensteraufnahme fehlgeschlagen. Bitte Trinity unter Datenschutz > Bildschirmaufnahme erlauben.")
        title = str(item.get("kCGWindowName") or item.get("kCGWindowOwnerName") or "aktives Fenster")
        return path, title
    except Exception:
        path.unlink(missing_ok=True)
        raise


def capture_window_jpeg(pid: int | None) -> tuple[bytes, str]:
    """Capture just one window and bound the image sent to the remote server."""
    from PIL import Image

    path, title = capture_window(pid)
    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail((1600, 1600))
            for quality in (78, 65, 50):
                output = io.BytesIO()
                image.save(output, format="JPEG", quality=quality, optimize=True)
                if output.tell() <= 2 * 1024 * 1024:
                    return output.getvalue(), title
            raise RuntimeError("Fensterbild lässt sich nicht unter 2 MB verkleinern.")
    finally:
        path.unlink(missing_ok=True)


def accessibility_available(*, prompt=False) -> bool:
    """Check before trying to control another app; prompt only on user action."""
    import Quartz

    if Quartz.CGPreflightPostEventAccess():
        return True
    return bool(Quartz.CGRequestPostEventAccess()) if prompt else False


def target_still_selected(pid: int, window_id: int) -> bool:
    item = window_descriptor(pid)
    return bool(
        foreground_pid() == pid and item
        and int(item.get("kCGWindowNumber") or 0) == window_id
    )


def paste_text_at_cursor(text: str) -> None:
    """Paste plain text into the *already focused* target; never chooses a field."""
    import AppKit
    import Quartz

    if not accessibility_available():
        raise RuntimeError("Bedienungshilfen-Zugriff für Trinity fehlt.")
    if not text or len(text) > 50_000:
        raise ValueError("Einfügetext muss zwischen 1 und 50.000 Zeichen lang sein.")
    pasteboard = AppKit.NSPasteboard.generalPasteboard()
    pasteboard.clearContents()
    if not pasteboard.setString_forType_(text, AppKit.NSPasteboardTypeString):
        raise RuntimeError("Text konnte nicht in die Zwischenablage gelegt werden.")
    # ANSI V is virtual key code 9 on macOS; Command+V is app-independent.
    for down in (True, False):
        event = Quartz.CGEventCreateKeyboardEvent(None, 9, down)
        Quartz.CGEventSetFlags(event, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def delete_selected_text() -> None:
    """Delete only the current selection after the caller verifies its range."""
    import Quartz

    if not accessibility_available():
        raise RuntimeError("Bedienungshilfen-Zugriff für Trinity fehlt.")
    for down in (True, False):
        event = Quartz.CGEventCreateKeyboardEvent(None, 51, down)  # ANSI Delete
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
