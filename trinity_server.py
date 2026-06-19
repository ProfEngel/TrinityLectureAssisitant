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


def run_server(home, host="127.0.0.1", port=8765, token=""):
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
    bridge = subprocess.Popen(bridge_command, cwd=home, env=env, stdout=bridge_log, stderr=subprocess.STDOUT)
    print(f"Trinity Server laeuft auf http://{host}:{port}")
    print("WebUI: /  |  Logs: logs/server-runtime.log und logs/server-web.log")
    try:
        while runtime.poll() is None and bridge.poll() is None:
            time.sleep(0.4)
    except KeyboardInterrupt:
        print("\nTrinity Server wird beendet.")
    finally:
        _terminate(runtime)
        _terminate(bridge)
        runtime_log.close()
        bridge_log.close()
    return runtime.returncode or bridge.returncode or 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Trinity Headless Server mit WebUI")
    parser.add_argument("--home", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default=os.environ.get("TRINITY_WEB_TOKEN", ""))
    args = parser.parse_args(argv)
    return run_server(args.home, args.host, args.port, args.token)


if __name__ == "__main__":
    raise SystemExit(main())
