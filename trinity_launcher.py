import subprocess
import sys
import time
import os
from datetime import datetime
from html import escape

from core.ui_modes import resolve_ui_modes


def _trinity_subprocess_env(environment=None):
    env = dict(environment or os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def _read_ui_modes(config_file, force_terminal=False, suppress_terminal=False):
    try:
        import json
        with open(config_file, "r", encoding="utf-8") as config_handle:
            config = json.load(config_handle)
        system_config = config.get("system", {})
    except Exception:
        system_config = {}
    return resolve_ui_modes(
        system_config,
        force_terminal=force_terminal,
        suppress_terminal=suppress_terminal,
    )


def _read_show_terminal(config_file):
    return _read_ui_modes(config_file)["terminal"]


def _console_python_executable(executable=None, platform_name=None):
    executable = executable or sys.executable
    host = platform_name or sys.platform
    if host == "win32" and os.path.basename(executable).casefold() == "pythonw.exe":
        console_python = os.path.join(os.path.dirname(executable), "python.exe")
        if os.path.isfile(console_python):
            return console_python
    return executable


def _requested_surface(arguments=None):
    arguments = list(arguments or sys.argv)
    if "--surface" not in arguments:
        return None
    try:
        return arguments[arguments.index("--surface") + 1]
    except IndexError:
        return None


def _graphical_session_available(platform_name=None, environment=None):
    host = platform_name or sys.platform
    environment = environment or os.environ
    if host in {"darwin", "win32"}:
        return True
    return bool(environment.get("DISPLAY") or environment.get("WAYLAND_DISPLAY"))


def _terminate(process):
    if process is not None and process.poll() is None:
        process.terminate()


def _log_message(log_handle, message):
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
    print(line)
    log_handle.write(line + "\n")
    log_handle.flush()


def _tail_text(path, max_lines=80):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except OSError:
        return ""
    return "".join(lines[-max_lines:]).strip()


def _show_runtime_error(base_dir, return_code, runtime_log_path=None):
    payload_file = os.path.join(base_dir, "core", "payload.html")
    state_file = os.path.join(base_dir, "core", "state.txt")
    logs_path = escape(os.path.join(base_dir, "logs"))
    runtime_tail = _tail_text(runtime_log_path or os.path.join(base_dir, "logs", "runtime.log"))
    runtime_tail_html = ""
    if runtime_tail:
        runtime_tail_html = (
            "<h3>Letzte Laufzeitmeldung</h3>"
            "<pre style='white-space:pre-wrap;max-height:360px;overflow:auto;"
            "background:rgba(0,0,0,0.28);padding:12px;border-radius:10px;'>"
            f"{escape(runtime_tail)}</pre>"
        )
    payload = f"""
    <!-- KEEP_OPEN -->
    <h2>Trinity-Kern wurde beendet</h2>
    <p>Die Oberfläche bleibt für Einstellungen und Diagnose geöffnet.</p>
    <p>Fehlercode: <code>{return_code}</code></p>
    <p>Protokolle: <code>{logs_path}</code></p>
    {runtime_tail_html}
    <p>Unter Windows bitte zunächst den Chatmodus verwenden und die experimentelle
    Spracheingabe erst nach erfolgreichem LLM-Test aktivieren.</p>
    """
    try:
        with open(payload_file, "w", encoding="utf-8") as payload_handle:
            payload_handle.write(payload)
        with open(state_file, "w", encoding="utf-8") as state_handle:
            state_handle.write("reporting")
    except OSError:
        pass


def launch_trinity():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print("🧞‍♀️ Starte Trinity System...")
    
    # 1. Pfade definieren
    base_dir = os.path.dirname(os.path.abspath(__file__))
    eyes_ui_script = os.path.join(base_dir, "trinity_app.py")
    classic_ui_script = os.path.join(base_dir, "trinity_classic.py")
    console_script = os.path.join(base_dir, "trinity_console.py")
    ear_script = os.path.join(base_dir, "core", "transcriber.py")
    config_file = os.path.join(base_dir, "core", "config.json")
    settings_script = os.path.join(base_dir, "core", "settings_ui.py")
    cli_script = os.path.join(base_dir, "trinity_cli.py")
    logs_dir = os.path.join(base_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    # 1.5 Prüfen ob config existiert (Erster Start)
    if not os.path.exists(config_file):
        print("Erstes Setup erkannt. Öffne Konfiguration...")
        requested_surface = _requested_surface()
        if requested_surface == "terminal" or not _graphical_session_available():
            subprocess.run(
                [sys.executable, cli_script, "onboarding"],
                env=_trinity_subprocess_env(),
            )
        else:
            subprocess.run(
                [sys.executable, settings_script],
                env=_trinity_subprocess_env(),
            )
        if not os.path.exists(config_file):
            print("Konfiguration abgebrochen. Beende Trinity.")
            sys.exit(1)

    diagnostic_mode = "--diagnostic" in sys.argv
    no_terminal = "--no-terminal" in sys.argv
    ui_modes = _read_ui_modes(
        config_file,
        force_terminal=diagnostic_mode,
        suppress_terminal=no_terminal,
    )
    surface = _requested_surface()
    surface_modes = {
        "classic": {"eyes": False, "classic": True, "terminal": False},
        "eyes": {"eyes": True, "classic": False, "terminal": False},
        "terminal": {"eyes": False, "classic": False, "terminal": True},
        "all": {"eyes": True, "classic": True, "terminal": True},
    }
    if surface in surface_modes:
        ui_modes = surface_modes[surface]
    show_terminal = ui_modes["terminal"]
    child_env = _trinity_subprocess_env()

    with open(
        os.path.join(logs_dir, "launcher.log"), "a", encoding="utf-8"
    ) as launcher_log, open(
        os.path.join(logs_dir, "runtime.log"), "a", encoding="utf-8"
    ) as runtime_log, open(
        os.path.join(logs_dir, "ui.log"), "a", encoding="utf-8"
    ) as ui_log:
        _log_message(
            launcher_log,
            "Starte Trinity-Laufzeit mit Oberflächen: "
            + ", ".join(name for name, enabled in ui_modes.items() if enabled),
        )
        console_flags = 0
        if sys.platform == "win32" and show_terminal:
            console_flags = subprocess.CREATE_NEW_CONSOLE

        if show_terminal:
            ear_process = subprocess.Popen(
                [
                    _console_python_executable(),
                    "-u",
                    console_script,
                    "--runtime",
                    ear_script,
                ],
                creationflags=console_flags,
                env=child_env,
            )
        else:
            ear_process = subprocess.Popen(
                [sys.executable, "-u", ear_script],
                stdout=runtime_log,
                stderr=subprocess.STDOUT,
                creationflags=0,
                env=child_env,
            )

        ui_processes = {}
        if ui_modes["eyes"]:
            ui_processes["Augen-UI"] = subprocess.Popen(
                [sys.executable, "-u", eyes_ui_script],
                stdout=None if show_terminal else ui_log,
                stderr=None if show_terminal else subprocess.STDOUT,
                creationflags=0,
                env=child_env,
            )
        if ui_modes["classic"]:
            ui_processes["Classic-UI"] = subprocess.Popen(
                [sys.executable, "-u", classic_ui_script],
                stdout=None if show_terminal else ui_log,
                stderr=None if show_terminal else subprocess.STDOUT,
                creationflags=0,
                env=child_env,
            )

        try:
            while True:
                for name, process in list(ui_processes.items()):
                    if process.poll() is not None:
                        _log_message(
                            launcher_log,
                            f"{name} wurde mit Code {process.returncode} beendet.",
                        )
                        del ui_processes[name]

                if (ui_modes["eyes"] or ui_modes["classic"]) and not ui_processes:
                    break
                if ear_process is not None and ear_process.poll() is not None:
                    return_code = ear_process.returncode
                    _log_message(
                        launcher_log,
                        "Kernprozess wurde mit Code "
                        f"{return_code} beendet. Die Oberfläche bleibt "
                        "für Einstellungen und Diagnose geöffnet.",
                    )
                    if return_code != 0 and ui_processes:
                        _show_runtime_error(base_dir, return_code, runtime_log.name)
                    ear_process = None
                    if return_code == 0 or not ui_processes:
                        break
                time.sleep(1)
        except KeyboardInterrupt:
            _log_message(launcher_log, "Trinity wurde manuell beendet.")
        finally:
            for process in ui_processes.values():
                _terminate(process)
            _terminate(ear_process)
            _log_message(launcher_log, "Trinity ist schlafen gegangen.")

if __name__ == "__main__":
    launch_trinity()
