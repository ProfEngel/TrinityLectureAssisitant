"""Traditional desktop UI for Trinity with transcript, results and text input."""

import glob
import html
import json
import os
import re
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QKeyEvent, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QComboBox,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTabWidget,
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
from memory_store import MemoryStore, render_graph_html
from remote_client import RemoteTrinityClient
from configuration import load_config, save_config
from trinity_bridge import TrinityBridge
from workspace_manager import INBOX_WORKSPACE_ID, TrinityWorkspaceManager


CHAT_HISTORY_FILE = os.path.join(MEMORY_DIR, "classic_chat_history.jsonl")
CHAT_UPLOAD_DIR = os.path.join(MEMORY_DIR, "chat_uploads")
CONFIG_FILE = os.path.join(CORE_DIR, "config.json")
LOGS_DIR = os.path.join(BASE_DIR, "logs")


THEMES = {
    "dark": {
        "app_bg": "#09090b",
        "panel_bg": "#121214",
        "raised_bg": "#18181b",
        "hover_bg": "#27272a",
        "text": "#f4f4f5",
        "muted": "#a1a1aa",
        "border": "#27272a",
        "strong_border": "#3f3f46",
        "user_bg": "#1d2838",
        "user_border": "#334155",
        "primary_bg": "#f4f4f5",
        "primary_text": "#09090b",
        "link": "#38bdf8",
        "selection": "#3f3f46",
    },
    "light": {
        "app_bg": "#f8fafc",
        "panel_bg": "#ffffff",
        "raised_bg": "#eef2f7",
        "hover_bg": "#e2e8f0",
        "text": "#0f172a",
        "muted": "#64748b",
        "border": "#d7dde7",
        "strong_border": "#cbd5e1",
        "user_bg": "#e0f2fe",
        "user_border": "#7dd3fc",
        "primary_bg": "#0f172a",
        "primary_text": "#ffffff",
        "link": "#0369a1",
        "selection": "#bfdbfe",
    },
}


def _latest_transcript(memory_dir=MEMORY_DIR):
    candidates = glob.glob(os.path.join(memory_dir, "raw_session_*.md"))
    return max(candidates, key=os.path.getmtime) if candidates else None


def _default_session_name_prefix():
    return datetime.now().strftime("%Y%m%d_%H%M_")


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
    media_url = str(attachment.get("media_url", ""))
    preview = ""
    if kind == "image" and (path.is_file() or media_url):
        source = media_url or path.resolve().as_uri()
        preview = (
            f'<img class="attachment-preview" src="{html.escape(source)}" '
            f'alt="{name}">'
        )
    labels = {"image": "Bild", "pdf": "PDF", "text": "Text"}
    return (
        '<div class="attachment">'
        f"{preview}<strong>{name}</strong>"
        f'<span>{labels.get(kind, "Datei")} · {size}</span>'
        "</div>"
    )


def _tail_file(path, max_lines=240):
    try:
        lines = Path(path).read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-max_lines:])


def _build_live_log_text(transcript_path, logs_dir=LOGS_DIR):
    sections = []
    if transcript_path:
        try:
            transcript = Path(transcript_path).read_text(
                encoding="utf-8",
                errors="replace",
            ).strip()
        except OSError:
            transcript = ""
        if transcript:
            sections.append(f"## Live-Mitschrift\n\n{transcript}")

    runtime = _tail_file(os.path.join(logs_dir, "runtime.log"))
    if runtime:
        sections.append(
            "## Laufzeitlog / Agenten\n\n"
            "Hier erscheinen geladene Agenten, aktivierte Skills, Tool-Ausgaben "
            "und Fehlermeldungen aus dem Trinity-Kernprozess.\n\n"
            f"{runtime}"
        )

    launcher = _tail_file(os.path.join(logs_dir, "launcher.log"), max_lines=80)
    if launcher:
        sections.append(f"## Launcher\n\n{launcher}")

    return "\n\n---\n\n".join(sections) or (
        "Noch keine Live-Mitschrift oder Laufzeitlogs vorhanden."
    )


