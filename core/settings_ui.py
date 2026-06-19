import sys
import os
import platform
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QCheckBox, QComboBox, QGroupBox, QFormLayout,
                             QTextEdit, QTabWidget, QDoubleSpinBox, QSpinBox,
                             QScrollArea, QFrame, QMessageBox, QRadioButton,
                             QButtonGroup, QSizePolicy)

from platform_adapters import create_tts_backend, find_codex_executable, find_opencode_executable
from configuration import DEFAULT_CONFIG, load_config, save_config
from ui_modes import resolve_ui_modes


CORE_DIR = os.path.dirname(os.path.abspath(__file__))


class SettingsWindow(QMainWindow):
    def __init__(self, config_path, embedded=False, on_return=None):
        super().__init__()
        self.config_path = config_path
        self.embedded = embedded
        self.on_return = on_return
        self.soul_path = os.path.join(CORE_DIR, "Soul.md")
        self.user_path = os.path.join(CORE_DIR, "User.md")
        self.tts_backend = create_tts_backend()
        self.setWindowTitle("Trinity Assistant – Einstellungen")
        self.setMinimumSize(600, 700)
        
        self.load_config()
        self.init_ui()
        self.apply_stylesheet()
        
    def load_config(self):
        self.config = load_config(self.config_path)

    def load_text_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def save_text_file(self, path, content):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def save_config(self):
        # LLM Slots
        if "active_slot" not in self.config["llm"]:
             self.config["llm"]["active_slot"] = "local"
             
        if self.llm_radio_local.isChecked(): self.config["llm"]["active_slot"] = "local"
        elif self.llm_radio_remote1.isChecked(): self.config["llm"]["active_slot"] = "remote_1"
        elif self.llm_radio_remote2.isChecked(): self.config["llm"]["active_slot"] = "remote_2"

        self.config["llm"]["local"]["url"] = self.local_url_edit.text()
        self.config["llm"]["local"]["model"] = self.local_model_edit.text()
        self.config["llm"]["local"]["api_key"] = self.local_key_edit.text()

        self.config["llm"]["remote_1"]["url"] = self.remote1_url_edit.text()
        self.config["llm"]["remote_1"]["model"] = self.remote1_model_edit.text()
        self.config["llm"]["remote_1"]["api_key"] = self.remote1_key_edit.text()

        self.config["llm"]["remote_2"]["url"] = self.remote2_url_edit.text()
        self.config["llm"]["remote_2"]["model"] = self.remote2_model_edit.text()
        self.config["llm"]["remote_2"]["api_key"] = self.remote2_key_edit.text()
        
        # APIs
        self.config["apis"]["tavily"] = self.tavily_key_edit.text()
        self.config["apis"]["fal_ai"] = self.fal_key_edit.text()
        
        # Persona
        self.config["persona"]["agent_name"] = self.agent_name_edit.text()
        variants_text = self.trigger_variants_edit.text()
        self.config["persona"]["trigger_variants"] = [v.strip() for v in variants_text.split(",") if v.strip()]
        
        # Image
        self.config["image"]["primary_model"] = self.image_primary_edit.text()
        self.config["image"]["fallback_model"] = self.image_fallback_edit.text()
        
        # STT
        self.config["stt"]["model"] = self.stt_model_combo.currentText()
        self.config["stt"]["silence_threshold"] = self.stt_thresh_spin.value()
        self.config["stt"]["chunk_duration"] = self.stt_duration_spin.value()
        self.config["stt"]["show_volume_meter"] = getattr(self, 'vol_meter_cb', QCheckBox()).isChecked()
        
        # TTS
        self.config["tts"]["voice"] = self.tts_voice_edit.text()
        
        # Proactive
        if "proactive" not in self.config:
            self.config["proactive"] = {}
        self.config["proactive"]["heartbeat_enabled"] = getattr(self, 'hb_cb', QCheckBox()).isChecked()
        self.config["proactive"]["bubbles_enabled"] = getattr(self, 'bubble_cb', QCheckBox()).isChecked()
        self.config["proactive"]["visuals_enabled"] = getattr(self, 'visual_cb', QCheckBox()).isChecked()
        self.config["proactive"]["interval_minutes"] = getattr(self, 'hb_interval_spin', QSpinBox()).value()
        
        # System
        if "system" not in self.config:
            self.config["system"] = {}
        self._sync_ui_mode_controls()
        eyes_enabled = getattr(self, "eyes_ui_cb", QCheckBox()).isChecked()
        classic_enabled = getattr(self, "classic_ui_cb", QCheckBox()).isChecked()
        web_enabled = getattr(self, "web_ui_cb", QCheckBox()).isChecked()
        terminal_enabled = getattr(self, "terminal_cb", QCheckBox()).isChecked()
        if not eyes_enabled and not classic_enabled and not web_enabled:
            terminal_enabled = True
        self.config["system"]["eyes_ui_enabled"] = eyes_enabled
        self.config["system"]["classic_ui_enabled"] = classic_enabled
        self.config["system"]["web_ui_enabled"] = web_enabled
        self.config["system"]["terminal_cli_enabled"] = terminal_enabled
        self.config["system"]["show_terminal"] = terminal_enabled
        self.config["system"]["mode"] = getattr(self, 'mode_combo', QComboBox()).currentText()
        self.config["system"]["windows_speech_enabled"] = getattr(
            self,
            "windows_speech_cb",
            QCheckBox(),
        ).isChecked()
        
        # Audio Routing
        if "audio_routing" not in self.config:
            self.config["audio_routing"] = {}
        if hasattr(self, 'private_audio_combo'):
            self.config["audio_routing"]["private_device"] = self.private_audio_combo.currentText()
        if hasattr(self, 'public_audio_combo'):
            self.config["audio_routing"]["public_device"] = self.public_audio_combo.currentText()
            
        # Telegram
        if "telegram" not in self.config:
            self.config["telegram"] = {}
        if hasattr(self, 'telegram_cb'):
            self.config["telegram"]["enabled"] = self.telegram_cb.isChecked()
            self.config["telegram"]["bot_token"] = self.tg_token_edit.text()
            self.config["telegram"]["chat_id"] = self.tg_chatid_edit.text()

        # Companion Bridge
        if "companion" not in self.config:
            self.config["companion"] = {}
        if hasattr(self, "companion_cb"):
            self.config["companion"]["enabled"] = self.companion_cb.isChecked()
            self.config["companion"]["host"] = (
                self.companion_host_edit.text().strip() or "127.0.0.1"
            )
            self.config["companion"]["port"] = self.companion_port_spin.value()
            self.config["companion"]["token"] = self.companion_token_edit.text()

        # Remote server client
        if hasattr(self, "remote_client_cb"):
            self.config.setdefault("client", {})["enabled"] = self.remote_client_cb.isChecked()
            self.config["client"]["server_url"] = self.remote_server_url_edit.text().strip()
            self.config["client"]["username"] = self.remote_username_edit.text().strip()
            self.config["client"]["token"] = self.remote_token_edit.text().strip()

        # Codex
        if "codex" not in self.config:
            self.config["codex"] = {}
        if hasattr(self, "codex_cb"):
            projects = {}
            for line in self.codex_projects_edit.toPlainText().splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                alias, path = stripped.split("=", 1)
                alias = alias.strip()
                path = path.strip()
                if alias and path:
                    projects[alias] = path

            self.config["codex"]["enabled"] = self.codex_cb.isChecked()
            self.config["codex"]["executable"] = (
                self.codex_executable_edit.text().strip() or "codex"
            )
            self.config["codex"]["default_project"] = (
                self.codex_default_project_edit.text().strip()
            )
            self.config["codex"]["projects"] = projects
            self.config["codex"]["sandbox"] = self.codex_sandbox_combo.currentText()
            self.config["codex"]["timeout_seconds"] = (
                self.codex_timeout_spin.value()
            )
            self.config["codex"]["max_output_chars"] = (
                self.codex_output_spin.value()
            )
            self.config["codex"]["ephemeral"] = (
                self.codex_ephemeral_cb.isChecked()
            )
            self.config["codex"]["network_access"] = (
                self.codex_network_cb.isChecked()
            )

        # OpenCode
        if "opencode" not in self.config:
            self.config["opencode"] = {}
        if hasattr(self, "opencode_cb"):
            projects = {}
            for line in self.opencode_projects_edit.toPlainText().splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                alias, path = stripped.split("=", 1)
                alias = alias.strip()
                path = path.strip()
                if alias and path:
                    projects[alias] = path

            self.config["opencode"]["enabled"] = self.opencode_cb.isChecked()
            self.config["opencode"]["executable"] = (
                self.opencode_executable_edit.text().strip() or "opencode"
            )
            self.config["opencode"]["default_project"] = (
                self.opencode_default_project_edit.text().strip()
            )
            self.config["opencode"]["projects"] = projects
            self.config["opencode"]["agent"] = self.opencode_agent_edit.text().strip()
            self.config["opencode"]["model"] = self.opencode_model_edit.text().strip()
            self.config["opencode"]["timeout_seconds"] = (
                self.opencode_timeout_spin.value()
            )
            self.config["opencode"]["max_output_chars"] = (
                self.opencode_output_spin.value()
            )

        # ComfyUI
        if "comfyui" not in self.config:
            self.config["comfyui"] = {}
        if hasattr(self, 'comfyui_cb'):
            self.config["comfyui"]["enabled"] = self.comfyui_cb.isChecked()
            self.config["comfyui"]["server_url"] = self.comfyui_url_edit.text().strip()
            # self.config["comfyui"]["default_workflow"] = self.comfyui_workflow_edit.text().strip()
            
        # Proactive Additions
        if hasattr(self, 'auto_rag_cb'):
            self.config["proactive"]["auto_rag_indexing"] = self.auto_rag_cb.isChecked()
        
        # Config-Datei speichern
        save_config(self.config_path, self.config)
        
        # Soul.md speichern
        self.save_text_file(self.soul_path, self.soul_edit.toPlainText())
        
        # User.md speichern
        self.save_text_file(self.user_path, self.user_edit.toPlainText())
        
        if self.embedded and self.on_return:
            self.on_return(True)
        else:
            QMessageBox.information(
                self,
                "Gespeichert",
                "Einstellungen gespeichert.\n"
                "Neue Anfragen übernehmen LLM-, Persona-, Telegram-, TTS- und "
                "Modus-Änderungen automatisch. Nur geänderte Oberflächenstarts "
                "(Augen-/Classic-/Terminal-Kombination) und die Companion Bridge "
                "brauchen einen Neustart.",
            )

    def _return_to_chat(self):
        if self.embedded and self.on_return:
            self.on_return(False)
        else:
            self.close()

    def apply_stylesheet(self):
        theme = self.config.get("system", {}).get("classic_theme", "dark")
        light = theme == "light"
        colors = {
            "app_bg": "#f8fafc" if light else "#09090b",
            "panel_bg": "#ffffff" if light else "#121214",
            "field_bg": "#ffffff" if light else "#09090b",
            "field_focus": "#f1f5f9" if light else "#121214",
            "raised_bg": "#eef2f7" if light else "#18181b",
            "hover_bg": "#e2e8f0" if light else "#27272a",
            "text": "#0f172a" if light else "#f4f4f5",
            "muted": "#475569" if light else "#d4d4d8",
            "faint": "#64748b" if light else "#71717a",
            "border": "#d7dde7" if light else "#27272a",
            "strong_border": "#cbd5e1" if light else "#3f3f46",
            "primary_bg": "#0f172a" if light else "#f4f4f5",
            "primary_text": "#ffffff" if light else "#09090b",
            "selection": "#bfdbfe" if light else "#3f3f46",
            "warning": "#b45309" if light else "#d29922",
            "info": "#0369a1" if light else "#8aadf4",
        }
        hover_rgba = "rgba(15, 23, 42, 0.06)" if light else "rgba(255, 255, 255, 0.05)"
        group_rgba = "rgba(15, 23, 42, 0.02)" if light else "rgba(255, 255, 255, 0.01)"
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {colors["app_bg"]}; }}
            
            QTabWidget::pane {{ 
                border: 1px solid {colors["border"]}; 
                background: {colors["panel_bg"]}; 
                border-bottom-left-radius: 12px; 
                border-bottom-right-radius: 12px;
                border-top-right-radius: 12px;
            }}
            
            QTabBar::tab {{ 
                background: transparent; 
                color: {colors["faint"]}; 
                padding: 12px 18px; 
                margin-right: 2px; 
                font-weight: 500;
                font-size: 12px;
                border-top-left-radius: 8px; 
                border-top-right-radius: 8px; 
            }}
            
            QTabBar::tab:hover {{
                background: {hover_rgba};
                color: {colors["text"]};
            }}
            
            QTabBar::tab:selected {{ 
                background: {colors["panel_bg"]}; 
                color: {colors["text"]}; 
                border-bottom: 2px solid {colors["text"]};
            }}
            
            QGroupBox {{ 
                color: {colors["text"]}; 
                font-size: 14px;
                font-weight: bold; 
                border: 1px solid {colors["border"]}; 
                border-radius: 10px; 
                margin-top: 25px; 
                padding-top: 25px; 
                background: {group_rgba};
            }}
            
            QGroupBox::title {{ 
                subcontrol-origin: margin; 
                left: 15px; 
                padding: 0 10px; 
                color: {colors["text"]};
            }}
            
            QLabel {{ color: {colors["muted"]}; font-size: 13px; }}
            QLabel#settingsTitle {{ color: {colors["text"]}; margin-bottom: 8px; }}
            
            QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {{ 
                background: {colors["field_bg"]}; 
                color: {colors["text"]}; 
                border: 1px solid {colors["border"]}; 
                border-radius: 6px; 
                padding: 10px; 
                min-height: 20px;
                selection-background-color: {colors["selection"]};
            }}
            
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{ 
                border-color: {colors["faint"]}; 
                background: {colors["field_focus"]};
            }}
            
            QComboBox QAbstractItemView {{
                background: {colors["field_bg"]};
                color: {colors["text"]};
                selection-background-color: {colors["selection"]};
                border: 1px solid {colors["border"]};
            }}
            
            QTextEdit {{ 
                background: {colors["field_bg"]}; 
                color: {colors["text"]}; 
                border: 1px solid {colors["border"]}; 
                border-radius: 8px; 
                padding: 12px; 
                font-family: 'SF Mono', 'Menlo', monospace; 
                font-size: 13px;
                selection-background-color: {colors["selection"]};
            }}
            
            QCheckBox {{ color: {colors["muted"]}; spacing: 10px; font-size: 13px; }}
            QCheckBox::indicator {{ width: 20px; height: 20px; border-radius: 5px; border: 1px solid {colors["strong_border"]}; background: {colors["field_bg"]}; }}
            QCheckBox::indicator:checked {{ background: {colors["primary_bg"]}; border: 1px solid {colors["primary_bg"]}; image: none; }}
            
            QRadioButton {{ color: {colors["muted"]}; spacing: 10px; padding: 6px; font-size: 13px; }}
            QRadioButton::indicator {{ width: 20px; height: 20px; border-radius: 11px; border: 1px solid {colors["strong_border"]}; background: {colors["field_bg"]}; }}
            QRadioButton::indicator:checked {{ background: {colors["primary_bg"]}; border: 5px solid {colors["field_bg"]}; }}
            
            QPushButton {{ 
                background: {colors["raised_bg"]}; 
                color: {colors["text"]}; 
                border: 1px solid {colors["border"]}; 
                border-radius: 8px; 
                padding: 12px 24px; 
                font-weight: 600;
                font-size: 13px;
            }}
            
            QPushButton:hover {{ background: {colors["hover_bg"]}; border-color: {colors["faint"]}; }}
            
            QPushButton#saveBtn {{ 
                background: {colors["primary_bg"]}; 
                color: {colors["primary_text"]}; 
                font-weight: bold; 
                border: none;
            }}
            
            QPushButton#saveBtn:hover {{ background: {colors["text"]}; color: {colors["app_bg"]}; }}
            
            QScrollArea {{ background: {colors["panel_bg"]}; border: none; }}
            QWidget#settingsScrollContent {{ background: {colors["panel_bg"]}; }}
            QScrollBar:vertical {{ border: none; background: {colors["app_bg"]}; width: 10px; margin: 0px; }}
            QScrollBar::handle:vertical {{ background: {colors["raised_bg"]}; min-height: 20px; border-radius: 5px; }}
            QScrollBar::handle:vertical:hover {{ background: {colors["hover_bg"]}; }}
        """)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # Header
        header_row = QHBoxLayout()
        header = QLabel("Trinity Assistant – Einstellungen")
        header.setObjectName("settingsTitle")
        header.setFont(QFont("", 18, QFont.Bold))
        header_row.addWidget(header)
        header_row.addStretch()
        if self.embedded:
            header_back = QPushButton("Zurück zum Chat")
            header_back.clicked.connect(self._return_to_chat)
            header_row.addWidget(header_back)
        main_layout.addLayout(header_row)
        
        # Tabs
        tabs = QTabWidget()
        tabs.setUsesScrollButtons(True)
        tabs.setElideMode(Qt.ElideRight)
        tabs.addTab(self._create_persona_tab(), "🤖 Persona")
        tabs.addTab(self._create_llm_tab(), "🧠 LLM")
        tabs.addTab(self._create_api_tab(), "🔑 APIs & Bild")
        tabs.addTab(self._create_stt_tts_tab(), "🎙️ Sprache")
        tabs.addTab(self._create_audio_tab(), "🔊 Audio-Routing")
        tabs.addTab(self._create_proactive_tab(), "🚀 Proaktiv")
        tabs.addTab(self._create_codex_tab(), "⌨️ Codex")
        tabs.addTab(self._create_opencode_tab(), "🛠️ OpenCode")
        tabs.addTab(self._scrollable_tab(self._create_system_tab()), "🖥️ System")
        tabs.addTab(self._create_soul_tab(), "📝 Soul")
        tabs.addTab(self._create_user_tab(), "👤 User")
        main_layout.addWidget(tabs)
        
        # Buttons
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton(
            "Zurück zum Chat" if self.embedded else "Abbrechen"
        )
        cancel_btn.clicked.connect(self._return_to_chat)
        
        save_btn = QPushButton(
            "Speichern und zurück zum Chat" if self.embedded else "Speichern"
        )
        save_btn.setObjectName("saveBtn")
        save_btn.clicked.connect(self.save_config)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        main_layout.addLayout(btn_layout)

    @staticmethod
    def _scrollable_tab(content):
        """Keep longer settings pages readable instead of letting Qt shrink forms."""
        content.setObjectName("settingsScrollContent")
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)
        return scroll

    # --- TAB: Proaktiv ---
    def _create_proactive_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("Proaktiver Agentic Companion (Phase 4)")
        form = QFormLayout()
        
        proactive_conf = self.config.get("proactive", {})
        
        self.hb_cb = QCheckBox("Heartbeat aktivieren (Regelmäßige Analyse)")
        self.hb_cb.setChecked(proactive_conf.get("heartbeat_enabled", False))
        form.addRow(self.hb_cb)
        
        self.hb_interval_spin = QSpinBox()
        self.hb_interval_spin.setRange(1, 30)
        self.hb_interval_spin.setValue(proactive_conf.get("interval_minutes", 2))
        form.addRow("Intervall (Minuten):", self.hb_interval_spin)
        
        self.bubble_cb = QCheckBox("UI-Bubbles aktivieren (Ampelsystem)")
        self.bubble_cb.setChecked(proactive_conf.get("bubbles_enabled", False))
        form.addRow(self.bubble_cb)
        
        self.visual_cb = QCheckBox("Proaktive Visuals aktivieren (Zusatzinfos einblenden)")
        self.visual_cb.setChecked(proactive_conf.get("visuals_enabled", False))
        form.addRow(self.visual_cb)
        
        self.auto_rag_cb = QCheckBox("Deep Memory: Session-Summaries automatisch ins RAG indexieren")
        self.auto_rag_cb.setChecked(proactive_conf.get("auto_rag_indexing", False))
        form.addRow(self.auto_rag_cb)
        
        hint = QLabel("Achtung: Heartbeat verursacht im Hintergrund Traffic zum LLM.\nNur bei performanten Modellen/APIs empfohlen!")
        hint.setStyleSheet("color: #ffaa00; font-size: 11px; margin-top: 10px;")
        hint.setWordWrap(True)
        form.addRow("", hint)
        
        # --- Telegram Bridge ---
        tg_conf = self.config.get("telegram", {})
        
        form.addRow(QLabel(" ")) # Spacer
        tg_label = QLabel("Telegram Bridge (Single-Monitor Setup)")
        tg_label.setStyleSheet("color: #00bfff; font-weight: bold; font-size: 13px;")
        form.addRow(tg_label)
        
        self.telegram_cb = QCheckBox("Bubble-Nachrichten per Telegram-DM senden")
        self.telegram_cb.setChecked(tg_conf.get("enabled", False))
        form.addRow(self.telegram_cb)
        
        self.tg_token_edit = QLineEdit(tg_conf.get("bot_token", ""))
        self.tg_token_edit.setPlaceholderText("z z.B. 123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
        self.tg_token_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Bot Token:", self.tg_token_edit)
        
        self.tg_chatid_edit = QLineEdit(tg_conf.get("chat_id", ""))
        self.tg_chatid_edit.setPlaceholderText("z.B. 123456789")
        form.addRow("Chat ID:", self.tg_chatid_edit)
        
        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()
        return widget

    # --- TAB: Codex ---
    def _create_codex_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Lokaler Codex-Agent")
        form = QFormLayout()
        codex_conf = self.config.get("codex", {})

        self.codex_cb = QCheckBox(
            "Codex-Aufträge per Sprache, Chat und Telegram erlauben"
        )
        self.codex_cb.setChecked(codex_conf.get("enabled", False))
        form.addRow(self.codex_cb)

        detected = find_codex_executable()
        status_text = (
            f"Codex gefunden: {detected}"
            if detected
            else "Codex wurde im Systempfad noch nicht gefunden."
        )
        status = QLabel(status_text)
        status.setWordWrap(True)
        status.setStyleSheet(
            "color: #7ee787; font-size: 11px;"
            if detected
            else "color: #d29922; font-size: 11px;"
        )
        form.addRow("Status:", status)

        self.codex_executable_edit = QLineEdit(
            codex_conf.get("executable", "codex")
        )
        self.codex_executable_edit.setPlaceholderText(
            "codex oder vollständiger Pfad zur Codex-Anwendung"
        )
        form.addRow("Programm:", self.codex_executable_edit)

        projects = codex_conf.get("projects", {})
        projects_text = ""
        if isinstance(projects, dict):
            projects_text = "\n".join(
                f"{alias} = {path}" for alias, path in projects.items()
            )
        self.codex_projects_edit = QTextEdit()
        self.codex_projects_edit.setPlainText(projects_text)
        self.codex_projects_edit.setPlaceholderText(
            "Automatismen = /vollständiger/Pfad/zum/Projekt\n"
            "Lehre = C:\\Users\\Name\\Projekte\\Lehre"
        )
        self.codex_projects_edit.setMinimumHeight(130)
        form.addRow("Freigegebene Projekte:", self.codex_projects_edit)

        project_hint = QLabel(
            "Eine Zeile pro Projekt: Name = vollständiger Ordnerpfad. "
            "Telegram-Aufträge können ausschließlich diese Ordner verwenden."
        )
        project_hint.setWordWrap(True)
        project_hint.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow("", project_hint)

        self.codex_default_project_edit = QLineEdit(
            codex_conf.get("default_project", "")
        )
        self.codex_default_project_edit.setPlaceholderText(
            "z.B. Automatismen"
        )
        form.addRow("Standardprojekt:", self.codex_default_project_edit)

        self.codex_sandbox_combo = QComboBox()
        self.codex_sandbox_combo.addItems(["workspace-write", "read-only"])
        sandbox = codex_conf.get("sandbox", "workspace-write")
        if sandbox in {"workspace-write", "read-only"}:
            self.codex_sandbox_combo.setCurrentText(sandbox)
        form.addRow("Codex-Rechte:", self.codex_sandbox_combo)

        self.codex_timeout_spin = QSpinBox()
        self.codex_timeout_spin.setRange(30, 3600)
        self.codex_timeout_spin.setSuffix(" Sekunden")
        self.codex_timeout_spin.setValue(
            int(codex_conf.get("timeout_seconds", 900))
        )
        form.addRow("Zeitlimit:", self.codex_timeout_spin)

        self.codex_output_spin = QSpinBox()
        self.codex_output_spin.setRange(500, 12000)
        self.codex_output_spin.setSingleStep(500)
        self.codex_output_spin.setSuffix(" Zeichen")
        self.codex_output_spin.setValue(
            int(codex_conf.get("max_output_chars", 3200))
        )
        form.addRow("Antwortlänge:", self.codex_output_spin)

        self.codex_ephemeral_cb = QCheckBox(
            "Codex-Läufe nicht als dauerhafte Sitzungen speichern"
        )
        self.codex_ephemeral_cb.setChecked(
            codex_conf.get("ephemeral", True)
        )
        form.addRow(self.codex_ephemeral_cb)

        self.codex_network_cb = QCheckBox(
            "Von Codex gestarteten Programmen Netzwerkzugriff erlauben"
        )
        self.codex_network_cb.setChecked(
            codex_conf.get("network_access", False)
        )
        form.addRow(self.codex_network_cb)

        security_hint = QLabel(
            "Empfohlen: workspace-write, Netzwerk aus. Codex darf in "
            "fernausgelösten Läufen Entwürfe vorbereiten, aber nichts versenden, "
            "veröffentlichen, pushen oder deployen."
        )
        security_hint.setWordWrap(True)
        security_hint.setStyleSheet("color: #d29922; font-size: 11px;")
        form.addRow("", security_hint)

        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()
        return widget

    # --- TAB: OpenCode ---
    def _create_opencode_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Lokaler OpenCode-Agent")
        form = QFormLayout()
        opencode_conf = self.config.get("opencode", {})

        self.opencode_cb = QCheckBox(
            "OpenCode-Aufträge per Sprache, Chat, Telegram und Companion erlauben"
        )
        self.opencode_cb.setChecked(opencode_conf.get("enabled", False))
        form.addRow(self.opencode_cb)

        detected = find_opencode_executable()
        status_text = (
            f"OpenCode gefunden: {detected}"
            if detected
            else "OpenCode wurde im Systempfad noch nicht gefunden."
        )
        status = QLabel(status_text)
        status.setWordWrap(True)
        status.setStyleSheet(
            "color: #7ee787; font-size: 11px;"
            if detected
            else "color: #d29922; font-size: 11px;"
        )
        form.addRow("Status:", status)

        self.opencode_executable_edit = QLineEdit(
            opencode_conf.get("executable", "opencode")
        )
        self.opencode_executable_edit.setPlaceholderText(
            "opencode oder vollständiger Pfad zur OpenCode-Anwendung"
        )
        form.addRow("Programm:", self.opencode_executable_edit)

        projects = opencode_conf.get("projects", {})
        projects_text = ""
        if isinstance(projects, dict):
            projects_text = "\n".join(
                f"{alias} = {path}" for alias, path in projects.items()
            )
        self.opencode_projects_edit = QTextEdit()
        self.opencode_projects_edit.setPlainText(projects_text)
        self.opencode_projects_edit.setPlaceholderText(
            "Automatismen = /vollständiger/Pfad/zum/Projekt\n"
            "Mail = C:\\Users\\Name\\Projekte\\MailAutomationen"
        )
        self.opencode_projects_edit.setMinimumHeight(130)
        form.addRow("Freigegebene Projekte:", self.opencode_projects_edit)

        project_hint = QLabel(
            "Eine Zeile pro Projekt: Name = vollständiger Ordnerpfad. "
            "OpenCode läuft ausschließlich in diesen Ordnern."
        )
        project_hint.setWordWrap(True)
        project_hint.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow("", project_hint)

        self.opencode_default_project_edit = QLineEdit(
            opencode_conf.get("default_project", "")
        )
        self.opencode_default_project_edit.setPlaceholderText(
            "z.B. Automatismen"
        )
        form.addRow("Standardprojekt:", self.opencode_default_project_edit)

        self.opencode_agent_edit = QLineEdit(opencode_conf.get("agent", "build"))
        self.opencode_agent_edit.setPlaceholderText("z.B. build oder plan")
        form.addRow("OpenCode-Agent:", self.opencode_agent_edit)

        self.opencode_model_edit = QLineEdit(opencode_conf.get("model", ""))
        self.opencode_model_edit.setPlaceholderText(
            "optional, z.B. provider/model"
        )
        form.addRow("Modell:", self.opencode_model_edit)

        self.opencode_timeout_spin = QSpinBox()
        self.opencode_timeout_spin.setRange(30, 7200)
        self.opencode_timeout_spin.setSuffix(" Sekunden")
        self.opencode_timeout_spin.setValue(
            int(opencode_conf.get("timeout_seconds", 900))
        )
        form.addRow("Zeitlimit:", self.opencode_timeout_spin)

        self.opencode_output_spin = QSpinBox()
        self.opencode_output_spin.setRange(500, 12000)
        self.opencode_output_spin.setSingleStep(500)
        self.opencode_output_spin.setSuffix(" Zeichen")
        self.opencode_output_spin.setValue(
            int(opencode_conf.get("max_output_chars", 3200))
        )
        form.addRow("Antwortlänge:", self.opencode_output_spin)

        security_hint = QLabel(
            "OpenCode nutzt `opencode run` im jeweiligen Projektordner. "
            "Fernausgelöste Läufe sollen Entwürfe vorbereiten, aber nichts "
            "versenden, löschen, veröffentlichen oder deployen."
        )
        security_hint.setWordWrap(True)
        security_hint.setStyleSheet("color: #d29922; font-size: 11px;")
        form.addRow("", security_hint)

        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()
        return widget

    # --- TAB: System ---
    def _create_system_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("System & App-Verhalten")
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignTop)
        
        system_conf = self.config.get("system", {})
        ui_modes = resolve_ui_modes(system_conf)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["office", "lecture", "chat"])
        self.mode_combo.setCurrentText(system_conf.get("mode", "office"))
        form.addRow("Trinity Modus:", self.mode_combo)
        
        mode_hint = QLabel("<b>Office</b>: Standard (STT+TTS an).<br><b>Lecture</b>: Vorlesung optimiert.<br><b>Chat</b>: STT+TTS aus (nur Flüstern/Telegram).")
        mode_hint.setStyleSheet("color: #888; font-size: 11px;")
        mode_hint.setWordWrap(True)
        form.addRow("", mode_hint)

        form.addRow(QLabel(" "))
        ui_label = QLabel("Bedienoberflächen")
        ui_label.setStyleSheet(
            "color: #00bfff; font-weight: bold; font-size: 13px;"
        )
        form.addRow(ui_label)

        self.eyes_ui_cb = QCheckBox(
            "Augen-UI für Vorlesung und schwebende Bedienung"
        )
        self.eyes_ui_cb.setChecked(ui_modes["eyes"])
        form.addRow(self.eyes_ui_cb)

        self.classic_ui_cb = QCheckBox(
            "Classic-UI mit Mitschrift, Ergebnissen und Texteingabe"
        )
        self.classic_ui_cb.setChecked(ui_modes["classic"])
        form.addRow(self.classic_ui_cb)

        self.web_ui_cb = QCheckBox(
            "WebUI im Browser starten (lokal unter http://127.0.0.1:8765/)"
        )
        self.web_ui_cb.setChecked(ui_modes["web"])
        form.addRow(self.web_ui_cb)

        self.terminal_cb = QCheckBox(
            "Terminal-CLI mit Mitschrift, Log-Ausgabe und Texteingabe"
        )
        self.terminal_cb.setChecked(ui_modes["terminal"])
        form.addRow(self.terminal_cb)

        self.ui_mode_hint = QLabel()
        self.ui_mode_hint.setWordWrap(True)
        self.ui_mode_hint.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow("", self.ui_mode_hint)

        self.eyes_ui_cb.stateChanged.connect(self._sync_ui_mode_controls)
        self.classic_ui_cb.stateChanged.connect(self._sync_ui_mode_controls)
        self.web_ui_cb.stateChanged.connect(self._sync_ui_mode_controls)
        self.terminal_cb.stateChanged.connect(self._sync_ui_mode_controls)
        self._sync_ui_mode_controls()

        if platform.system() == "Windows":
            self.windows_speech_cb = QCheckBox(
                "Experimentelle Windows-Spracheingabe aktivieren"
            )
            self.windows_speech_cb.setChecked(
                system_conf.get("windows_speech_enabled", False)
            )
            form.addRow(self.windows_speech_cb)

            speech_hint = QLabel(
                "Zunächst deaktiviert lassen und Trinity per Flüsterfeld testen. "
                "Whisper wird erst geladen, wenn diese Option aktiv ist."
            )
            speech_hint.setStyleSheet("color: #d29922; font-size: 11px;")
            speech_hint.setWordWrap(True)
            form.addRow("", speech_hint)
        
        hint = QLabel(
            "Mehrere Oberflächen können gleichzeitig aktiv sein. Wenn Augen- und "
            "Classic-UI ausgeschaltet sind, wird die Terminal-CLI automatisch "
            "aktiviert. Änderungen benötigen einen Neustart der App."
        )
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)
        form.addRow("", hint)
        
        group.setLayout(form)
        layout.addWidget(group)

        companion_conf = self.config.get("companion", {})
        companion_group = QGroupBox("Companion Bridge (iPhone / iPad / Smart Glass)")
        companion_form = QFormLayout()
        companion_form.setSpacing(14)
        companion_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        companion_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        companion_form.setFormAlignment(Qt.AlignTop)

        self.companion_cb = QCheckBox(
            "Bridge beim Trinity-Start öffnen"
        )
        self.companion_cb.setChecked(companion_conf.get("enabled", False))
        companion_form.addRow(self.companion_cb)

        self.companion_host_edit = QLineEdit(
            str(companion_conf.get("host", "127.0.0.1"))
        )
        self.companion_host_edit.setPlaceholderText(
            "127.0.0.1 nur lokal, 0.0.0.0 für Tailscale"
        )
        companion_form.addRow("Host:", self.companion_host_edit)

        self.companion_port_spin = QSpinBox()
        self.companion_port_spin.setRange(1024, 65535)
        try:
            companion_port = int(companion_conf.get("port", 8765) or 8765)
        except (TypeError, ValueError):
            companion_port = 8765
        self.companion_port_spin.setValue(companion_port)
        companion_form.addRow("Port:", self.companion_port_spin)

        self.companion_token_edit = QLineEdit(
            str(companion_conf.get("token", ""))
        )
        self.companion_token_edit.setEchoMode(QLineEdit.Password)
        self.companion_token_edit.setPlaceholderText(
            "Optional, aber für Tailscale empfohlen"
        )
        companion_form.addRow("Bearer Token:", self.companion_token_edit)

        companion_test_btn = QPushButton("🔗 Bridge testen")
        companion_test_btn.clicked.connect(self._test_companion_bridge)
        companion_form.addRow("", companion_test_btn)

        companion_hint = QLabel(
            "Für iPhone/iPad über Tailscale: Host auf 0.0.0.0 setzen, "
            "Port z.B. 8765. In der Companion-App dann "
            "http://TAILSCALE-IP:8765 und denselben Bearer Token eintragen. "
            "Änderungen brauchen einen Neustart von Trinity."
        )
        companion_hint.setStyleSheet("color: #888; font-size: 11px;")
        companion_hint.setWordWrap(True)
        companion_form.addRow("", companion_hint)

        companion_group.setLayout(companion_form)
        layout.addWidget(companion_group)

        client_conf = self.config.get("client", {})
        client_group = QGroupBox("Trinity-Server Client (Linux, Mac oder Windows)")
        client_form = QFormLayout()
        client_form.setSpacing(14)
        client_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        client_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        client_form.setFormAlignment(Qt.AlignTop)
        self.remote_client_cb = QCheckBox(
            "Diesen Desktop als Client eines entfernten Trinity-Servers verwenden"
        )
        self.remote_client_cb.setChecked(client_conf.get("enabled", False))
        client_form.addRow(self.remote_client_cb)
        self.remote_server_url_edit = QLineEdit(str(client_conf.get("server_url", "")))
        self.remote_server_url_edit.setPlaceholderText("http://TAILSCALE-IP:8765")
        client_form.addRow("Server-URL:", self.remote_server_url_edit)
        self.remote_username_edit = QLineEdit(str(client_conf.get("username", "")))
        client_form.addRow("Benutzername:", self.remote_username_edit)
        self.remote_token_edit = QLineEdit(str(client_conf.get("token", "")))
        self.remote_token_edit.setEchoMode(QLineEdit.Password)
        client_form.addRow("Sitzungstoken:", self.remote_token_edit)
        client_hint = QLabel(
            "Am einfachsten per Terminal anmelden: `trinity client login --url "
            "http://TAILSCALE-IP:8765`. Das speichert URL und Sitzungstoken. "
            "Nach Speichern und Neustart nutzt die Classic-UI den entfernten Server."
        )
        client_hint.setWordWrap(True)
        client_hint.setStyleSheet("color: #888; font-size: 11px;")
        client_form.addRow("", client_hint)
        client_group.setLayout(client_form)
        layout.addWidget(client_group)
        layout.addStretch()
        return widget

    def _test_companion_bridge(self):
        host = self.companion_host_edit.text().strip() or "127.0.0.1"
        port = self.companion_port_spin.value()
        probe_host = "127.0.0.1" if host == "0.0.0.0" else host
        url = f"http://{probe_host}:{port}/health"
        headers = {}
        token = self.companion_token_edit.text().strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            import requests

            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200 and response.json().get("ok"):
                QMessageBox.information(
                    self,
                    "✅ Verbunden",
                    f"Companion Bridge erreichbar:\n{url}",
                )
            elif response.status_code == 401:
                QMessageBox.warning(
                    self,
                    "⚠️ Token falsch",
                    "Die Bridge ist erreichbar, lehnt aber den Bearer Token ab.",
                )
            else:
                QMessageBox.warning(
                    self,
                    "⚠️ Antwort nicht OK",
                    f"Bridge antwortet mit Status {response.status_code}.",
                )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Nicht erreichbar",
                "Die Bridge läuft vermutlich noch nicht. Speichern, Trinity neu "
                f"starten und erneut testen.\n\n{exc}",
            )

    def _sync_ui_mode_controls(self):
        if not all(
            hasattr(self, name)
            for name in ("eyes_ui_cb", "classic_ui_cb", "web_ui_cb", "terminal_cb")
        ):
            return

        gui_enabled = (
            self.eyes_ui_cb.isChecked()
            or self.classic_ui_cb.isChecked()
            or self.web_ui_cb.isChecked()
        )
        if not gui_enabled:
            self.terminal_cb.blockSignals(True)
            self.terminal_cb.setChecked(True)
            self.terminal_cb.blockSignals(False)
            self.terminal_cb.setEnabled(False)
            message = (
                "Headless-Modus aktiv: Ohne grafische Oberfläche bleibt die "
                "Terminal-CLI zwingend eingeschaltet."
            )
        else:
            self.terminal_cb.setEnabled(True)
            message = (
                "Mindestens eine Oberfläche muss aktiv bleiben. Augen, Classic "
                "und WebUI können gemeinsam verwendet werden."
            )
        if hasattr(self, "ui_mode_hint"):
            self.ui_mode_hint.setText(message)

    # --- TAB: Audio-Routing (Souffleur) ---
    def _create_audio_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("Souffleur-Skill (Dynamisches Audio-Routing)")
        form = QFormLayout()
        
        devices = self.tts_backend.list_output_devices()
        if not devices:
            devices = ["Standard"]
            
        routing_conf = self.config.get("audio_routing", {})
        
        self.private_audio_combo = QComboBox()
        self.private_audio_combo.addItems(devices)
        curr_priv = routing_conf.get("private_device", "Standard")
        if curr_priv in devices:
            self.private_audio_combo.setCurrentText(curr_priv)
        form.addRow("Privates Gerät (AirPods):", self.private_audio_combo)
        
        self.public_audio_combo = QComboBox()
        self.public_audio_combo.addItems(devices)
        curr_pub = routing_conf.get("public_device", "Standard")
        if curr_pub in devices:
            self.public_audio_combo.setCurrentText(curr_pub)
        form.addRow("Plenum Gerät (Lautsprecher):", self.public_audio_combo)
        
        hint = QLabel("Wenn Trinity einen Text mit dem unsichtbaren [SPEAKER]-Tag generiert, leitet sie die Sprache automatisch auf das 'Plenum Gerät' um. Andernfalls spricht sie über das 'Private Gerät'.")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)
        form.addRow("", hint)
        
        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()
        return widget

    # --- TAB: Persona ---
    def _create_persona_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("Agent-Identität")
        form = QFormLayout()
        
        self.agent_name_edit = QLineEdit(self.config["persona"]["agent_name"])
        form.addRow("Agent-Name:", self.agent_name_edit)
        
        variants = ", ".join(self.config["persona"]["trigger_variants"])
        self.trigger_variants_edit = QLineEdit(variants)
        self.trigger_variants_edit.setPlaceholderText("trinity, triniti, trindy, ...")
        form.addRow("Wake-Word Varianten:", self.trigger_variants_edit)
        
        hint = QLabel("Kommagetrennte Liste. Whisper hört nicht immer exakt – hier alternative Schreibweisen eintragen.")
        hint.setStyleSheet("color: #666; font-size: 11px;")
        hint.setWordWrap(True)
        form.addRow("", hint)
        
        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()
        return widget

    # --- TAB: LLM ---
    def _create_llm_tab(self):
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        
        llm_conf = self.config.get("llm", {})
        active = llm_conf.get("active_slot", "local")
        self.llm_group = QButtonGroup(self)

        # Helper to create LLM sections
        def create_llm_box(title, key, radio_attr, url_attr, model_attr, key_attr):
            box = QGroupBox(title)
            form = QFormLayout()
            form.setSpacing(12)
            form.setLabelAlignment(Qt.AlignRight)
            
            radio = QRadioButton("Diesen Provider als aktiv markieren")
            radio.setChecked(active == key)
            setattr(self, radio_attr, radio)
            self.llm_group.addButton(radio)
            form.addRow(radio)
            
            data = llm_conf.get(key, {})
            url_edit = QLineEdit(data.get("url", ""))
            url_edit.setMinimumWidth(400)
            setattr(self, url_attr, url_edit)
            form.addRow("URL:", url_edit)
            
            model_edit = QLineEdit(data.get("model", ""))
            setattr(self, model_attr, model_edit)
            form.addRow("Modell:", model_edit)
            
            key_edit = QLineEdit(data.get("api_key", ""))
            key_edit.setEchoMode(QLineEdit.Password)
            setattr(self, key_attr, key_edit)
            form.addRow("API Key:", key_edit)
            
            box.setLayout(form)
            return box

        layout.addWidget(create_llm_box("🧠 LLM 1: Lokal (z.B. LMStudio / Ollama)", "local", 
                                       "llm_radio_local", "local_url_edit", "local_model_edit", "local_key_edit"))
        
        layout.addWidget(create_llm_box("🌐 LLM 2: Remote (z.B. OpenRouter / DeepSeek)", "remote_1", 
                                       "llm_radio_remote1", "remote1_url_edit", "remote1_model_edit", "remote1_key_edit"))
        
        layout.addWidget(create_llm_box("📡 LLM 3: Alternative (z.B. Groq / Custom)", "remote_2", 
                                       "llm_radio_remote2", "remote2_url_edit", "remote2_model_edit", "remote2_key_edit"))

        test_btn = QPushButton("🔗 Aktives LLM testen")
        test_btn.setMinimumHeight(42)
        test_btn.clicked.connect(self._test_llm_connection)
        layout.addWidget(test_btn)
        
        layout.addStretch()
        scroll.setWidget(content)
        QVBoxLayout(widget).addWidget(scroll)
        return widget

    def _test_llm_connection(self):
        if self.llm_radio_local.isChecked():
            url = self.local_url_edit.text().strip()
            model = self.local_model_edit.text().strip()
            api_key = self.local_key_edit.text().strip() or "lm-studio"
        elif self.llm_radio_remote1.isChecked():
            url = self.remote1_url_edit.text().strip()
            model = self.remote1_model_edit.text().strip()
            api_key = self.remote1_key_edit.text().strip()
        else:
            url = self.remote2_url_edit.text().strip()
            model = self.remote2_model_edit.text().strip()
            api_key = self.remote2_key_edit.text().strip()

        if not url or not model:
            QMessageBox.warning(
                self,
                "LLM-Konfiguration unvollständig",
                "Bitte URL und Modell des aktiven Providers eintragen.",
            )
            return

        try:
            import requests

            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost",
                    "X-Title": "Trinity Assistant",
                },
                json={
                    "model": model,
                    "max_tokens": 48,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Antworte ausschließlich mit: Verbindung erfolgreich",
                        }
                    ],
                },
                timeout=30,
            )
            response.raise_for_status()
            message = response.json()["choices"][0]["message"]
            answer = (
                message.get("content")
                or message.get("reasoning_content")
                or "Verbindung erfolgreich"
            ).strip()
            QMessageBox.information(
                self,
                "LLM erreichbar",
                f"Die API hat erfolgreich geantwortet:\n\n{answer[:300]}",
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "LLM nicht erreichbar",
                f"Die Verbindung ist fehlgeschlagen:\n\n{exc}",
            )

    # --- TAB: APIs & Image ---
    def _create_api_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        api_group = QGroupBox("Web-Suche & Bildgenerierung")
        api_form = QFormLayout()
        
        self.tavily_key_edit = QLineEdit(self.config["apis"]["tavily"])
        self.tavily_key_edit.setEchoMode(QLineEdit.Password)
        api_form.addRow("Tavily API Key:", self.tavily_key_edit)
        
        self.fal_key_edit = QLineEdit(self.config["apis"]["fal_ai"])
        self.fal_key_edit.setEchoMode(QLineEdit.Password)
        api_form.addRow("Fal.ai API Key:", self.fal_key_edit)
        
        api_group.setLayout(api_form)
        layout.addWidget(api_group)
        
        img_group = QGroupBox("Bild-Modelle (fal.ai)")
        img_form = QFormLayout()
        
        self.image_primary_edit = QLineEdit(self.config["image"]["primary_model"])
        img_form.addRow("Primäres Modell:", self.image_primary_edit)
        
        self.image_fallback_edit = QLineEdit(self.config["image"]["fallback_model"])
        img_form.addRow("Fallback-Modell:", self.image_fallback_edit)
        
        hint = QLabel("Primäres Modell wird zuerst versucht. Bei Fehler wechselt Trinity automatisch zum Fallback.")
        hint.setStyleSheet("color: #666; font-size: 11px;")
        hint.setWordWrap(True)
        img_form.addRow("", hint)
        
        img_group.setLayout(img_form)
        layout.addWidget(img_group)

        # --- ComfyUI Server ---
        comfyui_conf = self.config.get("comfyui", {})

        comfy_group = QGroupBox("ComfyUI Server (Lokale / Tailscale Generierung)")
        comfy_form = QFormLayout()
        comfy_form.setSpacing(15)
        comfy_form.setLabelAlignment(Qt.AlignRight)

        self.comfyui_cb = QCheckBox("ComfyUI aktivieren")
        self.comfyui_cb.setChecked(comfyui_conf.get("enabled", False))
        comfy_form.addRow(self.comfyui_cb)

        self.comfyui_url_edit = QLineEdit(comfyui_conf.get("server_url", ""))
        self.comfyui_url_edit.setPlaceholderText("z.B. http://100.122.13.123:8188")
        self.comfyui_url_edit.setMinimumWidth(380)

        test_btn = QPushButton("🔗 Test")
        test_btn.setMinimumHeight(40)
        test_btn.setFixedWidth(120)
        test_btn.clicked.connect(self._test_comfyui_connection)
        
        url_layout = QHBoxLayout()
        url_layout.addWidget(self.comfyui_url_edit)
        url_layout.addWidget(test_btn)
        comfy_form.addRow("Server URL:", url_layout)

        comfy_hint = QLabel(
            "Trinity wählt Workflows automatisch basierend auf deiner Anfrage aus.\n"
            "Server erreichbar? → Test-Button nutzen.\n"
            "Trigger: 'lokales Bild', 'flux render', 'mach ein video', 'song schreiben' …"
        )
        comfy_hint.setStyleSheet("color: #8aadf4; font-size: 12px; margin-top: 15px; font-weight: 500;")
        comfy_hint.setWordWrap(True)
        comfy_form.addRow(comfy_hint)

        comfy_group.setLayout(comfy_form)
        layout.addWidget(comfy_group)

        layout.addStretch()
        return widget

    def _test_comfyui_connection(self):
        """Pingt den ComfyUI-Server und zeigt eine Statusmeldung."""
        url = self.comfyui_url_edit.text().strip().rstrip("/")
        if not url:
            QMessageBox.warning(self, "Kein URL", "Bitte zuerst eine Server-URL eintragen.")
            return
        try:
            import requests
            resp = requests.get(f"{url}/system_stats", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                python_ver = data.get("system", {}).get("python_version", "?")
                QMessageBox.information(self, "✅ Verbunden",
                    f"ComfyUI-Server erreichbar!\nPython: {python_ver}")
            else:
                QMessageBox.warning(self, "⚠️ Fehler",
                    f"Server antwortet mit Status {resp.status_code}.")
        except Exception as e:
            QMessageBox.critical(self, "❌ Nicht erreichbar",
                f"Konnte den Server nicht erreichen:\n{e}")

    # --- TAB: STT/TTS ---
    def _create_stt_tts_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        stt_group = QGroupBox("Spracherkennung (STT)")
        stt_form = QFormLayout()
        
        self.stt_model_combo = QComboBox()
        self.stt_model_combo.addItems([
            "tiny",
            "base",
            "small",
            "medium",
            "large-v3"
        ])
        self.stt_model_combo.setCurrentText(self.config["stt"]["model"])
        stt_form.addRow("Whisper Modell:", self.stt_model_combo)
        
        self.stt_thresh_spin = QDoubleSpinBox()
        self.stt_thresh_spin.setRange(0.001, 0.5)
        self.stt_thresh_spin.setDecimals(3)
        self.stt_thresh_spin.setSingleStep(0.005)
        self.stt_thresh_spin.setValue(self.config["stt"]["silence_threshold"])
        stt_form.addRow("Silence Threshold:", self.stt_thresh_spin)
        
        self.stt_duration_spin = QSpinBox()
        self.stt_duration_spin.setRange(1, 10)
        self.stt_duration_spin.setValue(self.config["stt"]["chunk_duration"])
        stt_form.addRow("Chunk Duration (sek):", self.stt_duration_spin)
        
        self.vol_meter_cb = QCheckBox("Volume-Meter im Terminal anzeigen")
        self.vol_meter_cb.setChecked(self.config.get("stt", {}).get("show_volume_meter", False))
        stt_form.addRow("", self.vol_meter_cb)
        
        stt_group.setLayout(stt_form)
        layout.addWidget(stt_group)
        
        tts_group = QGroupBox("Sprachausgabe (TTS)")
        tts_form = QFormLayout()
        
        self.tts_voice_edit = QLineEdit(self.config["tts"]["voice"])
        tts_form.addRow(f"{platform.system()} Stimme:", self.tts_voice_edit)

        voices = self.tts_backend.list_voices()
        voice_examples = ", ".join(voices[:6]) if voices else "Systemstandard"
        hint = QLabel(
            f"TTS-Backend: {self.tts_backend.name}\n"
            f"Verfügbare Stimmen: {voice_examples}"
        )
        hint.setStyleSheet("color: #666; font-size: 11px;")
        hint.setWordWrap(True)
        tts_form.addRow("", hint)
        
        tts_group.setLayout(tts_form)
        layout.addWidget(tts_group)
        layout.addStretch()
        return widget

    # --- TAB: Soul ---
    def _create_soul_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info = QLabel("Die Soul-Datei definiert die Persönlichkeit und Verhaltensregeln der Agentin.")
        info.setStyleSheet("color: #888; font-size: 12px; margin-bottom: 6px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        self.soul_edit = QTextEdit()
        self.soul_edit.setPlainText(self.load_text_file(self.soul_path))
        self.soul_edit.setMinimumHeight(350)
        layout.addWidget(self.soul_edit)
        return widget

    # --- TAB: User ---
    def _create_user_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info = QLabel("Die User-Datei beschreibt den Nutzer und das Zielpublikum (z.B. Studenten, Fachbereich).")
        info.setStyleSheet("color: #888; font-size: 12px; margin-bottom: 6px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        self.user_edit = QTextEdit()
        self.user_edit.setPlainText(self.load_text_file(self.user_path))
        self.user_edit.setMinimumHeight(350)
        layout.addWidget(self.user_edit)
        return widget


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Icon setzen
    icon_path = os.path.join(CORE_DIR, "icon.png")
    if os.path.exists(icon_path):
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(icon_path))
        
    config_path = os.path.join(CORE_DIR, "config.json")
    window = SettingsWindow(config_path)
    window.show()
    sys.exit(app.exec())
