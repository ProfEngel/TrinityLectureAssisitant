"""Health checks and conservative repairs for Trinity installations."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from configuration import (
    ensure_support_files,
    load_config,
    save_config,
)
from ui_modes import resolve_ui_modes


def _result(level, name, message):
    return {"level": level, "name": name, "message": message}


def _module_available(name):
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _ssl_status(import_module=__import__):
    try:
        ssl_module = import_module("ssl")
        return True, ssl_module.OPENSSL_VERSION
    except (ImportError, OSError, AttributeError) as exc:
        return False, str(exc)


def run_doctor(trinity_home, fix=False, online=False):
    home = Path(trinity_home)
    core = home / "core"
    config_path = core / "config.json"
    results = []

    version_ok = (3, 9) <= sys.version_info[:2] < (3, 13)
    results.append(
        _result(
            "OK" if version_ok else "ERROR",
            "Python",
            sys.version.split()[0]
            if version_ok
            else "Trinity benötigt Python 3.9 bis 3.12.",
        )
    )
    ssl_ok, ssl_message = _ssl_status()
    results.append(
        _result(
            "OK" if ssl_ok else "ERROR",
            "SSL",
            ssl_message
            if ssl_ok
            else f"Python-SSL ist nicht verfügbar: {ssl_message}",
        )
    )

    if fix:
        created = ensure_support_files(home)
        if created:
            results.append(
                _result(
                    "FIXED",
                    "Dateien",
                    f"{len(created)} fehlende Datei(en) oder Ordner angelegt.",
                )
            )

    if not config_path.exists():
        if fix:
            save_config(config_path, load_config(config_path))
            results.append(
                _result("FIXED", "Konfiguration", "config.json wurde angelegt.")
            )
        else:
            results.append(
                _result(
                    "ERROR",
                    "Konfiguration",
                    "config.json fehlt. Nutze `trinity onboarding` oder `doctor --fix`.",
                )
            )
            return results

    try:
        raw_config = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(raw_config, dict):
            raise ValueError("Die Wurzel muss ein JSON-Objekt sein.")
        config = load_config(config_path)
        results.append(_result("OK", "Konfiguration", "JSON ist lesbar."))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        results.append(_result("ERROR", "Konfiguration", str(exc)))
        return results

    system = config.get("system", {})
    resolved_modes = resolve_ui_modes(system)
    configured_surface = any(
        bool(system.get(key))
        for key in (
            "eyes_ui_enabled",
            "classic_ui_enabled",
            "terminal_cli_enabled",
            "show_terminal",
        )
    )
    if not configured_surface:
        if fix:
            system["terminal_cli_enabled"] = True
            system["show_terminal"] = True
            save_config(config_path, config)
            results.append(
                _result(
                    "FIXED",
                    "Oberflächen",
                    "Terminal-CLI als sicheren Fallback aktiviert.",
                )
            )
        else:
            results.append(
                _result(
                    "WARN",
                    "Oberflächen",
                    "Keine Oberfläche konfiguriert; Laufzeit erzwingt Terminal-CLI.",
                )
            )
    else:
        active = ", ".join(name for name, enabled in resolved_modes.items() if enabled)
        results.append(_result("OK", "Oberflächen", active))

    gui_required = resolved_modes["eyes"] or resolved_modes["classic"]
    gui_modules = ("PySide6", "PySide6.QtWebEngineWidgets")
    missing_gui = [name for name in gui_modules if not _module_available(name)]
    if gui_required and missing_gui:
        results.append(
            _result(
                "ERROR",
                "Desktop-UI",
                "Fehlende Module: " + ", ".join(missing_gui),
            )
        )
    elif gui_required:
        results.append(_result("OK", "Desktop-UI", "PySide6 ist verfügbar."))

    active_slot = config.get("llm", {}).get("active_slot", "local")
    provider = config.get("llm", {}).get(active_slot, {})
    if provider.get("url") and provider.get("model"):
        results.append(
            _result("OK", "LLM", f"Provider `{active_slot}` ist konfiguriert.")
        )
    else:
        results.append(
            _result(
                "WARN",
                "LLM",
                "Beim aktiven Provider fehlen URL oder Modell.",
            )
        )

    codex = config.get("codex", {})
    if codex.get("enabled"):
        executable = codex.get("executable", "codex")
        found = Path(executable).is_file() if os.path.dirname(executable) else None
        if found is None:
            from shutil import which

            found = which(executable)
        results.append(
            _result(
                "OK" if found else "WARN",
                "Codex",
                str(found) if found else "Codex CLI wurde nicht gefunden.",
            )
        )

    opencode = config.get("opencode", {})
    if opencode.get("enabled"):
        executable = opencode.get("executable", "opencode")
        found = Path(executable).is_file() if os.path.dirname(executable) else None
        if found is None:
            from shutil import which

            found = which(executable)
        results.append(
            _result(
                "OK" if found else "WARN",
                "OpenCode",
                str(found) if found else "OpenCode CLI wurde nicht gefunden.",
            )
        )

    for directory in ("memory", "logs"):
        path = home / directory
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".trinity-write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            results.append(_result("OK", directory, "Schreibbar."))
        except OSError as exc:
            results.append(_result("ERROR", directory, str(exc)))

    if (home / ".git").is_dir():
        if online:
            fetch = subprocess.run(
                ["git", "fetch", "origin", "main"],
                cwd=str(home),
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            if fetch.returncode != 0:
                results.append(
                    _result(
                        "WARN",
                        "Aktualität",
                        (fetch.stderr or fetch.stdout).strip()[:300],
                    )
                )
            else:
                local = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(home),
                    capture_output=True,
                    text=True,
                    check=False,
                ).stdout.strip()
                remote = subprocess.run(
                    ["git", "rev-parse", "origin/main"],
                    cwd=str(home),
                    capture_output=True,
                    text=True,
                    check=False,
                ).stdout.strip()
                results.append(
                    _result(
                        "OK" if local == remote else "WARN",
                        "Aktualität",
                        "Installation ist aktuell."
                        if local == remote
                        else "Eine neuere Version liegt auf origin/main.",
                    )
                )
        else:
            results.append(
                _result(
                    "OK",
                    "Git",
                    "Repository erkannt; `doctor --online` prüft origin/main.",
                )
            )

    return results


def doctor_exit_code(results):
    return 1 if any(item["level"] == "ERROR" for item in results) else 0
