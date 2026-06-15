"""Traditional desktop UI for Trinity with transcript, results and text input."""

import glob
import html
import os
import subprocess
import sys

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QIcon, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.join(BASE_DIR, "core")
MEMORY_DIR = os.path.join(BASE_DIR, "memory")


def _latest_transcript(memory_dir=MEMORY_DIR):
    candidates = glob.glob(os.path.join(memory_dir, "raw_session_*.md"))
    return max(candidates, key=os.path.getmtime) if candidates else None


def _wrap_payload(payload):
    if "<!-- FULLPAGE -->" in payload:
        return payload.replace("<!-- FULLPAGE -->", "").replace(
            "<!-- KEEP_OPEN -->",
            "",
        )
    return f"""
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="UTF-8">
        <style>
          body {{
            background: #09090b;
            color: #f4f4f5;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            line-height: 1.55;
            margin: 0;
            padding: 22px;
          }}
          a {{ color: #38bdf8; }}
          code, pre {{ background: #18181b; border-radius: 6px; }}
          pre {{ padding: 12px; overflow: auto; }}
        </style>
      </head>
      <body>{payload}</body>
    </html>
    """


class ClassicWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Trinity Assistant")
        self.resize(1100, 760)
        self.setMinimumSize(760, 520)

        self._transcript_path = None
        self._transcript_signature = None
        self._payload_signature = None
        self._last_state = ""

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Trinity Assistant")
        title.setObjectName("title")
        self.status = QLabel("Bereit")
        self.status.setObjectName("status")
        settings_button = QPushButton("Einstellungen")
        settings_button.clicked.connect(self.open_settings)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.status)
        header.addWidget(settings_button)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Vertical)
        transcript_panel = QWidget()
        transcript_layout = QVBoxLayout(transcript_panel)
        transcript_layout.setContentsMargins(0, 0, 0, 0)
        transcript_layout.setSpacing(6)
        transcript_label = QLabel("Live-Mitschrift")
        transcript_label.setObjectName("section")
        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText("Die aktuelle Mitschrift erscheint hier.")
        transcript_layout.addWidget(transcript_label)
        transcript_layout.addWidget(self.transcript)

        results_panel = QWidget()
        results_layout = QVBoxLayout(results_panel)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(6)
        results_label = QLabel("Antworten und Agentenergebnisse")
        results_label.setObjectName("section")
        self.results = QWebEngineView()
        self.results.page().setBackgroundColor(QColor("#09090b"))
        web_settings = self.results.settings()
        web_settings.setAttribute(
            QWebEngineSettings.LocalContentCanAccessRemoteUrls,
            True,
        )
        web_settings.setAttribute(
            QWebEngineSettings.LocalContentCanAccessFileUrls,
            True,
        )
        self.results.setHtml(
            _wrap_payload(
                "<h2>Ergebnisse</h2><p>Trinitys Antworten und Agentenberichte "
                "erscheinen hier.</p>"
            )
        )
        results_layout.addWidget(results_label)
        results_layout.addWidget(self.results)

        splitter.addWidget(transcript_panel)
        splitter.addWidget(results_panel)
        splitter.setSizes([430, 260])
        layout.addWidget(splitter, 1)

        command_row = QHBoxLayout()
        self.command = QLineEdit()
        self.command.setPlaceholderText("Mit Trinity schreiben ...")
        self.command.returnPressed.connect(self.send_command)
        send_button = QPushButton("Senden")
        send_button.setObjectName("primary")
        send_button.clicked.connect(self.send_command)
        command_row.addWidget(self.command, 1)
        command_row.addWidget(send_button)
        layout.addLayout(command_row)

        self.setCentralWidget(central)
        self._apply_style()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(400)
        self.refresh()

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #09090b; color: #e4e4e7; }
            QLabel#title { font-size: 22px; font-weight: 650; }
            QLabel#section { color: #a1a1aa; font-size: 12px; font-weight: 600; }
            QLabel#status {
                background: #18181b; border: 1px solid #27272a;
                border-radius: 12px; padding: 6px 12px; color: #a1a1aa;
            }
            QTextEdit, QLineEdit {
                background: #121214; color: #f4f4f5;
                border: 1px solid #27272a; border-radius: 8px;
                padding: 10px; selection-background-color: #3f3f46;
            }
            QTextEdit { font-family: "SF Mono", Consolas, monospace; }
            QPushButton {
                background: #18181b; color: #e4e4e7;
                border: 1px solid #3f3f46; border-radius: 8px;
                padding: 9px 16px; font-weight: 600;
            }
            QPushButton:hover { background: #27272a; }
            QPushButton#primary { background: #f4f4f5; color: #09090b; }
            QSplitter::handle { background: #27272a; height: 2px; }
        """)

    def refresh(self):
        self._refresh_state()
        self._refresh_transcript()
        self._refresh_payload()

    def _refresh_state(self):
        state_path = os.path.join(CORE_DIR, "state.txt")
        try:
            state = open(state_path, encoding="utf-8").read().strip()
        except OSError:
            state = "offline"
        if state != self._last_state:
            labels = {
                "idle": "Bereit",
                "listening": "Hört zu",
                "thinking": "Denkt nach",
                "speaking": "Antwortet",
                "reporting": "Ergebnis bereit",
                "sleeping": "Pausiert",
                "offline": "Offline",
            }
            self.status.setText(labels.get(state, state or "Bereit"))
            self._last_state = state

    def _refresh_transcript(self):
        path = _latest_transcript()
        if not path:
            return
        try:
            signature = (path, os.path.getmtime(path), os.path.getsize(path))
        except OSError:
            return
        if signature == self._transcript_signature:
            return
        try:
            content = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            return
        self._transcript_path = path
        self._transcript_signature = signature
        self.transcript.setPlainText(content)
        self.transcript.moveCursor(QTextCursor.End)

    def _refresh_payload(self):
        path = os.path.join(CORE_DIR, "payload.html")
        try:
            signature = (os.path.getmtime(path), os.path.getsize(path))
        except OSError:
            return
        if signature == self._payload_signature:
            return
        try:
            payload = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            return
        self._payload_signature = signature
        base_url = QUrl.fromLocalFile(BASE_DIR + os.sep)
        self.results.setHtml(_wrap_payload(payload), base_url)

    def send_command(self):
        text = self.command.text().strip()
        if not text:
            return
        command_path = os.path.join(CORE_DIR, "cmd.txt")
        try:
            with open(command_path, "w", encoding="utf-8") as handle:
                handle.write("SILENT:" + text)
            self.command.clear()
            self.status.setText("Auftrag gesendet")
        except OSError as exc:
            self.results.setHtml(
                _wrap_payload(
                    "<h2>Eingabe fehlgeschlagen</h2>"
                    f"<p>{html.escape(str(exc))}</p>"
                )
            )

    def open_settings(self):
        subprocess.Popen(
            [sys.executable, os.path.join(CORE_DIR, "settings_ui.py")]
        )


def main():
    app = QApplication(sys.argv)
    icon_candidates = [
        os.path.join(CORE_DIR, "icon.png"),
        os.path.join(BASE_DIR, "assets", "icon.PNG"),
    ]
    icon_path = next((path for path in icon_candidates if os.path.exists(path)), None)
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))
    window = ClassicWindow()
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
