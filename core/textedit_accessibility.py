"""Read and select exact ranges in accessible foreground text fields.

The native helper runs inside the already-authorized Trinity process; no new
background app or blanket document automation permission is required.
"""

from __future__ import annotations

import ctypes
import json
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _library():
    home = Path(__file__).resolve().parent.parent
    source = home / "tools" / "textedit_ax.swift"
    destination = home / "TrinityRuntime" / "bin" / "libtrinity_textedit_ax.dylib"
    if not destination.exists() or destination.stat().st_mtime < source.stat().st_mtime:
        destination.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["xcrun", "swiftc", "-emit-library", str(source), "-o", str(destination)],
            capture_output=True, text=True, timeout=45, check=False,
        )
        if result.returncode:
            raise RuntimeError(f"TextEdit-Bedienungshilfe konnte nicht gebaut werden: {result.stderr[:500]}")
    library = ctypes.CDLL(str(destination))
    library.trinity_textedit_inspect.argtypes = []
    library.trinity_textedit_inspect.restype = ctypes.c_void_p
    library.trinity_textedit_select.argtypes = [ctypes.c_int32, ctypes.c_int32]
    library.trinity_textedit_select.restype = ctypes.c_int32
    library.trinity_textedit_free.argtypes = [ctypes.c_void_p]
    library.trinity_textedit_free.restype = None
    library.trinity_focused_app_pid.argtypes = []
    library.trinity_focused_app_pid.restype = ctypes.c_int32
    library.trinity_ax_trusted.argtypes = []
    library.trinity_ax_trusted.restype = ctypes.c_int32
    library.trinity_ax_request.argtypes = []
    library.trinity_ax_request.restype = ctypes.c_int32
    library.trinity_focus_diagnostics.argtypes = []
    library.trinity_focus_diagnostics.restype = ctypes.c_void_p
    return library


def focused_app_pid():
    return int(_library().trinity_focused_app_pid()) or None


def ax_trusted():
    return bool(_library().trinity_ax_trusted())


def request_ax_access():
    """Ask from Trinity itself, only following an explicit dictation start."""
    return bool(_library().trinity_ax_request())


def focus_diagnostics():
    library = _library()
    pointer = library.trinity_focus_diagnostics()
    if not pointer:
        return {}
    try:
        return json.loads(ctypes.string_at(pointer).decode("utf-8"))
    finally:
        library.trinity_textedit_free(pointer)


def inspect_textedit() -> dict:
    library = _library()
    pointer = library.trinity_textedit_inspect()
    if not pointer:
        raise RuntimeError("Kein zugängliches Textfeld fokussiert oder Bedienungshilfen fehlen.")
    try:
        return json.loads(ctypes.string_at(pointer).decode("utf-8"))
    finally:
        library.trinity_textedit_free(pointer)


def select_textedit_range(start: int, length: int) -> None:
    if start < 0 or length < 0 or start + length > 2_147_483_647:
        raise ValueError("Ungültiger TextEdit-Bereich.")
    error = _library().trinity_textedit_select(start, length)
    if error:
        raise RuntimeError(f"TextEdit-Bereich konnte nicht ausgewählt werden ({error}).")
