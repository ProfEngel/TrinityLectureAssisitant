"""Run Trinity's headless core and browser WebUI as one supervised process."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def _terminate(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def run_server(home, host="127.0.0.1", port=8765, token="", auth_enabled=False,
               voice_profile=None):
    home = Path(home).resolve()
    logs = home / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "TRINITY_SERVER": "1"})
    runtime_log = (logs / "server-runtime.log").open("a", encoding="utf-8")
    bridge_log = (logs / "server-web.log").open("a", encoding="utf-8")
    runtime = subprocess.Popen([sys.executable, "-u", str(home / "core" / "transcriber.py")], cwd=home, env=env, stdout=runtime_log, stderr=subprocess.STDOUT)
    bridge_command = [sys.executable, "-u", str(home / "core" / "trinity_bridge.py"), "--home", str(home), "--host", host, "--port", str(port)]
    if token:
        bridge_command.extend(["--token", token])
    if auth_enabled:
        bridge_command.append("--auth")
    bridge = subprocess.Popen(bridge_command, cwd=home, env=env, stdout=bridge_log, stderr=subprocess.STDOUT)
    voice_log = None
    voice = None
    if voice_profile:
        voice_log = (logs / "server-voice.log").open("a", encoding="utf-8")
        voice = subprocess.Popen(
            [sys.executable, "-u", str(home / "trinity_cli.py"), "voice", "serve", "--profile", voice_profile],
            cwd=home, env=env, stdout=voice_log, stderr=subprocess.STDOUT,
        )
    print(f"Trinity Server laeuft auf http://{host}:{port}")
    if voice_profile:
        print(f"Trinity Voice laeuft mit Profil {voice_profile}; Details: logs/server-voice.log")
    if auth_enabled:
        print("WebUI: /  |  Erster Aufruf: Admin-Account anlegen | getrennte Nutzerbereiche aktiv")
    else:
        print("WebUI: /  |  Logs: logs/server-runtime.log und logs/server-web.log")
    processes = [runtime, bridge] + ([voice] if voice is not None else [])
    exit_code = 0
    try:
        while all(process.poll() is None for process in processes):
            time.sleep(0.4)
        exit_code = next((int(process.returncode or 1) for process in processes
                          if process.poll() is not None), 1)
    except KeyboardInterrupt:
        print("\nTrinity Server wird beendet.")
    finally:
        for process in reversed(processes):
            _terminate(process)
        runtime_log.close()
        bridge_log.close()
        if voice_log is not None:
            voice_log.close()
    return exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(description="Trinity Headless Server mit WebUI")
    parser.add_argument("--home", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default=os.environ.get("TRINITY_WEB_TOKEN", ""))
    parser.add_argument("--auth", action="store_true", help="Passwort-Accounts und getrennte Nutzerbereiche aktivieren")
    parser.add_argument("--voice-profile", default=None,
                        help="Sprachpipeline mitstarten, z.B. trinity-linux-server")
    args = parser.parse_args(argv)
    return run_server(args.home, args.host, args.port, args.token, args.auth,
                      voice_profile=args.voice_profile)


if __name__ == "__main__":
    raise SystemExit(main())
