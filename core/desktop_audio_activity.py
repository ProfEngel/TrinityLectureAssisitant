"""Process-backed indicators for desktop audio, independent of UI animation state."""

import os
import sys
from pathlib import Path


MARKERS = {
    "microphone": "desktop_microphone.ready",
    "speech": "desktop_speech.ready",
    "eve": "desktop_eve_audio.ready",
}


def mark_audio_active(home, source, pid=None):
    path = Path(home) / "TrinityRuntime" / "voice" / MARKERS[source]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(pid or os.getpid()), encoding="utf-8")
    except OSError:
        pass


def clear_audio_active(home, source):
    path = Path(home) / "TrinityRuntime" / "voice" / MARKERS[source]
    try:
        if path.read_text(encoding="utf-8").strip() == str(os.getpid()):
            path.unlink(missing_ok=True)
    except OSError:
        pass


def desktop_audio_active(home):
    for name in MARKERS.values():
        path = Path(home) / "TrinityRuntime" / "voice" / name
        try:
            pid = int(path.read_text(encoding="utf-8").strip())
            if pid <= 1:
                continue
            if _process_is_alive(pid):
                return True
        except PermissionError:
            # A running process we cannot inspect must not look like a muted mic.
            return True
        except (OSError, ValueError):
            continue
    return False


def _process_is_alive(pid):
    # os.kill(pid, 0) is a POSIX probe, but can terminate a process on Windows.
    if sys.platform == "win32":
        return _windows_process_is_alive(pid)
    os.kill(pid, 0)
    return True


def _windows_process_is_alive(pid):
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION only
    if not handle:
        return ctypes.get_last_error() == 5  # Access denied: conservatively active.
    try:
        code = wintypes.DWORD()
        return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
    finally:
        kernel.CloseHandle(handle)
