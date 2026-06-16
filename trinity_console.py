"""Interactive terminal surface that owns Trinity's runtime process."""

import argparse
import os
import queue
import subprocess
import sys
import threading
import time


def _runtime_env(environment=None):
    env = dict(environment or os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def _read_commands(command_queue):
    while True:
        try:
            command_queue.put(input("\nDu > "))
        except EOFError:
            command_queue.put(None)
            return


def run_console(runtime_script):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    command_file = os.path.join(base_dir, "core", "cmd.txt")
    runtime = subprocess.Popen(
        [sys.executable, "-u", runtime_script],
        env=_runtime_env(),
    )

    print("Trinity Terminal CLI")
    print("====================")
    print("Befehle werden still an Trinity übergeben. 'exit' beendet Trinity.")

    commands = queue.Queue()
    requested_exit = False
    threading.Thread(
        target=_read_commands,
        args=(commands,),
        daemon=True,
    ).start()

    try:
        while runtime.poll() is None:
            try:
                command = commands.get(timeout=0.2)
            except queue.Empty:
                continue

            if command is None:
                while runtime.poll() is None:
                    time.sleep(0.5)
                break

            text = command.strip()
            if not text:
                continue
            if text.casefold() in {"exit", "quit", "beenden"}:
                requested_exit = True
                runtime.terminate()
                break

            with open(command_file, "w", encoding="utf-8") as handle:
                handle.write("SILENT:" + text)
    except KeyboardInterrupt:
        requested_exit = True
        runtime.terminate()
    finally:
        if runtime.poll() is None:
            runtime.terminate()
        try:
            return_code = runtime.wait(timeout=5)
            return 0 if requested_exit else return_code
        except subprocess.TimeoutExpired:
            runtime.kill()
            return_code = runtime.wait()
            return 0 if requested_exit else return_code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True)
    args = parser.parse_args()
    raise SystemExit(run_console(args.runtime))


if __name__ == "__main__":
    main()