def _render_chat_html(events, theme="dark"):
    colors = THEMES.get(theme, THEMES["dark"])
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
html, body {{ background:{colors["app_bg"]}; color:{colors["text"]}; font-family:-apple-system,
BlinkMacSystemFont,"Segoe UI",sans-serif; margin:0; }}
body {{ padding:18px; }}
.empty {{ color:{colors["muted"]}; text-align:center; padding:80px 20px; }}
.message {{ max-width:86%; margin:0 0 16px; padding:13px 15px;
border:1px solid {colors["border"]}; border-radius:14px; background:{colors["panel_bg"]}; }}
.message.user {{ margin-left:auto; background:{colors["user_bg"]}; border-color:{colors["user_border"]}; }}
.message-meta {{ display:flex; justify-content:space-between; gap:20px;
font-size:11px; font-weight:700; color:{colors["muted"]}; margin-bottom:8px; }}
.message-text {{ white-space:normal; line-height:1.55; overflow-wrap:anywhere; }}
.attachment {{ display:inline-flex; vertical-align:top; flex-direction:column;
gap:4px; max-width:220px; margin:10px 8px 0 0; padding:9px;
border:1px solid {colors["strong_border"]}; border-radius:10px; background:{colors["raised_bg"]}; }}
.attachment span {{ color:{colors["muted"]}; font-size:11px; }}
.attachment-preview {{ width:200px; max-height:150px; object-fit:cover;
border-radius:7px; margin-bottom:4px; }}
.payload-card {{ margin-top:12px; border-top:1px solid {colors["border"]}; padding-top:12px; }}
.payload-title {{ color:{colors["muted"]}; font-size:11px; font-weight:700; margin-bottom:8px; }}
iframe {{ width:100%; min-height:360px; border:1px solid {colors["border"]};
border-radius:10px; background:{colors["app_bg"]}; }}
a {{ color:{colors["link"]}; }}
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
        self._memory_signature = None
        self._last_state = ""
        self._workspace_payload_signature = None
        self._lecture_path = ""
        self.session_id = ""
        self.session_name = ""
        self.session_started_at = time.time()
        self.pending_attachments = []
        self.remote_client = self._load_remote_client()
        self.remote_events = []
        self.remote_after = 0.0
        self._remote_next_poll = 0.0
        self.memory_store = MemoryStore(os.path.join(MEMORY_DIR, "trinity_memory.sqlite3"))
        self.workspace_manager = TrinityWorkspaceManager(BASE_DIR, load_config(CONFIG_FILE))
        self.selected_workspace_id = INBOX_WORKSPACE_ID
        self.selected_workspace_title = "Schnellsessions"
        self.theme = self._load_theme()
        self.workspace_sidebar_visible = True
        self.setAcceptDrops(True)

        self.pages = QStackedWidget()
        self.chat_page = QWidget()
        layout = QVBoxLayout(self.chat_page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        self.logo = QLabel()
        self.logo.setObjectName("logo")
        logo_path = self._logo_path()
        if logo_path:
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                self.logo.setPixmap(
                    pixmap.scaled(
                        40,
                        40,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
        self.logo.setFixedSize(46, 42)
        title = QLabel("Trinity Assistant")
        title.setObjectName("title")
        self.status = QLabel("Bereit")
        self.status.setObjectName("status")
        self.workspace_sidebar_button = QPushButton("☰")
        self.workspace_sidebar_button.setObjectName("subtle")
        self.workspace_sidebar_button.setToolTip("Arbeitsorganisation ein- oder ausklappen")
        self.workspace_sidebar_button.clicked.connect(self.toggle_workspace_sidebar)
        self.listen_button = QPushButton()
        self.listen_button.setObjectName("subtle")
        self.listen_button.setFixedSize(46, 38)
        self.listen_button.clicked.connect(self.toggle_microphone)
        self.new_session_button = QPushButton()
        self.new_session_button.setObjectName("subtle")
        self.new_session_button.setFixedSize(46, 38)
        self.new_session_button.setToolTip("Neue Session")
        self.new_session_button.clicked.connect(self.start_new_session)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["lecture", "office", "chat"])
        self.mode_combo.setToolTip("Trinity-Betriebsmodus")
        self.mode_combo.currentTextChanged.connect(self.set_runtime_mode)
        self.audio_source_button = QPushButton()
        self.audio_source_button.setObjectName("subtle")
        self.audio_source_button.setFixedSize(46, 38)
        self.audio_source_button.clicked.connect(self.toggle_audio_capture_mode)
        self.tts_button = QPushButton()
        self.tts_button.setObjectName("subtle")
        self.tts_button.setFixedSize(46, 38)
        self.tts_button.clicked.connect(self.toggle_tts)
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("theme")
        self.theme_button.setFixedSize(46, 38)
        self.theme_button.setToolTip("Zwischen Dark Mode und Hell Mode wechseln")
        self.theme_button.clicked.connect(self.toggle_theme)
        settings_button = QPushButton("⚙")
        settings_button.setObjectName("gear")
        settings_button.setFixedSize(42, 38)
        settings_button.setToolTip("Einstellungen öffnen")
        settings_button.clicked.connect(self.show_settings)
        header.addWidget(self.logo)
        header.addWidget(title)
        header.addWidget(self.workspace_sidebar_button)
        header.addStretch()
        header.addWidget(self.status)
        header.addWidget(self.listen_button)
        header.addWidget(self.audio_source_button)
        header.addWidget(self.new_session_button)
        header.addWidget(self.mode_combo)
        header.addWidget(self.tts_button)
        header.addWidget(self.theme_button)
        header.addWidget(settings_button)
        layout.addLayout(header)

        self.main_tabs = QTabWidget()
        self.main_tabs.setObjectName("workspaceTabs")

        daily_tab = QWidget()
        daily_layout = QVBoxLayout(daily_tab)
        daily_layout.setContentsMargins(0, 0, 0, 0)
        self.daily_workspace = QWebEngineView()
        self._configure_web_view(self.daily_workspace)
        daily_layout.addWidget(self.daily_workspace)

        lecture_tab = QWidget()
        lecture_layout = QVBoxLayout(lecture_tab)
        lecture_layout.setContentsMargins(0, 0, 0, 0)
        lecture_toolbar = QHBoxLayout()
        self.lecture_label = QLabel("Noch kein Foliensatz geöffnet")
        self.lecture_label.setObjectName("section")
        lecture_open_button = QPushButton("PDF öffnen")
        lecture_open_button.setObjectName("subtle")
        lecture_open_button.clicked.connect(self.choose_lecture_pdf)
        lecture_external_button = QPushButton("Extern öffnen")
        lecture_external_button.setObjectName("subtle")
        lecture_external_button.clicked.connect(self.open_lecture_externally)
        lecture_toolbar.addWidget(self.lecture_label, 1)
        lecture_toolbar.addWidget(lecture_open_button)
        lecture_toolbar.addWidget(lecture_external_button)
        self.lecture_workspace = QWebEngineView()
        self._configure_web_view(self.lecture_workspace)
        lecture_layout.addLayout(lecture_toolbar)
        lecture_layout.addWidget(self.lecture_workspace, 1)

        web_tab = QWidget()
        web_layout = QVBoxLayout(web_tab)
        web_layout.setContentsMargins(0, 0, 0, 0)
        web_toolbar = QHBoxLayout()
        self.web_address = QLineEdit("https://www.google.com")
        self.web_address.setPlaceholderText("https://…")
        self.web_address.returnPressed.connect(self.open_web_address)
        web_back_button = QPushButton("←")
        web_back_button.setObjectName("subtle")
        web_back_button.clicked.connect(lambda: self.web_workspace.back())
        web_forward_button = QPushButton("→")
        web_forward_button.setObjectName("subtle")
        web_forward_button.clicked.connect(lambda: self.web_workspace.forward())
        web_reload_button = QPushButton("Neu laden")
        web_reload_button.setObjectName("subtle")
        web_reload_button.clicked.connect(lambda: self.web_workspace.reload())
        web_open_button = QPushButton("Öffnen")
        web_open_button.setObjectName("subtle")
        web_open_button.clicked.connect(self.open_web_address)
        web_external_button = QPushButton("Extern")
        web_external_button.setObjectName("subtle")
        web_external_button.clicked.connect(self.open_web_externally)
        for widget in (
            web_back_button, web_forward_button, self.web_address, web_reload_button,
            web_open_button, web_external_button,
        ):
            web_toolbar.addWidget(widget, 1 if widget is self.web_address else 0)
        self.web_workspace = QWebEngineView()
        self._configure_web_view(self.web_workspace)
        self.web_workspace.setUrl(QUrl("https://www.google.com"))
        web_layout.addLayout(web_toolbar)
        web_layout.addWidget(self.web_workspace, 1)

        agents_tab = QWidget()
        agents_layout = QVBoxLayout(agents_tab)
        agents_layout.setContentsMargins(0, 0, 0, 0)
        self.agents_workspace = QWebEngineView()
        self._configure_web_view(self.agents_workspace)
        agents_layout.addWidget(self.agents_workspace)

        control_tab = QWidget()
        control_layout = QVBoxLayout(control_tab)
        control_layout.setContentsMargins(0, 0, 0, 0)
        self.control_workspace = QWebEngineView()
        self._configure_web_view(self.control_workspace)
        control_layout.addWidget(self.control_workspace)

        chat_tab = QWidget()
        chat_tab_layout = QVBoxLayout(chat_tab)
        chat_tab_layout.setContentsMargins(0, 0, 0, 0)
        chat_tab_layout.setSpacing(8)
        self.chat_history = QWebEngineView()
        self._configure_web_view(self.chat_history)
        self.chat_history.setHtml(_render_chat_html([], self.theme))
        chat_tab_layout.addWidget(self.chat_history, 1)

        transcript_tab = QWidget()
        transcript_layout = QVBoxLayout(transcript_tab)
        transcript_layout.setContentsMargins(0, 0, 0, 0)
        transcript_layout.setSpacing(8)
        self.transcript = QTextEdit()
        self.transcript.setObjectName("transcript")
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText(
            "Live-Mitschrift, Agentenstarts und Laufzeitlog erscheinen hier."
        )
        transcript_layout.addWidget(self.transcript)

        memory_tab = QWidget()
        memory_layout = QVBoxLayout(memory_tab)
        memory_layout.setContentsMargins(0, 0, 0, 0)
        memory_layout.setSpacing(8)
        memory_header = QHBoxLayout()
        self.memory_status = QLabel("Memory bereit")
        self.memory_status.setObjectName("section")
        bake_button = QPushButton("Memory backen")
        bake_button.setObjectName("subtle")
        bake_button.clicked.connect(self.bake_memory)
        refresh_memory_button = QPushButton("Graph aktualisieren")
        refresh_memory_button.setObjectName("subtle")
        refresh_memory_button.clicked.connect(self.refresh_memory_graph)
        memory_header.addWidget(self.memory_status, 1)
        memory_header.addWidget(bake_button)
        memory_header.addWidget(refresh_memory_button)
        self.memory_graph = QWebEngineView()
        self._configure_web_view(self.memory_graph)
        self.memory_graph.setHtml(
            render_graph_html({"nodes": [], "links": []}, self.theme)
        )
        memory_layout.addLayout(memory_header)
        memory_layout.addWidget(self.memory_graph, 1)
        self.memory_panel = memory_tab

        live_tab = QWidget()
        live_layout = QVBoxLayout(live_tab)
        live_layout.setContentsMargins(0, 0, 0, 0)
        live_layout.addWidget(transcript_tab)

        self.main_tabs.addTab(daily_tab, "Talk")
        self.main_tabs.addTab(lecture_tab, "Vortrag")
        self.main_tabs.addTab(web_tab, "Web")
        self.main_tabs.addTab(agents_tab, "Agents")
        self.main_tabs.addTab(control_tab, "Control")
        self.main_tabs.addTab(chat_tab, "Chat")
        self.main_tabs.addTab(live_tab, "Live")

        workspace_shell = QWidget()
        workspace_shell_layout = QHBoxLayout(workspace_shell)
        workspace_shell_layout.setContentsMargins(0, 0, 0, 0)
        workspace_shell_layout.setSpacing(10)
        self.workspace_sidebar = self._build_workspace_sidebar()
        workspace_shell_layout.addWidget(self.workspace_sidebar)
        workspace_shell_layout.addWidget(self.main_tabs, 1)
        layout.addWidget(workspace_shell, 1)

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
        self._update_theme_button()
        self._sync_runtime_controls()
        self._refresh_workspace_views(force=True)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(400)
        self.refresh()

    def _build_workspace_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("workspaceSidebar")
        sidebar.setFixedWidth(245)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Arbeitsräume")
        title.setObjectName("sidebarTitle")
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(4)
        title_row.addWidget(title, 1)
        title_row.addWidget(
            self._sidebar_icon_button("＋", "Neuen Arbeitsraum anlegen", self.create_workspace_from_sidebar)
        )
        title_row.addWidget(
            self._sidebar_icon_button("◰", "Neue Session im gewählten Arbeitsraum", self.start_new_session)
        )
        title_row.addWidget(
            self._sidebar_icon_button("✎", "Neue Notiz im gewählten Arbeitsraum", self.create_note_for_selected_workspace)
        )
        layout.addLayout(title_row)
        self.sidebar_dynamic_layout = QVBoxLayout()
        self.sidebar_dynamic_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_dynamic_layout.setSpacing(4)
        layout.addLayout(self.sidebar_dynamic_layout)
        self._refresh_workspace_sidebar()
        layout.addStretch()
        return sidebar

    def _clear_sidebar_dynamic_layout(self):
        while self.sidebar_dynamic_layout.count():
            item = self.sidebar_dynamic_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            child_layout = item.layout()
            if child_layout is not None:
                self._clear_layout(child_layout)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            child_layout = item.layout()
            if child_layout is not None:
                self._clear_layout(child_layout)

    def _refresh_workspace_sidebar(self):
        if not hasattr(self, "sidebar_dynamic_layout"):
            return
        self._clear_sidebar_dynamic_layout()
        try:
            workspaces = self.workspace_manager.list_workspaces()
            selected_workspace = self.workspace_manager.get_workspace(self.selected_workspace_id)
            self.selected_workspace_title = selected_workspace.title
            sessions = self.workspace_manager.list_sessions(self.selected_workspace_id, limit=8)
            notes = self.workspace_manager.list_notes(self.selected_workspace_id, limit=5)
        except (OSError, ValueError) as exc:
            self._add_sidebar_group(
                self.sidebar_dynamic_layout,
                "Fehler",
                [(f"Nicht geladen: {exc}", self._show_sidebar_placeholder)],
            )
            return

        workspace_items = workspaces[:8]
        pinned_workspaces = [item for item in workspaces if item.pinned]
        pinned_sessions = [item for item in self.workspace_manager.list_sessions(limit=20) if item.pinned]
        session_items = [
            item
            for item in sessions[:8]
        ]
        note_items = [
            (
                item.title,
                lambda checked=False, record=item: self._open_note_sidebar_item(record),
            )
            for item in notes
        ]

        self._add_pinned_sidebar_group(self.sidebar_dynamic_layout, "Angeheftet", pinned_workspaces, pinned_sessions)
        self._add_workspace_sidebar_group(self.sidebar_dynamic_layout, "", workspace_items)
        if note_items:
            self._add_sidebar_group(self.sidebar_dynamic_layout, "Notizen", note_items)
        if session_items:
            self._add_session_sidebar_group(self.sidebar_dynamic_layout, "Sessions", session_items)

    def _select_workspace_sidebar_item(self, record):
        self.selected_workspace_id = record.id
        self.selected_workspace_title = record.title
        self.status.setText(f"Arbeitsraum: {record.title}")
        self._refresh_workspace_sidebar()

    def _select_session_sidebar_item(self, record):
        self.session_id = record.id
        self.session_name = record.title
        self._chat_signature = None
        self._refresh_chat_history()
        self.status.setText(f"Session geöffnet: {record.title}")

    def _workspace_label(self, record):
        marker = "▾ " if record.id == self.selected_workspace_id else ""
        return f"{marker}{record.title}"

    def _open_note_sidebar_item(self, record):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(record.path)))
        self.status.setText(f"Notiz geöffnet: {record.title}")

    def create_note_for_selected_workspace(self):
        suggested = _default_session_name_prefix() + "Notiz"
        title, accepted = QInputDialog.getText(
            self,
            "Neue Notiz",
            f"Notiz fuer {self.selected_workspace_title}:",
            text=suggested,
        )
        if not accepted:
            return
        try:
            note = self.workspace_manager.create_note(
                self.selected_workspace_id,
                title.strip() or suggested,
            )
        except (OSError, ValueError) as exc:
            self.status.setText(f"Notiz konnte nicht erstellt werden: {exc}")
            return
        self._refresh_workspace_sidebar()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(note.path)))
        self.status.setText(f"Notiz erstellt: {note.title}")

    def create_workspace_from_sidebar(self):
        title, accepted = QInputDialog.getText(
            self,
            "Neuer Arbeitsraum",
            "Name:",
            text="",
        )
        if not accepted:
            return
        title = title.strip()
        if not title:
            self.status.setText("Arbeitsraum braucht einen Namen.")
            return
        try:
            workspace = self.workspace_manager.create_workspace(title)
        except (OSError, ValueError) as exc:
            self.status.setText(f"Arbeitsraum konnte nicht erstellt werden: {exc}")
            return
        self.selected_workspace_id = workspace.id
        self.selected_workspace_title = workspace.title
        self._refresh_workspace_sidebar()
        self.status.setText(f"Arbeitsraum erstellt: {workspace.title}")

    def summarize_session_from_sidebar(self, record):
        try:
            record = self.workspace_manager.update_session_summary_status(record.id, "queued")
            started_at = self._session_started_timestamp(record)
            display_session_id = self.session_id or record.id
            display_session_name = self.session_name or record.title
            self._summarize_previous_session_in_background(
                record.id,
                record.title,
                started_at,
                time.time(),
                display_session_id,
                display_session_name,
            )
        except (OSError, ValueError) as exc:
            self.status.setText(f"Summary konnte nicht gestartet werden: {exc}")
            return
        self._refresh_workspace_sidebar()
        self.status.setText(f"Zusammenfassung gestartet: {record.title}")

    def start_session_for_workspace(self, record):
        self.selected_workspace_id = record.id
        self.selected_workspace_title = record.title
        self._refresh_workspace_sidebar()
        self.start_new_session()

    def toggle_workspace_pinned(self, record):
        try:
            updated = self.workspace_manager.update_workspace_pinned(record.id, not record.pinned)
        except (OSError, ValueError) as exc:
            self.status.setText(f"Anheften fehlgeschlagen: {exc}")
            return
        self._refresh_workspace_sidebar()
        self.status.setText(
            f"Arbeitsraum angeheftet: {updated.title}"
            if updated.pinned
            else f"Arbeitsraum gelöst: {updated.title}"
        )

    def toggle_session_pinned(self, record):
        try:
            updated = self.workspace_manager.update_session_pinned(record.id, not record.pinned)
        except (OSError, ValueError) as exc:
            self.status.setText(f"Anheften fehlgeschlagen: {exc}")
            return
        self._refresh_workspace_sidebar()
        self.status.setText(
            f"Session angeheftet: {updated.title}"
            if updated.pinned
            else f"Session gelöst: {updated.title}"
        )

    def _session_started_timestamp(self, record):
        try:
            data = json.loads((record.path / "session.json").read_text(encoding="utf-8"))
            started_at = str(data.get("started_at") or "")
            if started_at:
                return datetime.fromisoformat(started_at).timestamp()
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        return self.session_started_at

    def _sidebar_button(self, label, callback):
        button = QPushButton(label)
        button.setObjectName("sidebarButton")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    def _add_sidebar_group(self, layout, title, items):
        label = QLabel(title)
        label.setObjectName("sidebarGroup")
        layout.addWidget(label)
        for item_label, callback in items:
            layout.addWidget(self._sidebar_button(item_label, callback))

    def _sidebar_icon_button(self, label, tooltip, callback):
        button = QPushButton(label)
        button.setObjectName("sidebarIconButton")
        button.setToolTip(tooltip)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    def _add_workspace_sidebar_group(self, layout, title, workspaces):
        if title:
            label = QLabel(title)
            label.setObjectName("sidebarGroup")
            layout.addWidget(label)
        if not workspaces:
            return
        for record in workspaces:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            row.addWidget(
                self._sidebar_button(
                    self._workspace_label(record),
                    lambda checked=False, item=record: self._select_workspace_sidebar_item(item),
                ),
                1,
            )
            row.addWidget(
                self._sidebar_icon_button(
                    "＋",
                    "Neue Session in diesem Arbeitsraum",
                    lambda checked=False, item=record: self.start_session_for_workspace(item),
                )
            )
            row.addWidget(
                self._sidebar_icon_button(
                    "★" if record.pinned else "☆",
                    "Arbeitsraum anheften oder lösen",
                    lambda checked=False, item=record: self.toggle_workspace_pinned(item),
                )
            )
            layout.addLayout(row)

    def _add_pinned_sidebar_group(self, layout, title, workspaces, sessions):
        if not workspaces and not sessions:
            return
        label = QLabel(title)
        label.setObjectName("sidebarGroup")
        layout.addWidget(label)
        for record in workspaces[:4]:
            layout.addWidget(
                self._sidebar_button(
                    f"📁 {record.title}",
                    lambda checked=False, item=record: self._select_workspace_sidebar_item(item),
                )
            )
        for record in sessions[:4]:
            layout.addWidget(
                self._sidebar_button(
                    f"📄 {record.title}",
                    lambda checked=False, item=record: self._select_session_sidebar_item(item),
                )
            )

    def _add_session_sidebar_group(self, layout, title, sessions):
        label = QLabel(title)
        label.setObjectName("sidebarGroup")
        layout.addWidget(label)
        if not sessions:
            layout.addWidget(self._sidebar_button("Noch keine Sessions", self._show_sidebar_placeholder))
            return
        for record in sessions:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            session_label = record.title
            if record.summary_status not in {"", "none"}:
                session_label = f"{session_label} · {record.summary_status}"
            row.addWidget(
                self._sidebar_button(
                    session_label,
                    lambda checked=False, item=record: self._select_session_sidebar_item(item),
                ),
                1,
            )
            row.addWidget(
                self._sidebar_icon_button(
                    "★" if record.pinned else "☆",
                    "Session anheften oder lösen",
                    lambda checked=False, item=record: self.toggle_session_pinned(item),
                )
            )
            row.addWidget(
                self._sidebar_icon_button(
                    "Σ",
                    "Diese Session im Hintergrund zusammenfassen",
                    lambda checked=False, item=record: self.summarize_session_from_sidebar(item),
                )
            )
            layout.addLayout(row)

    def _show_sidebar_placeholder(self):
        self.status.setText("Diese Arbeitsorga-Gruppe wird im nächsten Schritt vertieft.")

    def toggle_workspace_sidebar(self):
        self.workspace_sidebar_visible = not self.workspace_sidebar_visible
        self.workspace_sidebar.setVisible(self.workspace_sidebar_visible)
        self.workspace_sidebar_button.setText("☰" if self.workspace_sidebar_visible else "☷")
        self.status.setText(
            "Arbeitsorganisation eingeblendet"
            if self.workspace_sidebar_visible
            else "Arbeitsorganisation ausgeblendet"
        )

    def _load_remote_client(self):
        try:
            config = json.loads(Path(CONFIG_FILE).read_text(encoding="utf-8"))
            client = config.get("client", {})
            if client.get("enabled") and client.get("server_url") and client.get("token"):
                return RemoteTrinityClient(client["server_url"], client["token"], timeout=1.5)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        return None

    def _remote_event_for_render(self, event):
        cloned = dict(event)
        base_url = self.remote_client.server_url.rstrip("/") if self.remote_client else ""
        attachments = []
        for item in event.get("attachments", []):
            copied = dict(item)
            if str(copied.get("media_url", "")).startswith("/"):
                copied["media_url"] = base_url + copied["media_url"]
            attachments.append(copied)
        cloned["attachments"] = attachments
        payload = str(cloned.get("payload_html", ""))
        cloned["payload_html"] = re.sub(
            r"([\"'])/media\?",
            lambda match: f"{match.group(1)}{base_url}/media?",
            payload,
        )
        return cloned

    def _logo_path(self):
        candidates = [
            os.path.join(CORE_DIR, "icon.png"),
            os.path.join(BASE_DIR, "assets", "trinity_icon_new.png"),
            os.path.join(BASE_DIR, "assets", "icon.PNG"),
        ]
        return next((path for path in candidates if os.path.exists(path)), None)

    def _configure_web_view(self, view):
        view.page().setBackgroundColor(QColor(THEMES[self.theme]["app_bg"]))
        settings = view.settings()
        settings.setAttribute(
            QWebEngineSettings.LocalContentCanAccessRemoteUrls,
            True,
        )
        settings.setAttribute(
            QWebEngineSettings.LocalContentCanAccessFileUrls,
            True,
        )

    def _load_theme(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
                config = json.load(handle)
            theme = config.get("system", {}).get("classic_theme", "dark")
        except (OSError, json.JSONDecodeError):
            theme = "dark"
        return theme if theme in THEMES else "dark"

    def _save_theme(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
                config = json.load(handle)
        except (OSError, json.JSONDecodeError):
            config = {}
        config.setdefault("system", {})["classic_theme"] = self.theme
        with open(CONFIG_FILE, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2, ensure_ascii=False)

    def _update_theme_button(self):
        if self.theme == "dark":
            self.theme_button.setText("Hell")
        else:
            self.theme_button.setText("Dunkel")

    def _sync_settings_theme(self):
        if hasattr(self, "settings_page"):
            self.settings_page.config.setdefault("system", {})["classic_theme"] = self.theme
            self.settings_page.apply_stylesheet()

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self._save_theme()
        self._apply_style()
        self._sync_settings_theme()
        self._update_theme_button()
        self._chat_signature = None
        self._memory_signature = None
        self._refresh_chat_history()
        self.refresh_memory_graph()

    def _apply_style(self):
        colors = THEMES[self.theme]
        for view in (getattr(self, "chat_history", None), getattr(self, "memory_graph", None)):
            if view is not None:
                view.page().setBackgroundColor(QColor(colors["app_bg"]))
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background: {colors["app_bg"]}; color: {colors["text"]}; }}
            QLabel#title {{ font-size: 22px; font-weight: 650; }}
            QLabel#section {{ color: {colors["muted"]}; font-size: 12px; font-weight: 600; }}
            QLabel#logo {{ background: transparent; }}
            QLabel#status {{
                background: {colors["raised_bg"]}; border: 1px solid {colors["border"]};
                border-radius: 12px; padding: 6px 12px; color: {colors["muted"]};
            }}
            QTextEdit {{
                background: {colors["panel_bg"]}; color: {colors["text"]};
                border: 1px solid {colors["border"]}; border-radius: 8px;
                padding: 10px; selection-background-color: {colors["selection"]};
            }}
            QLineEdit {{
                background: {colors["panel_bg"]}; color: {colors["text"]};
                border: 1px solid {colors["border"]}; border-radius: 8px; padding: 8px;
            }}
            QTextEdit#transcript {{ font-family: "SF Mono", Consolas, monospace; }}
            QLabel#attachments {{
                background: {colors["raised_bg"]}; border: 1px solid {colors["strong_border"]};
                border-radius: 8px; padding: 8px 10px; color: {colors["text"]};
            }}
            QPushButton {{
                background: {colors["raised_bg"]}; color: {colors["text"]};
                border: 1px solid {colors["strong_border"]}; border-radius: 8px;
                padding: 9px 16px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {colors["hover_bg"]}; }}
            QPushButton#primary {{ background: {colors["primary_bg"]}; color: {colors["primary_text"]}; }}
            QPushButton#subtle {{ padding: 7px 10px; color: {colors["muted"]}; }}
            QPushButton#gear {{ font-size: 20px; padding: 0; }}
            QPushButton#theme {{ padding: 7px 13px; }}
            QWidget#workspaceSidebar {{
                background: {colors["panel_bg"]};
                border: 1px solid {colors["border"]};
                border-radius: 12px;
            }}
            QLabel#sidebarTitle {{
                color: {colors["text"]};
                font-size: 14px;
                font-weight: 700;
                padding: 2px 2px 6px;
            }}
            QLabel#sidebarGroup {{
                color: {colors["muted"]};
                background: transparent;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.5px;
                padding: 12px 2px 2px;
            }}
            QLabel#sidebarHint {{
                color: {colors["muted"]};
                font-size: 11px;
                padding: 8px 2px 0;
            }}
            QPushButton#sidebarButton {{
                background: transparent;
                border: 0;
                border-radius: 8px;
                color: {colors["text"]};
                font-weight: 500;
                text-align: left;
                padding: 7px 9px;
            }}
            QPushButton#sidebarButton:hover {{
                background: {colors["hover_bg"]};
            }}
            QPushButton#sidebarIconButton {{
                background: transparent;
                border: 1px solid {colors["border"]};
                border-radius: 7px;
                color: {colors["muted"]};
                min-width: 25px;
                max-width: 28px;
                padding: 5px 0;
                font-weight: 700;
            }}
            QPushButton#sidebarIconButton:hover {{
                background: {colors["hover_bg"]};
                color: {colors["text"]};
            }}
            QTabWidget::pane {{
                border: 1px solid {colors["border"]}; border-radius: 10px;
                top: -1px;
            }}
            QTabBar::tab {{
                background: {colors["panel_bg"]}; color: {colors["muted"]};
                border: 1px solid {colors["border"]}; border-bottom: none;
                padding: 8px 14px; border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
            QTabBar::tab:selected {{ background: {colors["raised_bg"]}; color: {colors["text"]}; }}
            QTabWidget#workspaceTabs::pane {{ border-radius: 12px; }}
            QTabWidget#workspaceTabs QTabBar::tab {{ min-width: 92px; padding: 10px 15px; }}
        """)

    def refresh(self):
        if self.remote_client:
            self._refresh_remote_chat()
            self._refresh_workspace_views()
            return
        self._refresh_state()
        self._refresh_transcript()
        self._refresh_chat_history()
        self._refresh_memory_if_changed()
        self._refresh_workspace_views()

    def _payload_for_workspace(self):
        if self.remote_client:
            try:
                result = self.remote_client.latest_payload()
            except RuntimeError:
                return "", None, QUrl()
            return (
                str(result.get("html") or ""),
                float(result.get("timestamp", 0) or 0),
                QUrl(self.remote_client.server_url.rstrip("/") + "/"),
            )
        payload_path = os.path.join(CORE_DIR, "payload.html")
        try:
            signature = (os.path.getmtime(payload_path), os.path.getsize(payload_path))
            payload = Path(payload_path).read_text(encoding="utf-8")
        except OSError:
            signature = None
            payload = ""
        return payload, signature, QUrl.fromLocalFile(BASE_DIR + os.sep)

    def _workspace_html(self, title, subtitle, payload):
        colors = THEMES[self.theme]
        if payload.strip():
            content = payload.replace("<!-- FULLPAGE -->", "")
        else:
            content = (
                '<div class="empty"><div class="orb"></div>'
                f"<h2>{html.escape(title)}</h2><p>{html.escape(subtitle)}</p></div>"
            )
        return f"""<!doctype html><html><head><meta charset='utf-8'><style>
            body {{ margin:0; min-height:100vh; background:{colors['app_bg']}; color:{colors['text']}; font:16px system-ui,sans-serif; }}
            .empty {{ min-height:70vh; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; color:{colors['muted']}; }}
            .empty h2 {{ color:{colors['text']}; margin:18px 0 6px; }} .empty p {{ max-width:440px; margin:0; line-height:1.5; }}
            .orb {{ width:132px; height:132px; border-radius:50%; background:radial-gradient(circle at 38% 35%, #d8b4fe, #7c3aed 45%, #172554 72%); box-shadow:0 0 48px #7c3aed88; animation:pulse 4s ease-in-out infinite; }}
            @keyframes pulse {{ 50% {{ transform:scale(1.06); box-shadow:0 0 72px #a855f788; }} }}
        </style></head><body>{content}</body></html>"""

    def _panel_html(self, title, subtitle, cards):
        colors = THEMES[self.theme]
        cards_html = []
        for card in cards:
            icon = html.escape(card.get("icon", "•"))
            heading = html.escape(card.get("title", ""))
            body = html.escape(card.get("body", ""))
            badge = html.escape(card.get("badge", ""))
            cards_html.append(
                "<article class='card'>"
                f"<div class='icon'>{icon}</div>"
                "<div class='card-body'>"
                f"<h3>{heading}</h3><p>{body}</p>"
                "</div>"
                f"<span class='badge'>{badge}</span>"
                "</article>"
            )
        return f"""<!doctype html><html><head><meta charset='utf-8'><style>
            body {{ margin:0; min-height:100vh; background:{colors['app_bg']}; color:{colors['text']}; font:15px system-ui,sans-serif; }}
            main {{ max-width:980px; margin:0 auto; padding:34px 28px 48px; }}
            h1 {{ margin:0; font-size:32px; letter-spacing:-0.04em; }}
            .sub {{ color:{colors['muted']}; margin:8px 0 24px; line-height:1.5; }}
            .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:14px; }}
            .card {{ display:flex; align-items:center; gap:14px; min-height:86px; padding:16px;
                border:1px solid {colors['border']}; border-radius:18px; background:{colors['panel_bg']}; }}
            .icon {{ width:42px; height:42px; border-radius:14px; display:flex; align-items:center; justify-content:center;
                background:{colors['raised_bg']}; color:{colors['link']}; font-size:20px; flex:0 0 auto; }}
            .card-body {{ flex:1; min-width:0; }}
            h3 {{ margin:0 0 4px; font-size:16px; }}
            p {{ margin:0; color:{colors['muted']}; line-height:1.4; }}
            .badge {{ border:1px solid {colors['strong_border']}; border-radius:999px; padding:5px 9px;
                color:{colors['muted']}; font-size:11px; white-space:nowrap; }}
        </style></head><body><main><h1>{html.escape(title)}</h1>
        <p class='sub'>{html.escape(subtitle)}</p><section class='grid'>{''.join(cards_html)}</section></main></body></html>"""

    def _agents_html(self):
        return self._panel_html(
            "Agents",
            "Zentrale Sicht auf laufende Aufträge, direkt startbare Hauptagenten und geplante Automatismen.",
            [
                {
                    "icon": "▶",
                    "title": "Laufende Aufträge",
                    "body": "Hier erscheinen aktive Pi-, Codex- oder Trinity-Jobs mit Status, Ergebnis und Log.",
                    "badge": "Jobs",
                },
                {
                    "icon": "⚙",
                    "title": "Startbare Hauptagenten",
                    "body": "Später lassen sich Mailrundlauf, Recherche, Medienjobs oder eigene BrainVault-Agenten direkt starten.",
                    "badge": "Trigger",
                },
                {
                    "icon": "◷",
                    "title": "Geplante Automatismen",
                    "body": "Wiederkehrende Abläufe wie Morgen-Mailzusammenfassung oder Tagesbriefing werden hier verwaltet.",
                    "badge": "Planung",
                },
            ],
        )

    def _control_html(self):
        return self._panel_html(
            "Control",
            "Arbeitsnahe Steuerung fuer Memory, RAG, Skills, Sessions, Prompts und Diagnose.",
            [
                {
                    "icon": "◎",
                    "title": "Übersicht",
                    "body": "Systemzustand, aktive Verbindung, Runtime und wichtige Hinweise.",
                    "badge": "Status",
                },
                {
                    "icon": "▦",
                    "title": "RAG und Dateien",
                    "body": "Index, Wissensquellen und geladene Dateien werden hier gebündelt.",
                    "badge": "Wissen",
                },
                {
                    "icon": "✦",
                    "title": "Dreaming und Memory",
                    "body": "Memory-Graph, Zusammenfassungen und Hintergrundverdichtung wandern aus der Arbeitsansicht hierher.",
                    "badge": "Memory",
                },
                {
                    "icon": "✎",
                    "title": "System- und Userprompt",
                    "body": "Persona, Arbeitsregeln und persönliche Hinweise bleiben sichtbar, aber getrennt von harten API-Settings.",
                    "badge": "Prompts",
                },
            ],
        )

    def _refresh_workspace_views(self, force=False):
        payload, payload_signature, base_url = self._payload_for_workspace()
        signature = (payload_signature, self._last_state, self.theme)
        if not force and signature == self._workspace_payload_signature:
            return
        self._workspace_payload_signature = signature
        daily_html = self._workspace_html(
            "Trinity im Talk",
            "Mikrofon und Lautsprecher oben steuern. Neue Ergebnisse erscheinen hier.",
            payload,
        )
        self.daily_workspace.setHtml(daily_html, base_url)
        self.agents_workspace.setHtml(self._agents_html(), base_url)
        self.control_workspace.setHtml(self._control_html(), base_url)

    def choose_lecture_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Foliensatz als PDF öffnen",
            self._lecture_path or str(Path.home()),
            "PDF-Dateien (*.pdf)",
        )
        if not path:
            return
        self._lecture_path = path
        self.lecture_label.setText(Path(path).name)
        self.lecture_workspace.setUrl(QUrl.fromLocalFile(path))
        self.main_tabs.setCurrentIndex(1)

    def open_lecture_externally(self):
        if self._lecture_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._lecture_path))
        else:
            self.choose_lecture_pdf()

    def open_web_address(self):
        url = QUrl.fromUserInput(self.web_address.text().strip())
        if not url.isValid() or not url.scheme():
            self.status.setText("Bitte eine gültige Webadresse eingeben")
            return
        self.web_address.setText(url.toString())
        self.web_workspace.setUrl(url)

    def open_web_externally(self):
        url = QUrl.fromUserInput(self.web_address.text().strip())
        if url.isValid() and url.scheme():
            QDesktopServices.openUrl(url)

    def toggle_presenter_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _refresh_remote_chat(self):
        if time.monotonic() < self._remote_next_poll:
            return
        self._remote_next_poll = time.monotonic() + 1.2
        try:
            incoming = self.remote_client.events_since(self.remote_after)
        except RuntimeError as exc:
            self.status.setText(f"Server nicht erreichbar: {exc}")
            return
        if incoming:
            matching = [
                event for event in incoming
                if not self.session_id or event.get("session_id") == self.session_id
            ]
            self.remote_events.extend(self._remote_event_for_render(event) for event in matching)
            self.remote_after = max(
                self.remote_after,
                max(float(event.get("timestamp", 0) or 0) for event in incoming),
            )
            self.chat_history.setHtml(
                _render_chat_html(self.remote_events, self.theme),
                QUrl(self.remote_client.server_url + "/"),
            )
        self.status.setText("Server verbunden")

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
        signature_parts = []
        try:
            if path:
                signature_parts.append((path, os.path.getmtime(path), os.path.getsize(path)))
            for log_name in ("runtime.log", "launcher.log"):
                log_path = os.path.join(LOGS_DIR, log_name)
                if os.path.exists(log_path):
                    signature_parts.append(
                        (
                            log_path,
                            os.path.getmtime(log_path),
                            os.path.getsize(log_path),
                        )
                    )
        except OSError:
            return
        signature = tuple(signature_parts)
        if signature == self._transcript_signature:
            return
        self._transcript_path = path
        self._transcript_signature = signature
        content = _build_live_log_text(path)
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
        if self.session_id:
            events = [
                event for event in events
                if event.get("session_id") == self.session_id
            ]
        base_url = QUrl.fromLocalFile(BASE_DIR + os.sep)
        self.chat_history.setHtml(_render_chat_html(events, self.theme), base_url)

    def _runtime_values(self):
        if self.remote_client:
            try:
                return self.remote_client.get_runtime()
            except RuntimeError:
                pass
        config = load_config(CONFIG_FILE)
        system = config.get("system", {})
        return {
            "mode": str(system.get("mode", "lecture") or "lecture"),
            "microphone_enabled": bool(system.get("microphone_enabled", True)),
            "audio_capture_mode": str(system.get("audio_capture_mode", "mic_only") or "mic_only"),
            "tts_enabled": bool(system.get("tts_enabled", True)),
        }

    def _set_runtime_values(self, updates):
        if self.remote_client:
            try:
                return self.remote_client.set_runtime(updates)
            except RuntimeError as exc:
                self.status.setText(f"Laufzeitsteuerung fehlgeschlagen: {exc}")
                return None
        config = load_config(CONFIG_FILE)
        system = config.setdefault("system", {})
        system.update(updates)
        save_config(CONFIG_FILE, config)
        return self._runtime_values()

    def _sync_runtime_controls(self, values=None):
        values = values or self._runtime_values()
        microphone_enabled = bool(values.get("microphone_enabled", True))
        tts_enabled = bool(values.get("tts_enabled", True))
        audio_capture_mode = str(values.get("audio_capture_mode", "mic_only") or "mic_only")
        self.listen_button.setText("🎙" if microphone_enabled else "🔇")
        self.listen_button.setToolTip("Mikrofon aktiv" if microphone_enabled else "Mikrofon pausiert")
        self.audio_source_button.setText("👥" if audio_capture_mode == "mic_and_system" else "🧑")
        self.audio_source_button.setToolTip(
            "Eigenes Mikro + Meeting/System-Audio (benötigt Loopback-Gerät)"
            if audio_capture_mode == "mic_and_system"
            else "Nur eigenes Mikro"
        )
        self.new_session_button.setText("＋")
        self.tts_button.setText("🔊" if tts_enabled else "🔈")
        self.tts_button.setToolTip("Desktop-TTS aktiv" if tts_enabled else "Desktop-TTS pausiert")
        mode = values.get("mode", "lecture")
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentText(mode if mode in {"lecture", "office", "chat"} else "lecture")
        self.mode_combo.blockSignals(False)

    def toggle_microphone(self):
        values = self._runtime_values()
        result = self._set_runtime_values(
            {"microphone_enabled": not values["microphone_enabled"]}
        )
        if result:
            self._sync_runtime_controls(result)
            self.status.setText("Mikrofon aktiviert" if result["microphone_enabled"] else "Mikrofon pausiert")

    def toggle_audio_capture_mode(self):
        values = self._runtime_values()
        current = str(values.get("audio_capture_mode", "mic_only") or "mic_only")
        next_mode = "mic_and_system" if current == "mic_only" else "mic_only"
        result = self._set_runtime_values({"audio_capture_mode": next_mode})
        if result:
            self._sync_runtime_controls(result)
            self.status.setText(
                "Audioquelle: Mikro + Meeting/System (Loopback nötig)"
                if next_mode == "mic_and_system"
                else "Audioquelle: eigenes Mikro"
            )

    def toggle_tts(self):
        values = self._runtime_values()
        result = self._set_runtime_values({"tts_enabled": not values["tts_enabled"]})
        if result:
            self._sync_runtime_controls(result)
            self.status.setText("Desktop-TTS aktiviert" if result["tts_enabled"] else "Desktop-TTS pausiert")

    def set_runtime_mode(self, mode):
        result = self._set_runtime_values({"mode": mode})
        if result:
            self._sync_runtime_controls(result)
            self.status.setText(f"Trinity-Modus: {result['mode']}")

    def start_new_session(self):
        suggested_name = _default_session_name_prefix()
        name, accepted = QInputDialog.getText(
            self,
            "Neue Session",
            "Sessionname (optional):",
            text=suggested_name,
        )
        if not accepted:
            return
        old_session_id = self.session_id
        old_session_name = self.session_name or "Classic Desktop"
        old_started_at = self.session_started_at
        old_ended_at = time.time()
        session = self.workspace_manager.create_session(
            name.strip() or suggested_name,
            workspace_id=self.selected_workspace_id or INBOX_WORKSPACE_ID,
            mode=self.mode_combo.currentText(),
        )
        self.session_id = session.id
        self.session_name = session.title
        self.session_started_at = time.time()
        self._summarize_previous_session_in_background(
            old_session_id,
            old_session_name,
            old_started_at,
            old_ended_at,
            self.session_id,
            self.session_name,
        )
        self.remote_events = []
        self.remote_after = time.time()
        self.pending_attachments = []
        self._update_attachment_summary()
        self._chat_signature = None
        self.chat_history.setHtml(_render_chat_html([], self.theme))
        self._refresh_workspace_sidebar()
        label = self.session_name or "ohne Namen"
        self.status.setText(f"Neue Session: {label}")

    def _summarize_previous_session_in_background(
        self,
        session_id,
        session_name,
        started_at,
        ended_at,
        display_session_id,
        display_session_name,
    ):
        closing_session_id = session_id or f"classic-unscoped-{int(started_at)}"

        def worker():
            payload = {
                "session_id": closing_session_id,
                "session_name": session_name,
                "display_session_id": display_session_id,
                "display_session_name": display_session_name,
                "include_unscoped": not bool(session_id),
                "started_at": started_at,
                "ended_at": ended_at,
            }
            try:
                if self.remote_client:
                    self.remote_client.end_session(payload)
                else:
                    TrinityBridge(BASE_DIR).end_session(payload)
            except Exception as exc:  # pylint: disable=broad-except
                append_chat_event(
                    CHAT_HISTORY_FILE,
                    {
                        "request_id": f"session-summary-error-{closing_session_id}",
                        "role": "assistant",
                        "source": "session-summary",
                        "text": f"Session-Summary konnte nicht gestartet werden: {exc}",
                        "session_id": display_session_id,
                        "session_name": display_session_name,
                        "metadata": {
                            "original_session_id": closing_session_id,
                            "original_session_name": session_name,
                        },
                    },
                )

        threading.Thread(
            target=worker,
            name=f"trinity-classic-session-summary-{closing_session_id[:12]}",
            daemon=True,
        ).start()

    def _refresh_memory_if_changed(self):
        path = os.path.join(MEMORY_DIR, "trinity_memory.sqlite3")
        try:
            signature = (os.path.getmtime(path), os.path.getsize(path))
        except OSError:
            signature = None
        if signature == self._memory_signature:
            return
        self._memory_signature = signature
        self.refresh_memory_graph()

    def refresh_memory_graph(self):
        status = self.memory_store.status()
        graph = self.memory_store.graph_data()
        self.memory_status.setText(
            f"{status['memories']} Memories · {status['links']} Links · "
            f"{status['unbaked']} unbaked"
        )
        base_url = QUrl.fromLocalFile(BASE_DIR + os.sep)
        self.memory_graph.setHtml(render_graph_html(graph, self.theme), base_url)

    def bake_memory(self):
        try:
            result = self.memory_store.bake_chat_history(CHAT_HISTORY_FILE)
            self.status.setText(
                f"Memory gebacken: {result['imported']} importiert, "
                f"{result['baked']} verdichtet"
            )
            self._memory_signature = None
            self.refresh_memory_graph()
        except (OSError, ValueError) as exc:
            self.status.setText(f"Memory Bake fehlgeschlagen: {exc}")

    def choose_attachments(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Anlagen auswählen",
            str(Path.home()),
            (
                "Unterstützte Dateien (*.txt *.md *.markdown *.csv *.tsv *.json "
                "*.yaml *.yml *.log *.py *.js *.html *.css *.pdf *.png *.jpg "
                "*.jpeg *.webp *.gif *.xlsx *.xlsm);;Alle Dateien (*)"
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
        if self.remote_client:
            try:
                self.remote_client.send_message(
                    text,
                    self.pending_attachments,
                    session_id=self.session_id,
                    session_name=self.session_name,
                )
                self.command.clear()
                self.pending_attachments = []
                self._update_attachment_summary()
                self.status.setText("Auftrag an Trinity-Server gesendet")
                self._remote_next_poll = 0
            except RuntimeError as exc:
                self.status.setText(f"Senden fehlgeschlagen: {exc}")
            return

        request = build_chat_request(
            text,
            self.pending_attachments,
            history_recorded=True,
        )
        request["session_id"] = self.session_id
        request["session_name"] = self.session_name
        append_chat_event(
            CHAT_HISTORY_FILE,
            {
                "request_id": request["request_id"],
                "role": "user",
                "source": "classic",
                "text": text,
                "attachments": self.pending_attachments,
                "session_id": self.session_id,
                "session_name": self.session_name,
            },
        )
        try:
            session_id = self.memory_store.ensure_session("classic", "Classic UI")
            self.memory_store.add_message(
                session_id,
                "user",
                text,
                {"source": "classic", "request_id": request["request_id"]},
            )
        except Exception:
            pass
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
        self._sync_settings_theme()
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
