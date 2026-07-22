"""Install and run Trinity Canvas as a managed Trinity Desktop component."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

try:
    from .configuration import load_config
    from .trinity_paths import TrinityPaths
except ImportError:  # Direct execution with core/ on sys.path.
    from configuration import load_config
    from trinity_paths import TrinityPaths


CANVAS_REPOSITORY = "https://github.com/ProfEngel/TrinityCreativeCanvas.git"
DEFAULT_CANVAS_PORT = 8787


def default_canvas_install_dir() -> Path:
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / "TrinityCanvas"
    return Path.home() / "TrinityCreativeCanvas"


class CanvasManager:
    """Keep Canvas installation details and its internal port out of the UI."""

    def __init__(self, home: str | Path, config: dict | None = None):
        self.home = Path(home).expanduser().resolve()
        self.config = config if config is not None else load_config(self.home / "core" / "config.json")
        self.settings = self.config.get("canvas", {})
        self.paths = TrinityPaths.from_config(self.home, self.config)
        configured_dir = str(self.settings.get("install_dir") or "").strip()
        self.install_dir = Path(configured_dir).expanduser().resolve() if configured_dir else default_canvas_install_dir()
        self.port = int(self.settings.get("port") or DEFAULT_CANVAS_PORT)
        self.host = "127.0.0.1"
        self.data_dir = self.paths.runtime_root / "canvas"
        self.logs_dir = self.home / "logs" / "canvas"
        self.pid_path = self.data_dir / "canvas.pid"

    @property
    def enabled(self) -> bool:
        return bool(self.settings.get("enabled", True))

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def server_entrypoint(self) -> Path:
        return self.install_dir / "dist-server" / "server" / "index.js"

    def is_running(self, timeout: float = 0.6) -> bool:
        try:
            with urlopen(f"{self.url}/api/health", timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return bool(payload.get("ok") and payload.get("service") == "trinity-creative-canvas")
        except (OSError, URLError, ValueError, json.JSONDecodeError):
            return False

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "installed": (self.install_dir / "package.json").is_file(),
            "built": self.server_entrypoint.is_file() and (self.install_dir / "dist" / "index.html").is_file(),
            "running": self.is_running(),
            "install_dir": str(self.install_dir),
            "data_dir": str(self.data_dir),
            "url": self.url,
        }

    def install_or_update(self) -> dict:
        git = shutil.which("git")
        npm = shutil.which("npm")
        if not git:
            raise ValueError("Git fehlt; Trinity Canvas kann nicht installiert werden.")
        if not npm:
            raise ValueError("Node.js/npm fehlt; installiere Node.js und starte die Canvas-Installation erneut.")

        if not self.install_dir.exists():
            self.install_dir.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [git, "clone", "--branch", "main", "--single-branch", CANVAS_REPOSITORY, str(self.install_dir)],
                check=True,
            )
        elif not (self.install_dir / ".git").is_dir():
            raise ValueError(f"Vorhandener Canvas-Ordner ist kein Git-Repository: {self.install_dir}")
        else:
            dirty = subprocess.run(
                [git, "status", "--porcelain"],
                cwd=self.install_dir,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if dirty:
                raise ValueError("Canvas enthält lokale Änderungen; Update zum Schutz dieser Arbeit abgebrochen.")
            subprocess.run([git, "pull", "--ff-only", "origin", "main"], cwd=self.install_dir, check=True)

        install_command = [npm, "ci"] if (self.install_dir / "package-lock.json").is_file() else [npm, "install"]
        subprocess.run(install_command, cwd=self.install_dir, check=True)
        subprocess.run([npm, "run", "build"], cwd=self.install_dir, check=True)
        return self.status()

    def start(self, *, log_handle=None):
        if not self.enabled or self.is_running():
            return None
        node = shutil.which("node")
        if not node:
            raise ValueError("Node.js fehlt; Trinity Canvas kann nicht gestartet werden.")
        if not self.server_entrypoint.is_file():
            raise ValueError("Trinity Canvas ist noch nicht gebaut. Nutze `trinity canvas install`.")

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        output = log_handle
        owned_log = None
        if output is None:
            owned_log = (self.logs_dir / "canvas.log").open("a", encoding="utf-8")
            output = owned_log
        environment = dict(os.environ)
        environment.update(
            {
                "NODE_ENV": "production",
                "HOST": self.host,
                "PORT": str(self.port),
                "DATA_DIR": str(self.data_dir),
                "WORKSPACES_DIR": str(self.data_dir / "workspaces"),
            }
        )
        process = subprocess.Popen(
            [node, str(self.server_entrypoint)],
            cwd=self.install_dir,
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        process._trinity_canvas_log = owned_log  # type: ignore[attr-defined]
        self.pid_path.write_text(str(process.pid), encoding="utf-8")
        for _ in range(40):
            if self.is_running(timeout=0.25):
                return process
            if process.poll() is not None:
                break
            time.sleep(0.25)
        self._terminate_process(process)
        raise ValueError("Trinity Canvas ist nicht rechtzeitig gestartet; siehe logs/canvas.")

    def stop(self) -> bool:
        try:
            pid = int(self.pid_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return False
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            self.pid_path.unlink(missing_ok=True)
            return False
        self.pid_path.unlink(missing_ok=True)
        return True

    def open(self) -> bool:
        if not self.is_running():
            self.start()
        return bool(webbrowser.open(self.url))

    def _terminate_process(self, process) -> None:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.kill()
        self.pid_path.unlink(missing_ok=True)
        handle = getattr(process, "_trinity_canvas_log", None)
        if handle is not None:
            handle.close()
