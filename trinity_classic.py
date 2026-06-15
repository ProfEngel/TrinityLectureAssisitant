"""Traditional desktop UI for Trinity with transcript, results and text input."""

import glob
import html
import os
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QIcon, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.join(BASE_DIR, "core")
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

from settings_ui import SettingsWindow
from chat_attachments import stage_attachment
from chat_protocol import (
    append_chat_event,
    build_chat_request,
    encode_chat_request,
    load_chat_events,
)


CHAT_HISTORY_FILE = os.path.join(MEMORY_DIR, "classic_chat_history.jsonl")
CHAT_UPLOAD_DIR = os.path.join(MEMORY_DIR, "chat_uploads")


def _latest_transcript(memory_dir=MEMORY_DIR):
    candidates = glob.glob(os.path.join(memory_dir, "raw_session_*.md"))
    return max(candidates, key=os.path.getmtime) if candidates else None


def _format_size(size):
    value = float(size or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024


def _attachment_html(attachment):
    name = html.escape(str(attachment.get("name", "Anlage")))
    kind = attachment.get("kind", "file")
    size = html.escape(_format_size(attachment.get("size", 0)))
    path = Path(str(attachment.get("path", "")))
    preview = ""
    if kind == "image" and path.is_file():
        preview = (
            f'<img class="attachment-preview" src="{html.escape(path.resolve().as_uri())}" '
            f'alt="{name}">'
        )
    labels = {"image": "Bild", "pdf": "PDF", "text": "Text"}
    return (
        '<div class="attachment">'
        f"{preview}<strong>{name}</strong>"
        f'<span>{labels.get(kind, "Datei")} · {size}</span>'
        "</div>"
    )


def _render_chat_html(events):
    message_html = []
    for event in events:
        role = event.get("role", "assistant")
        text = html.escape(str(event.get("text", ""))).replace("\n", "<br>")
        timestamp = event.get("timestamp")
        try:
            time_label = datetime.fromtimestamp(float(timestamp)).strftime("%H:%M")
        except (TypeError, ValueError, OSError):
            time_label = ""
        attachments = "".join(
            _attachment_html(item) for item in event.get("attachments", [])
        )
        payload = event.get("payload_html", "")
        payload_frame = ""
        if payload:
            cleaned = payload.replace("<!-- FULLPAGE -->", "")
            payload_frame = (
                '<div class="payload-card"><div class="payload-title">'
                "Agenten- oder Medienergebnis</div>"
                f'<iframe srcdoc="{html.escape(cleaned, quote=True)}">'
                "</iframe></div>"
            )
        sender = "Du" if role == "user" else "Trinity"
        body = f"<div class=\"message-text\">{text}</div>" if text else ""
        message_html.append(
            f'<article class="message {html.escape(role)}">'
            f'<div class="message-meta">{sender}<span>{time_label}</span></div>'
            f"{body}{attachments}{payload_frame}</article>"
        )

    empty = (
        '<div class="empty"><h2>Chat mit Trinity</h2>'
        "<p>Schreibe eine Nachricht oder füge Texte, PDFs und Bilder hinzu.</p></div>"
    )
    content = "".join(message_html) or empty
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
html, body {{ background:#09090b; color:#f4f4f5; font-family:-apple-system,
BlinkMacSystemFont,"Segoe UI",sans-serif; margin:0; }}
body {{ padding:18px; }}
.empty {{ color:#71717a; text-align:center; padding:80px 20px; }}
.message {{ max-width:86%; margin:0 0 16px; padding:13px 15px;
border:1px solid #27272a; border-radius:14px; background:#121214; }}
.message.user {{ margin-left:auto; background:#1d2838; border-color:#334155; }}
.message-meta {{ display:flex; justify-content:space-between; gap:20px;
font-size:11px; font-weight:700; color:#a1a1aa; margin-bottom:8px; }}
.message-text {{ white-space:normal; line-height:1.55; overflow-wrap:anywhere; }}
.attachment {{ display:inline-flex; vertical-align:top; flex-direction:column;
gap:4px; max-width:220px; margin:10px 8px 0 0; padding:9px;
border:1px solid #3f3f46; border-radius:10px; background:#18181b; }}
.attachment span {{ color:#a1a1aa; font-size:11px; }}
.attachment-preview {{ width:200px; max-height:150px; object-fit:cover;
border-radius:7px; margin-bottom:4px; }}
.payload-card {{ margin-top:12px; border-top:1px solid #27272a; padding-top:12px; }}
.payload-title {{ color:#a1a1aa; font-size:11px; font-weight:700; margin-bottom:8px; }}
iframe {{ width:100%; min-height:360px; border:1px solid #27272a;
border-radius:10px; background:#09090b; }}
a {{ color:#38bdf8; }}
</style></head><body>{content}<script>
window.scrollTo(0, document.body.scrollHeight);
</script></body></html>"""


class ChatInput(QTextEdit):
    submit_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent):
        if (
            event.key() in (Qt.Key_Return, Qt.Key_Enter)
            and not event.modifiers() & Qt.ShiftModifier
        ):
            self.submit_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class ClassicWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Trinity Assistant")
        self.resize(1100, 760)
        self.setMinimumSize(760, 520)

        self._transcript_path = None
        self._transcript_signature = None
        self._chat_signature = None
        self._last_state = ""
        self.pending_attachments = []
        self.setAcceptDrops(True)

        self.pages = QStackedWidget()
        self.chat_page = QWidget()
        layout = QVBoxLayout(self.chat_page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Trinity Assistant")
        title.setObjectName("title")
        self.status = QLabel("Bereit")
        self.status.setObjectName("status")
        settings_button = QPushButton("⚙")
        settings_button.setObjectName("gear")
        settings_button.setFixedSize(42, 38)
        settings_button.setToolTip("Einstellungen öffnen")
        settings_button.clicked.connect(self.show_settings)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.status)
        header.addWidget(settings_button)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        transcript_panel = QWidget()
        transcript_layout = QVBoxLayout(transcript_panel)
        transcript_layout.setContentsMargins(0, 0, 0, 0)
        transcript_layout.setSpacing(6)
        transcript_label = QLabel("Live-Mitschrift")
        transcript_label.setObjectName("section")
        self.transcript = QTextEdit()
        self.transcript.setObjectName("transcript")
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText("Die aktuelle Mitschrift erscheint hier.")
        transcript_layout.addWidget(transcript_label)
        transcript_layout.addWidget(self.transcript)

        chat_panel = QWidget()
        chat_layout = QVBoxLayout(chat_panel)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(8)
        chat_label = QLabel("Chat")
        chat_label.setObjectName("section")
        self.chat_history = QWebEngineView()
        self.chat_history.page().setBackgroundColor(QColor("#09090b"))
        web_settings = self.chat_history.settings()
        web_settings.setAttribute(
            QWebEngineSettings.LocalContentCanAccessRemoteUrls,
            True,
        )
        web_settings.setAttribute(
            QWebEngineSettings.LocalContentCanAccessFileUrls,
            True,
        )
        self.chat_history.setHtml(_render_chat_html([]))
        chat_layout.addWidget(chat_label)
        chat_layout.addWidget(self.chat_history, 1)

        splitter.addWidget(transcript_panel)
        splitter.addWidget(chat_panel)
        splitter.setSizes([390, 710])
        layout.addWidget(splitter, 1)

        attachment_row = QHBoxLayout()
        self.attachment_summary = QLabel("")
        self.attachment_summary.setObjectName("attachments")
        self.attachment_summary.setVisible(False)
        clear_attachments = QPushButton("Anlagen entfernen")
        clear_attachments.setObjectName("subtle")
        clear_attachments.clicked.connect(self.clear_attachments)
        self.clear_attachments_button = clear_attachments
        clear_attachments.setVisible(False)
        attachment_row.addWidget(self.attachment_summary, 1)
        attachment_row.addWidget(clear_attachments)
        layout.addLayout(attachment_row)

        command_row = QHBoxLayout()
        attach_button = QPushButton("Anlage")
        attach_button.setToolTip("Text, PDF oder Bild hinzufügen")
        attach_button.clicked.connect(self.choose_attachments)
        self.command = ChatInput()
        self.command.setFixedHeight(68)
        self.command.setPlaceholderText(
            "Mit Trinity schreiben ...  Enter sendet, Shift+Enter macht eine neue Zeile"
        )
        self.command.submit_requested.connect(self.send_command)
        send_button = QPushButton("Senden")
        send_button.setObjectName("primary")
        send_button.clicked.connect(self.send_command)
        command_row.addWidget(attach_button)
        command_row.addWidget(self.command, 1)
        command_row.addWidget(send_button)
        layout.addLayout(command_row)

        self.settings_page = SettingsWindow(
            os.path.join(CORE_DIR, "config.json"),
            embedded=True,
            on_return=self.return_to_chat,
        )
        self.pages.addWidget(self.chat_page)
        self.pages.addWidget(self.settings_page)
        self.setCentralWidget(self.pages)
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
            QTextEdit {
                background: #121214; color: #f4f4f5;
                border: 1px solid #27272a; border-radius: 8px;
                padding: 10px; selection-background-color: #3f3f46;
            }
            QTextEdit#transcript { font-family: "SF Mono", Consolas, monospace; }
            QLabel#attachments {
                background: #18181b; border: 1px solid #3f3f46;
                border-radius: 8px; padding: 8px 10px; color: #d4d4d8;
            }
            QPushButton {
                background: #18181b; color: #e4e4e7;
                border: 1px solid #3f3f46; border-radius: 8px;
                padding: 9px 16px; font-weight: 600;
            }
            QPushButton:hover { background: #27272a; }
            QPushButton#primary { background: #f4f4f5; color: #09090b; }
            QPushButton#subtle { padding: 7px 10px; color: #a1a1aa; }
            QPushButton#gear { font-size: 20px; padding: 0; }
            QSplitter::handle { background: #27272a; width: 2px; }
        """)

    def refresh(self):
        self._refresh_state()
        self._refresh_transcript()
        self._refresh_chat_history()

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

    def _refresh_chat_history(self):
        path = CHAT_HISTORY_FILE
        try:
            signature = (os.path.getmtime(path), os.path.getsize(path))
        except OSError:
            return
        if signature == self._chat_signature:
            return
        self._chat_signature = signature
        events = load_chat_events(path)
        base_url = QUrl.fromLocalFile(BASE_DIR + os.sep)
        self.chat_history.setHtml(_render_chat_html(events), base_url)

    def choose_attachments(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Anlagen auswählen",
            str(Path.home()),
            (
                "Unterstützte Dateien (*.txt *.md *.markdown *.csv *.tsv *.json "
                "*.yaml *.yml *.log *.py *.js *.html *.css *.pdf *.png *.jpg "
                "*.jpeg *.webp *.gif);;Alle Dateien (*)"
            ),
        )
        self._add_attachments(paths)

    def _add_attachments(self, paths):
        errors = []
        for path in paths:
            try:
                self.pending_attachments.append(
                    stage_attachment(path, CHAT_UPLOAD_DIR)
                )
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
        self._update_attachment_summary()
        if errors:
            self.status.setText(errors[0])

    def _update_attachment_summary(self):
        count = len(self.pending_attachments)
        visible = count > 0
        self.attachment_summary.setVisible(visible)
        self.clear_attachments_button.setVisible(visible)
        if visible:
            names = ", ".join(item["name"] for item in self.pending_attachments)
            self.attachment_summary.setText(f"{count} Anlage(n): {names}")

    def clear_attachments(self):
        upload_root = Path(CHAT_UPLOAD_DIR).resolve()
        for attachment in self.pending_attachments:
            path = Path(str(attachment.get("path", "")))
            try:
                resolved = path.resolve()
                if upload_root in resolved.parents:
                    resolved.unlink(missing_ok=True)
            except OSError:
                pass
        self.pending_attachments = []
        self._update_attachment_summary()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            supported = any(
                url.isLocalFile() for url in event.mimeData().urls()
            )
            if supported:
                event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        self._add_attachments(paths)
        event.acceptProposedAction()

    def send_command(self):
        text = self.command.toPlainText().strip()
        if not text and not self.pending_attachments:
            return
        if not text:
            text = "Bitte analysiere die beigefügten Anlagen."
        request = build_chat_request(
            text,
            self.pending_attachments,
            history_recorded=True,
        )
        append_chat_event(
            CHAT_HISTORY_FILE,
            {
                "request_id": request["request_id"],
                "role": "user",
                "source": "classic",
                "text": text,
                "attachments": self.pending_attachments,
            },
        )
        command_path = os.path.join(CORE_DIR, "cmd.txt")
        try:
            with open(command_path, "w", encoding="utf-8") as handle:
                handle.write(encode_chat_request(request))
            self.command.clear()
            self.pending_attachments = []
            self._update_attachment_summary()
            self.status.setText("Auftrag gesendet")
            self._chat_signature = None
            self._refresh_chat_history()
        except OSError as exc:
            append_chat_event(
                CHAT_HISTORY_FILE,
                {
                    "request_id": request["request_id"],
                    "role": "assistant",
                    "source": "classic",
                    "text": f"Eingabe fehlgeschlagen: {exc}",
                },
            )
            self._chat_signature = None
            self._refresh_chat_history()

    def show_settings(self):
        self.pages.setCurrentWidget(self.settings_page)

    def return_to_chat(self, saved=False):
        self.pages.setCurrentWidget(self.chat_page)
        if saved:
            self.status.setText("Einstellungen gespeichert")
            self.command.setFocus(Qt.OtherFocusReason)


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
