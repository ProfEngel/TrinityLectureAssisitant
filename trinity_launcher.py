import subprocess
import sys
import time
import os
from datetime import datetime
from html import escape


def _read_show_terminal(config_file):
    try:
        import json
        with open(config_file, "r", encoding="utf-8") as config_handle:
            config = json.load(config_handle)
        return bool(config.get("system", {}).get("show_terminal", False))
    except Exception:
        return False


def _terminate(process):
    if process is not None and process.poll() is None:
        process.terminate()


def _log_message(log_handle, message):
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
    print(line)
    log_handle.write(line + "\n")
    log_handle.flush()


def _show_runtime_error(base_dir, return_code):
    payload_file = os.path.join(base_dir, "core", "payload.html")
    state_file = os.path.join(base_dir, "core", "state.txt")
    logs_path = escape(os.path.join(base_dir, "logs"))
    payload = f"""
    <!-- KEEP_OPEN -->
    <h2>Trinity-Kern wurde beendet</h2>
    <p>Die Oberfläche bleibt für Einstellungen und Diagnose geöffnet.</p>
    <p>Fehlercode: <code>{return_code}</code></p>
    <p>Protokolle: <code>{logs_path}</code></p>
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
    print("🧞‍♀️ Starte Trinity System...")
    
    # 1. Pfade definieren
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ui_script = os.path.join(base_dir, "trinity_app.py")
    ear_script = os.path.join(base_dir, "core", "transcriber.py")
    config_file = os.path.join(base_dir, "core", "config.json")
    settings_script = os.path.join(base_dir, "core", "settings_ui.py")
    logs_dir = os.path.join(base_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    # 1.5 Prüfen ob config existiert (Erster Start)
    if not os.path.exists(config_file):
        print("⚙️ Erstes Setup erkannt. Öffne Konfiguration...")
        subprocess.run([sys.executable, settings_script])
        if not os.path.exists(config_file):
            print("❌ Konfiguration abgebrochen. Beende Trinity.")
            sys.exit(1)

    diagnostic_mode = "--diagnostic" in sys.argv
    no_terminal = "--no-terminal" in sys.argv
    show_terminal = diagnostic_mode or (
        not no_terminal and _read_show_terminal(config_file)
    )
    runtime_creation_flags = 0
    if sys.platform == "win32" and show_terminal and not diagnostic_mode:
        runtime_creation_flags = subprocess.CREATE_NEW_CONSOLE

    with open(
        os.path.join(logs_dir, "launcher.log"), "a", encoding="utf-8"
    ) as launcher_log, open(
        os.path.join(logs_dir, "runtime.log"), "a", encoding="utf-8"
    ) as runtime_log, open(
        os.path.join(logs_dir, "ui.log"), "a", encoding="utf-8"
    ) as ui_log:
        _log_message(launcher_log, "Starte Trinity-Laufzeit.")
        ear_process = subprocess.Popen(
            [sys.executable, "-u", ear_script],
            stdout=None if show_terminal else runtime_log,
            stderr=None if show_terminal else subprocess.STDOUT,
            creationflags=runtime_creation_flags,
        )
        ui_process = subprocess.Popen(
            [sys.executable, "-u", ui_script],
            stdout=None if show_terminal else ui_log,
            stderr=None if show_terminal else subprocess.STDOUT,
            creationflags=0,
        )

        try:
            while True:
                if ui_process.poll() is not None:
                    _log_message(
                        launcher_log,
                        f"UI wurde mit Code {ui_process.returncode} beendet.",
                    )
                    break
                if ear_process is not None and ear_process.poll() is not None:
                    return_code = ear_process.returncode
                    _log_message(
                        launcher_log,
                        "Kernprozess wurde mit Code "
                        f"{return_code} beendet. Die Oberfläche bleibt "
                        "für Einstellungen und Diagnose geöffnet.",
                    )
                    _show_runtime_error(base_dir, return_code)
                    ear_process = None
                time.sleep(1)
        except KeyboardInterrupt:
            _log_message(launcher_log, "Trinity wurde manuell beendet.")
        finally:
            _terminate(ui_process)
            _terminate(ear_process)
            _log_message(launcher_log, "Trinity ist schlafen gegangen.")

if __name__ == "__main__":
    launch_trinity()
