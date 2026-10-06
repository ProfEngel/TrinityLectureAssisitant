"""Frozen graphical installer/launcher. Runtime Python stays outside the bundle.

All subprocesses use argv arrays, never a shell. Existing configurations and
memory are never replaced by release templates. No administrator is required.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

VERSION = "0.19.1"


def data_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/TrinityDesktop"
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "TrinityDesktop"


def resources() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "resources"


def normalize_api_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Bitte eine HTTP(S)-URL ohne eingebettete Zugangsdaten eingeben.")
    if parsed.query or parsed.fragment:
        raise ValueError("Die API-URL darf keine Query oder Fragment enthalten.")
    if value.endswith("/chat/completions"):
        return value
    return value + ("/chat/completions" if parsed.path.rstrip("/").endswith("/v1") else "/v1/chat/completions")


def safe_extract(archive: Path, target: Path):
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            parts = PurePosixPath(info.filename)
            if parts.is_absolute() or ".." in parts.parts or "\\" in info.orig_filename or ":" in info.filename:
                raise ValueError("Ungültiger Pfad im Installationspaket.")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Symbolischer Link im Installationspaket nicht erlaubt.")
        bundle.extractall(target)


def new_config(app: Path, values: dict) -> dict:
    sys.path.insert(0, str(app))
    from core.configuration import default_config
    config = default_config()
    config["system"].update(show_terminal=False, terminal_cli_enabled=False, mode="chat",
                            voice_sentence_streaming=True, windows_speech_enabled=False)
    config["proactive"].update(heartbeat_enabled=False, session_summary_auto_rag_indexing=False)
    config["canvas"]["enabled"] = False
    config["voice"].update(engine="eve", fallback_to_legacy=False, num_pipelines=1,
                            barge_in_enabled=False, echo_suppression_enabled=True)
    if values["mode"] == "client":
        server = values["url"].strip().rstrip("/")
        if urlsplit(server).scheme not in {"http", "https"} or not urlsplit(server).hostname:
            raise ValueError("Trinity-Server-URL ungültig.")
        host = urlsplit(server).hostname
        ws = values["voice_url"].strip() or ("wss" if server.startswith("https") else "ws") + "://" + (f"[{host}]" if ":" in host else host) + ":8766/v1/realtime"
        if urlsplit(ws).scheme not in {"ws", "wss"} or not urlsplit(ws).hostname:
            raise ValueError("Voice-URL ungültig.")
        if not values["key"].strip():
            raise ValueError("Im Client-Modus wird der Trinity-Server-Token benötigt.")
        config["client"].update(enabled=True, server_url=server, token=values["key"].strip())
        config["voice"].update(profile="trinity-mac-client", remote_voice_url=ws,
                                remote_voice_token=values["key"].strip())
        return config
    config["llm"]["local"].update(url=normalize_api_url(values["url"]), model=values["model"].strip(),
                                    api_key=values["key"].strip(), request_timeout_seconds=45)
    if not config["llm"]["local"]["model"]:
        raise ValueError("Bitte den Modellnamen angeben.")
    mac = sys.platform == "darwin"
    name = "eve-mac-local" if mac else "eve-windows-local"
    config["voice"]["profile"] = name
    profile = config["voice"]["profiles"][name]
    profile.update(num_pipelines=1, bind_host="127.0.0.1", local_audio=True,
                   stt_model="animaslabs/parakeet-tdt-0.6b-v3-mlx-4bit" if mac else "nvidia/parakeet-tdt-0.6b-v3",
                   tts_model="mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit" if mac else "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
                   tts_backend="ggml" if mac else "torch")
    voice = resources() / "eve.wav"
    destination = app / "TrinityRuntime/voices/eve/eve.wav"
    if voice.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(voice, destination)
        config["voice"].update(reference_audio=str(destination),
                                reference_text=(resources() / "eve.txt").read_text(encoding="utf-8").strip())
    else:
        profile["tts_model"] = profile["tts_model"].replace("-Base", "-CustomVoice")
        config["voice"]["tts_speaker"] = "Vivian"
    return config


def run_command(argv, log, env, timeout=3600):
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen([str(x) for x in argv], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               encoding="utf-8", errors="replace", env=env, creationflags=flags)
    import threading
    expired = threading.Event()
    def terminate():
        expired.set()
        process.kill()
    timer = threading.Timer(timeout, terminate)
    timer.start()
    try:
        for line in process.stdout:
            log(line.rstrip())
        status = process.wait()
        if expired.is_set():
            raise RuntimeError("Einrichtung hat das Zeitlimit erreicht. Bitte erneut versuchen.")
        if status:
            raise RuntimeError(f"Einrichtung fehlgeschlagen (Code {status}). Details siehe Protokoll.")
    finally:
        timer.cancel()


def setup(values, root: Path, log):
    root.mkdir(parents=True, exist_ok=True)
    app = root / "app"
    marker = root / "installation.json"
    complete = json.loads(marker.read_text()) if marker.exists() else {}
    if complete.get("version") == VERSION and (app / "core/config.json").is_file():
        return app, root / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python3")
    # Refuse changing code while the current installation's launcher is running.
    lock = app / "TrinityRuntime/launcher.lock"
    if lock.exists():
        with lock.open("r+b") as handle:
            if os.name == "nt":
                import msvcrt
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    raise RuntimeError("Trinity läuft noch. Bitte vor dem Update beenden.")
            else:
                import fcntl
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    raise RuntimeError("Trinity läuft noch. Bitte vor dem Update beenden.")
    mac = sys.platform == "darwin"
    existing = app / "core/config.json"
    mode = values["mode"]
    if existing.exists():
        # Existing server, Eve, API and client choices always win over defaults.
        mode = "client" if json.loads(existing.read_text(encoding="utf-8")).get("client", {}).get("enabled") else "standalone"
    if mode == "standalone" and mac and platform.machine() != "arm64":
        raise RuntimeError("Lokales Parakeet/Qwen3 benötigt einen Apple-Silicon-Mac. Auf Intel bitte Server-Client wählen.")
    if mode == "standalone" and not mac and not shutil.which("nvidia-smi"):
        raise RuntimeError("Lokale Sprache benötigt eine NVIDIA-GPU mit aktuellem Treiber. Ohne GPU bitte Server-Client wählen.")
    archive = resources() / "source.zip"
    expected = (resources() / "source.sha256").read_text().strip()
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise RuntimeError("Installationspaket beschädigt. Bitte erneut herunterladen.")
    # Stage the new code. Preserve prior code and runtime for recovery on failure.
    with tempfile.TemporaryDirectory(prefix="trinity-stage-", dir=root) as temporary:
        staged = Path(temporary)
        safe_extract(archive, staged)
        if app.exists():
            backup = root / "recovery" / f"before-{VERSION}"
            if not backup.exists():
                shutil.copytree(app, backup)
        else:
            app.mkdir()
        shutil.copytree(staged, app, dirs_exist_ok=True)
    for name in ("Soul", "User"):
        dest = app / "core" / f"{name}.md"
        if not dest.exists() or not dest.stat().st_size:
            shutil.copyfile(app / "core" / f"{name}.md.example", dest)
    config = new_config(app, values) if not existing.exists() else json.loads(existing.read_text(encoding="utf-8"))
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", UV_PYTHON_INSTALL_DIR=str(root / "python"),
               UV_CACHE_DIR=str(root / "cache"), HF_HOME=str(root / "models"), TORCH_HOME=str(root / "torch"),
               TOKENIZERS_PARALLELISM="false", HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1")
    uv = resources() / ("uv.exe" if os.name == "nt" else "uv")
    if os.name != "nt":
        uv.chmod(0o755)
    log("Python und Laufzeit werden eingerichtet …")
    run_command([uv, "python", "install", "3.11"], log, env)
    python = root / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python3")
    if not python.exists():
        run_command([uv, "venv", "--python", "3.11", "--managed-python", root / "venv"], log, env)
    packages = [f"{app}[{'macos' if mac else 'windows'}]", "websockets>=14,<18"]
    if mode == "standalone":
        if not mac:
            log("CUDA-PyTorch wird installiert (NVIDIA-Treiber erforderlich) …")
            run_command([uv, "pip", "install", "--python", python, "torch==2.11.0", "torchaudio==2.11.0",
                         "--index-url", "https://download.pytorch.org/whl/cu128"], log, env)
        packages.append("speech-to-speech==0.2.11")
    run_command([uv, "pip", "install", "--python", python, *packages], log, env)
    if mode == "standalone":
        if not mac:
            run_command([python, "-c", "import torch; assert torch.cuda.is_available(), 'NVIDIA-CUDA nicht verfügbar; Treiber prüfen oder Client-Modus wählen.'"], log, env, 60)
        log("Parakeet und Qwen3 werden heruntergeladen und getestet; dies kann einige Minuten dauern …")
        pending = root / "setup-pending.json"
        pending.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        pending.chmod(0o600)
        try:
            run_command([python, "-u", app / "desktop_distribution/warm_voice.py", "--config", pending], log, env)
        finally:
            pending.unlink(missing_ok=True)
    if not existing.exists():
        existing.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        existing.chmod(0o600)
    marker.write_text(json.dumps({"version": VERSION, "mode": mode}), encoding="utf-8")
    log("Einrichtung erfolgreich. Trinity kann gestartet werden.")
    return app, python


def main():
    from PySide6.QtCore import QThread, Signal, QTimer, QLockFile
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                  QLabel, QLineEdit, QComboBox, QPushButton, QPlainTextEdit, QMessageBox)
    application = QApplication(sys.argv)
    application.setApplicationName("Trinity")
    application.setWindowIcon(QIcon(str(resources() / "icon.png")))
    application.setStyleSheet("""
        QWidget { background:#10171e; color:#e6edf3; font-size:14px; }
        QLineEdit,QComboBox,QPlainTextEdit { background:#1b2732; border:1px solid #34424f; border-radius:8px; padding:9px; }
        QPushButton { background:#ffaa50; color:#111820; border:0; border-radius:10px; padding:12px 20px; font-weight:600; }
        QLabel#title { font-size:34px; font-weight:700; }
    """)
    root = Path(os.environ.get("TRINITY_DESKTOP_DATA", str(data_root())))
    root.mkdir(parents=True, exist_ok=True)
    installer_lock = QLockFile(str(root / "setup.lock"))
    installer_lock.setStaleLockTime(0)
    if not installer_lock.tryLock(0):
        QMessageBox.information(None, "Trinity", "Die Trinity-Einrichtung ist bereits geöffnet.")
        return 0
    class Worker(QThread):
        line = Signal(str)
        done = Signal(object)
        failed = Signal(str)
        def __init__(self, values):
            super().__init__()
            self.values = values
        def run(self):
            try:
                self.done.emit(setup(self.values, root, self.line.emit))
            except Exception as exc:
                # Never log raw requests/configuration or authentication headers.
                self.failed.emit(str(exc))
    window = QMainWindow()
    window.setWindowTitle(f"Trinity Desktop · {VERSION}")
    window.resize(760, 690)
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(36, 30, 36, 30)
    layout.setSpacing(12)
    title = QLabel("Trinity. Eine Stimme. Ein Gedächtnis.")
    title.setObjectName("title")
    title.setWordWrap(True)
    layout.addWidget(title)
    explanation = QLabel("Standalone mit Parakeet-STT und Qwen3-TTS oder als schlanker Client für Deinen Trinity-Server.\nDie Ersteinrichtung lädt Python, Bibliotheken und Sprachmodelle automatisch herunter.")
    explanation.setWordWrap(True)
    layout.addWidget(explanation)
    mode = QComboBox()
    mode.addItem("Standalone · Sprache auf diesem Computer", "standalone")
    mode.addItem("Server-Client · vorhandene Trinity verbinden", "client")
    layout.addWidget(mode)
    url = QLineEdit()
    url.setPlaceholderText("OpenAI-kompatible API-URL, z. B. http://localhost:1234/v1")
    model = QLineEdit()
    model.setPlaceholderText("LLM-Modellname")
    key = QLineEdit()
    key.setPlaceholderText("API-Key / Passwort (optional)")
    key.setEchoMode(QLineEdit.Password)
    voice_url = QLineEdit()
    voice_url.setPlaceholderText("Voice-WebSocket-URL (optional; Standard Port 8766)")
    for field in (url, model, key, voice_url):
        layout.addWidget(field)
    def mode_changed():
        client = mode.currentData() == "client"
        model.setVisible(not client)
        voice_url.setVisible(client)
        url.setPlaceholderText("Trinity-Server-URL, z. B. https://trinity.example.org" if client else "OpenAI-kompatible API-URL, z. B. http://localhost:1234/v1")
        key.setPlaceholderText("Trinity-Server-Token (erforderlich)" if client else "API-Key / Passwort (optional)")
    mode.currentIndexChanged.connect(mode_changed)
    mode_changed()
    existing = root / "app/core/config.json"
    if existing.exists():
        explanation.setText("Bestehende Installation erkannt. Deine Verbindungen, Eve-Stimme und Memory bleiben erhalten.")
        for field in (mode, url, model, key, voice_url):
            field.setVisible(False)
    warning = QLabel("Lokale Sprache: Apple Silicon (16 GB RAM empfohlen) oder Windows 11 mit NVIDIA-GPU (8 GB VRAM empfohlen).\nMindestens 15 GB freier Speicher; erster Download benötigt Internet. Ohne passende GPU: Server-Client.\nMikrofon erst nach Berechtigung; Fensterzugriff und Schreibzugriff nur mit Deiner Freigabe.")
    warning.setWordWrap(True)
    layout.addWidget(warning)
    logs = QPlainTextEdit()
    logs.setReadOnly(True)
    logs.setMaximumBlockCount(300)
    layout.addWidget(logs, 1)
    start = QPushButton("Einrichten und starten" if not existing.exists() else "Trinity starten / aktualisieren")
    layout.addWidget(start)
    window.setCentralWidget(panel)
    def launch(result):
        app, python = result
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", HF_HOME=str(root / "models"),
                   TORCH_HOME=str(root / "torch"), TRINITY_VOICE_MULTIPLEX="1", HF_HUB_DISABLE_TELEMETRY="1")
        (root / "logs").mkdir(exist_ok=True)
        with (root / "logs/desktop.log").open("a", encoding="utf-8") as log:
            subprocess.Popen([str(python), "-u", str(app / "trinity_launcher.py"), "--no-terminal"],
                             cwd=app, env=env, stdout=log, stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        application.quit()
    def failed(message):
        start.setEnabled(True)
        logs.appendPlainText(message)
        QMessageBox.warning(window, "Einrichtung nicht abgeschlossen", message)
    def clicked():
        values = dict(mode=mode.currentData(), url=url.text(), model=model.text(), key=key.text(), voice_url=voice_url.text())
        if not existing.exists():
            try:
                if values["mode"] == "standalone":
                    normalize_api_url(values["url"])
                    if not values["model"].strip():
                        raise ValueError("Bitte den Modellnamen angeben.")
                elif not values["key"].strip():
                    raise ValueError("Bitte den Trinity-Server-Token angeben.")
            except ValueError as exc:
                failed(str(exc))
                return
        start.setEnabled(False)
        window.worker = Worker(values)
        window.worker.line.connect(logs.appendPlainText)
        window.worker.done.connect(lambda result: setattr(window, "launch_result", result))
        window.worker.finished.connect(lambda: launch(window.launch_result) if hasattr(window, "launch_result") else None)
        window.worker.failed.connect(failed)
        window.worker.start()
    start.clicked.connect(clicked)
    def may_close(event):
        if hasattr(window, "worker") and window.worker.isRunning():
            event.ignore()
            QMessageBox.information(window, "Einrichtung läuft", "Bitte die laufende Einrichtung abwarten. Bei einem Fehler kannst Du erneut versuchen.")
        else:
            event.accept()
    window.closeEvent = may_close
    window.show()
    if "--screenshot" in sys.argv:
        output = sys.argv[sys.argv.index("--screenshot") + 1]
        def screenshot():
            window.grab().save(output)
            application.quit()
        QTimer.singleShot(700, screenshot)
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
