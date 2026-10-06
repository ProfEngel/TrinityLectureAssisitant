"""Render the actual Desktop UI with a disposable, disconnected neutral profile."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

root = Path(__file__).resolve().parents[1]
destination = Path(sys.argv[1]).resolve()
if len(sys.argv) == 2:
    with tempfile.TemporaryDirectory(prefix="trinity-ui-demo-") as folder:
        stage = Path(folder)
        subprocess.run(["git", "archive", "--format=zip", "HEAD", "-o", str(stage / "source.zip")], cwd=root, check=True)
        with zipfile.ZipFile(stage / "source.zip") as archive:
            archive.extractall(stage / "app")
        subprocess.run([sys.executable, __file__, str(destination), str(stage / "app")],
                       env=dict(os.environ, QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu --no-sandbox"), check=True)
else:
    demo = Path(sys.argv[2])
    sys.path.insert(0, str(demo))
    sys.path.insert(0, str(demo / "core"))
    from core.configuration import default_config
    config = default_config()
    config["system"]["mode"] = "chat"
    config["system"]["theme"] = "dark"
    config["companion"]["enabled"] = False
    (demo / "core/config.json").write_text(json.dumps(config))
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    import trinity_classic
    app = QApplication([])
    window = trinity_classic.ClassicWindow()
    window.resize(1200, 800)
    # Render neutral onboarding content, not a made-up assistant conversation.
    (demo / "core/payload.html").write_text('<html><body style="background:#10171e;color:#e8eef1;font:18px -apple-system,sans-serif;padding:42px"><p style="color:#ffb45e;font-size:12px;letter-spacing:2px">TRINITY DESKTOP · DEMOPROFIL</p><h1 style="font-size:48px">Ein Gespräch.<br>Viele Möglichkeiten.</h1><p>Sprache · Folien · Memory · Schreibarbeit</p><p style="color:#a3b2ba;line-height:1.8">Verbinde Dein OpenAI-kompatibles LLM in den Einstellungen.<br>Sprich mit Trinity oder beginne eine Nachricht.<br>Freigegebene Folien und Texte können Teil des Gesprächs werden.</p><p style="color:#ffb45e">Standalone oder ein gemeinsamer Trinity-Server.</p></body></html>', encoding="utf-8")
    window.show()
    def capture():
        destination.parent.mkdir(parents=True, exist_ok=True)
        window.grab().save(str(destination))
        app.quit()
    QTimer.singleShot(2400, capture)
    app.exec()
