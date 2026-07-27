import subprocess
import sys
import time
import os
import signal
import webbrowser
from datetime import datetime
from html import escape

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.join(BASE_DIR, "core")
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

from core.configuration import load_config
from core.canvas_manager import CanvasManager
from core.runtime_reset import reset_operational_memory
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


def _read_companion_config(config_file):
    try:
        return load_config(config_file).get("companion", {})
    except Exception:
        return {}


def _read_server_config(config_file):
    try:
        return load_config(config_file).get("server", {})
    except Exception:
        return {}


def _read_workbench_config(config_file):
    try:
        return load_config(config_file).get("workbench", {})
    except Exception:
        return {}


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


def _request_graceful_shutdown(_signum, _frame):
    """Move external termination through the launcher's cleanup block."""

    raise KeyboardInterrupt


def _acquire_launcher_lock(base_dir, platform_name=None):
    """Hold one OS-level lock so a second app click cannot duplicate Trinity."""

    runtime_dir = os.path.join(base_dir, "TrinityRuntime")
    os.makedirs(runtime_dir, exist_ok=True)
    lock_handle = open(os.path.join(runtime_dir, "launcher.lock"), "a+b")
    host = platform_name or sys.platform
    try:
        if host == "win32":
            import msvcrt

            lock_handle.seek(0, os.SEEK_END)
            if lock_handle.tell() == 0:
                lock_handle.write(b"0")
                lock_handle.flush()
            lock_handle.seek(0)
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, ImportError):
        lock_handle.close()
        return None
    return lock_handle


def _release_launcher_lock(lock_handle, platform_name=None):
    if lock_handle is None or lock_handle.closed:
        return
    host = platform_name or sys.platform
    try:
        if host == "win32":
            import msvcrt

            lock_handle.seek(0)
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    except (OSError, ImportError):
        pass
    lock_handle.close()


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
    launcher_lock = _acquire_launcher_lock(base_dir)
    if launcher_lock is None:
        print("Trinity läuft bereits. Der zweite Start wird beendet.")
        return
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _request_graceful_shutdown)
    eyes_ui_script = os.path.join(base_dir, "trinity_app.py")
    classic_ui_script = os.path.join(base_dir, "trinity_classic.py")
    console_script = os.path.join(base_dir, "trinity_console.py")
    ear_script = os.path.join(base_dir, "core", "transcriber.py")
    bridge_script = os.path.join(base_dir, "core", "trinity_bridge.py")
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
        "classic": {"eyes": False, "classic": True, "web": False, "terminal": False},
        "eyes": {"eyes": True, "classic": False, "web": False, "terminal": False},
        "web": {"eyes": False, "classic": False, "web": True, "terminal": False},
        "terminal": {"eyes": False, "classic": False, "web": False, "terminal": True},
        "all": {"eyes": True, "classic": True, "web": True, "terminal": True},
    }
    if surface in surface_modes:
        ui_modes = surface_modes[surface]
    show_terminal = ui_modes["terminal"]
    child_env = _trinity_subprocess_env()
    companion_config = _read_companion_config(config_file)
    server_config = _read_server_config(config_file)
    workbench_config = _read_workbench_config(config_file)

    with open(
        os.path.join(logs_dir, "launcher.log"), "a", encoding="utf-8"
    ) as launcher_log, open(
        os.path.join(logs_dir, "runtime.log"), "a", encoding="utf-8"
    ) as runtime_log, open(
        os.path.join(logs_dir, "ui.log"), "a", encoding="utf-8"
    ) as ui_log, open(
        os.path.join(logs_dir, "canvas.log"), "a", encoding="utf-8"
    ) as canvas_log:
        _log_message(
            launcher_log,
            "Starte Trinity-Laufzeit mit Oberflächen: "
            + ", ".join(name for name, enabled in ui_modes.items() if enabled),
        )
        console_flags = 0
        if sys.platform == "win32" and show_terminal:
            console_flags = subprocess.CREATE_NEW_CONSOLE

        bridge_process = None
        canvas_process = None
        canvas_manager = CanvasManager(base_dir)
        if canvas_manager.enabled:
            try:
                canvas_process = canvas_manager.start(log_handle=canvas_log)
                _log_message(
                    launcher_log,
                    "Canvas ist bereit und wird von Trinity verwaltet.",
                )
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                _log_message(launcher_log, f"Canvas konnte nicht gestartet werden: {exc}")
        web_enabled = ui_modes["web"]
        companion_enabled = companion_config.get("enabled", False)
        workbench_enabled = workbench_config.get("enabled", True)
        if companion_enabled or web_enabled or workbench_enabled:
            bridge_config = companion_config if companion_enabled else server_config
            bridge_host = str(bridge_config.get("host") or "127.0.0.1")
            bridge_port = int(bridge_config.get("port") or 8765)
            bridge_command = [
                sys.executable,
                "-u",
                bridge_script,
                "--home",
                base_dir,
                "--host",
                bridge_host,
                "--port",
                str(bridge_port),
            ]
            token = str(bridge_config.get("token") or "")
            if token:
                child_env["TRINITY_BRIDGE_TOKEN"] = token
            if web_enabled and not companion_enabled and bridge_config.get("auth_enabled", False):
                bridge_command.append("--auth")
            bridge_process = subprocess.Popen(
                bridge_command,
                stdout=None if show_terminal else runtime_log,
                stderr=None if show_terminal else subprocess.STDOUT,
                creationflags=0,
                env=child_env,
            )
            _log_message(
                launcher_log,
                ("WebUI und Companion Bridge" if companion_enabled and web_enabled else
                 "WebUI" if web_enabled else "Companion Bridge")
                + f" gestartet auf {bridge_host}:{bridge_port}",
            )
            if web_enabled:
                browser_host = "127.0.0.1" if bridge_host in {"0.0.0.0", "::"} else bridge_host
                webbrowser.open(f"http://{browser_host}:{bridge_port}/")

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
                if bridge_process is not None and bridge_process.poll() is not None:
                    _log_message(
                        launcher_log,
                        f"Companion Bridge wurde mit Code {bridge_process.returncode} beendet.",
                    )
                    bridge_process = None
                    if web_enabled and not ui_processes:
                        break
                time.sleep(1)
        except KeyboardInterrupt:
            _log_message(launcher_log, "Trinity wurde manuell beendet.")
        finally:
            for process in ui_processes.values():
                _terminate(process)
            _terminate(ear_process)
            _terminate(bridge_process)
            _terminate(canvas_process)
            reset_request_path = canvas_manager.paths.runtime_root / "reset-request.json"
            if reset_request_path.is_file():
                try:
                    import json

                    request = json.loads(reset_request_path.read_text(encoding="utf-8"))
                    reset_request_path.unlink(missing_ok=True)
                    result = reset_operational_memory(
                        base_dir,
                        backup=bool(request.get("backup", True)),
                        include_generated=bool(request.get("include_generated", False)),
                        include_canvas=bool(request.get("include_canvas", False)),
                    )
                    _log_message(
                        launcher_log,
                        "Memory wurde zurückgesetzt; Sicherung: " + str(result.get("backup") or "keine"),
                    )
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    _log_message(launcher_log, f"Memory-Reset fehlgeschlagen: {exc}")
            _log_message(launcher_log, "Trinity ist schlafen gegangen.")
            _release_launcher_lock(launcher_lock)

if __name__ == "__main__":
    launch_trinity()
