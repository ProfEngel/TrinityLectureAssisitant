import sys
import os
import platform
import shlex
import shutil
import subprocess
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QCheckBox, QComboBox, QGroupBox, QFormLayout,
                             QTextEdit, QTabWidget, QDoubleSpinBox, QSpinBox,
                             QScrollArea, QFrame, QMessageBox, QRadioButton,
                             QButtonGroup, QSizePolicy, QTableWidget,
                             QTableWidgetItem, QHeaderView)

from platform_adapters import (
    create_tts_backend,
    find_codex_executable,
    find_opencode_executable,
    find_pi_executable,
)
from agent_catalog import (
    QUALITY_STATUSES,
    build_agent_catalog,
    default_harnesses_for_agent,
    normalize_catalog_overrides,
)
from brainvault_agents import (
    brainvault_root_from_config,
    build_catalog as build_brainvault_catalog,
    ensure_brainvault_layout,
)
from configuration import DEFAULT_CONFIG, load_config, save_config
from memory_store import MemoryStore, render_graph_html
from trinity_paths import default_runtime_root, default_vault_root
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

        # Optional Eve Voice Runtime. Legacy remains available at all times.
        voice = self.config.setdefault("voice", {})
        voice["engine"] = self.voice_engine_combo.currentData()
        voice["profile"] = self._selected_voice_profile_id()
        voice["fallback_to_legacy"] = self.voice_fallback_cb.isChecked()
        voice["reference_audio"] = self.voice_reference_edit.text().strip()
        voice["access_token"] = self.voice_token_edit.text().strip()
        voice["streaming_chunk_size"] = self.voice_chunk_size_spin.value()
        voice["audio_prebuffer_ms"] = self.voice_prebuffer_spin.value()
        selected_profile = voice.setdefault("profiles", {}).setdefault(
            voice["profile"], {}
        )
        selected_profile["bind_host"] = self.voice_bind_host_edit.text().strip() or "127.0.0.1"
        selected_profile["public_port"] = self.voice_public_port_spin.value()
        
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
            self.config["opencode"]["server_url"] = (
                self.opencode_server_url_edit.text().strip()
                if hasattr(self, "opencode_server_url_edit")
                else "http://127.0.0.1:4096"
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

        # Pi
        if "pi" not in self.config:
            self.config["pi"] = {}
        if hasattr(self, "pi_cb"):
            projects = {}
            for line in self.pi_projects_edit.toPlainText().splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                alias, path = stripped.split("=", 1)
                alias = alias.strip()
                path = path.strip()
                if alias and path:
                    projects[alias] = path

            self.config["pi"]["enabled"] = self.pi_cb.isChecked()
            self.config["pi"]["executable"] = (
                self.pi_executable_edit.text().strip() or "pi"
            )
            self.config["pi"]["projects"] = projects
            self.config["pi"]["default_project"] = (
                self.pi_default_project_edit.text().strip()
            )
            arguments = self.pi_arguments_edit.text().strip()
            try:
                self.config["pi"]["arguments"] = shlex.split(arguments) if arguments else []
            except ValueError:
                self.config["pi"]["arguments"] = arguments.split() if arguments else []
            self.config["pi"]["timeout_seconds"] = self.pi_timeout_spin.value()
            self.config["pi"]["max_output_chars"] = self.pi_output_spin.value()

        # Harness routing: roles and per-agent execution matrix
        if hasattr(self, "harness_role_checks"):
            routing = self.config.setdefault("harness_routing", {})
            frameworks = routing.setdefault("frameworks", {})
            for harness_id, label in self._all_harness_labels().items():
                framework = frameworks.setdefault(harness_id, {})
                framework["label"] = label
                if hasattr(self, "harness_active_checks"):
                    framework["active"] = self.harness_active_checks[harness_id].isChecked()
                roles = {
                    role: checkbox.isChecked()
                    for (current_harness, role), checkbox in self.harness_role_checks.items()
                    if current_harness == harness_id
                }
                if roles:
                    framework["roles"] = roles
            assignments = dict(routing.get("agent_assignments", {}))
            if hasattr(self, "harness_agent_table"):
                harness_ids = self._harness_ids()
                for row, agent_id in enumerate(getattr(self, "harness_agent_ids", [])):
                    selected = []
                    for col, harness_id in enumerate(harness_ids, start=1):
                        item = self.harness_agent_table.item(row, col)
                        if item and item.checkState() == Qt.Checked:
                            selected.append(harness_id)
                    preserved = [
                        harness_id
                        for harness_id in assignments.get(agent_id, [])
                        if harness_id not in harness_ids
                    ]
                    assignments[agent_id] = [*preserved, *selected]
            routing["agent_assignments"] = assignments

        # Agent catalog metadata: maturity. Rights stay in agent.yaml/config and
        # are deliberately not exposed in the simplified settings tables.
        if hasattr(self, "agent_catalog_tables"):
            self.config.setdefault("agent_catalog", {})["agents"] = (
                self._collect_agent_catalog_overrides()
            )

        # Control Plane / MainHub
        if "control_plane" not in self.config:
            self.config["control_plane"] = {}
        if hasattr(self, "control_plane_cb"):
            self.config["control_plane"]["enabled"] = self.control_plane_cb.isChecked()
            self.config["control_plane"]["runtime_root"] = (
                self.runtime_root_edit.text().strip()
            )
            content_vault = self.vault_root_edit.text().strip()
            agents_root = self.external_agents_root_edit.text().strip()
            self.config["control_plane"]["vault_root"] = content_vault
            self.config["control_plane"]["brainvault_root"] = agents_root
            self.config["control_plane"]["external_agents_root"] = agents_root
            self.config["control_plane"]["default_brainvault_harness"] = (
                self.brainvault_harness_combo.currentText()
            )
            self._sync_cloud_agent_pool_projects()

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
            self.config["proactive"]["session_summary_auto_rag_indexing"] = self.auto_rag_cb.isChecked()
        
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

            QTableWidget {{
                background: {colors["field_bg"]};
                alternate-background-color: {colors["raised_bg"]};
                color: {colors["text"]};
                border: 1px solid {colors["border"]};
                border-radius: 8px;
                gridline-color: {colors["border"]};
                selection-background-color: {colors["selection"]};
            }}

            QHeaderView::section {{
                background: {colors["raised_bg"]};
                color: {colors["text"]};
                border: 1px solid {colors["border"]};
                padding: 6px;
                font-weight: 600;
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
        self.settings_mic_button = QPushButton()
        self.settings_mic_button.setToolTip(
            "Desktop-Zuhören sofort pausieren oder wieder aktivieren"
        )
        self.settings_mic_button.clicked.connect(self._toggle_settings_microphone)
        header_row.addWidget(self.settings_mic_button)
        self.settings_tts_button = QPushButton()
        self.settings_tts_button.setToolTip(
            "Desktop-Sprachausgabe sofort pausieren oder wieder aktivieren"
        )
        self.settings_tts_button.clicked.connect(self._toggle_settings_tts)
        header_row.addWidget(self.settings_tts_button)
        if self.embedded:
            header_back = QPushButton("Zurück zum Chat")
            header_back.clicked.connect(self._return_to_chat)
            header_row.addWidget(header_back)
        main_layout.addLayout(header_row)
        self._sync_settings_runtime_buttons()
        
        # Tabs
        tabs = QTabWidget()
        tabs.setUsesScrollButtons(True)
        tabs.setElideMode(Qt.ElideRight)
        tabs.addTab(self._create_persona_tab(), "🤖 Persona")
        tabs.addTab(self._create_llm_tab(), "🧠 LLM")
        tabs.addTab(self._create_api_tab(), "🔑 APIs & Bild")
        tabs.addTab(self._scrollable_tab(self._create_stt_tts_tab()), "🎙️ Sprache")
        tabs.addTab(self._create_audio_tab(), "🔊 Audio-Routing")
        tabs.addTab(self._create_proactive_tab(), "🚀 Proaktiv")
        tabs.addTab(self._create_memory_tab(), "🧠 Memory")
        tabs.addTab(self._scrollable_tab(self._create_harnesses_tab()), "🧭 Harnesses")
        tabs.addTab(self._scrollable_tab(self._create_mainhub_tab()), "🗂 MainHub")
        tabs.addTab(self._scrollable_tab(self._create_agent_ecosystem_tab()), "🧰 Agenten")
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

    def _settings_runtime_values(self):
        system = self.config.setdefault("system", {})
        return {
            "microphone_enabled": bool(system.get("microphone_enabled", True)),
            "tts_enabled": bool(system.get("tts_enabled", True)),
        }

    def _sync_settings_runtime_buttons(self):
        if not hasattr(self, "settings_mic_button"):
            return
        values = self._settings_runtime_values()
        microphone_enabled = values["microphone_enabled"]
        tts_enabled = values["tts_enabled"]
        self.settings_mic_button.setText(
            "🎙 Hört zu" if microphone_enabled else "🔇 Hört nicht zu"
        )
        self.settings_tts_button.setText(
            "🔊 Spricht" if tts_enabled else "🔈 Spricht nicht"
        )

    def _save_runtime_toggle(self, updates):
        system = self.config.setdefault("system", {})
        system.update(updates)
        save_config(self.config_path, self.config)
        self._sync_settings_runtime_buttons()

    def _toggle_settings_microphone(self):
        values = self._settings_runtime_values()
        self._save_runtime_toggle(
            {"microphone_enabled": not values["microphone_enabled"]}
        )

    def _toggle_settings_tts(self):
        values = self._settings_runtime_values()
        self._save_runtime_toggle({"tts_enabled": not values["tts_enabled"]})

    def _create_memory_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        description = QLabel(
            "Memory, Graph und Deep-Memory-Diagnose liegen hier in den "
            "Einstellungen. Die taegliche Arbeitsansicht bleibt dadurch schlank."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        header = QHBoxLayout()
        self.memory_status_label = QLabel("Memory wird geladen ...")
        self.memory_status_label.setObjectName("settingsSection")
        bake_button = QPushButton("Memory backen")
        bake_button.clicked.connect(self._bake_memory_from_settings)
        refresh_button = QPushButton("Graph aktualisieren")
        refresh_button.clicked.connect(self._refresh_memory_from_settings)
        header.addWidget(self.memory_status_label, 1)
        header.addWidget(bake_button)
        header.addWidget(refresh_button)
        layout.addLayout(header)

        self.settings_memory_graph = QWebEngineView()
        settings = self.settings_memory_graph.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        layout.addWidget(self.settings_memory_graph, 1)

        self._refresh_memory_from_settings()
        return widget

    def _memory_store_for_settings(self):
        home = os.path.dirname(CORE_DIR)
        memory_dir = os.path.join(home, "memory")
        return MemoryStore(os.path.join(memory_dir, "trinity_memory.sqlite3"))

    def _memory_theme(self):
        return self.config.get("system", {}).get("classic_theme", "dark")

    def _refresh_memory_from_settings(self):
        if not hasattr(self, "settings_memory_graph"):
            return
        store = self._memory_store_for_settings()
        status = store.status()
        self.memory_status_label.setText(
            f"{status['memories']} Memories · {status['links']} Links · "
            f"{status['unbaked']} unbaked"
        )
        self.settings_memory_graph.setHtml(
            render_graph_html(store.graph_data(), self._memory_theme())
        )

    def _bake_memory_from_settings(self):
        home = os.path.dirname(CORE_DIR)
        chat_history = os.path.join(home, "memory", "classic_chat_history.jsonl")
        try:
            result = self._memory_store_for_settings().bake_chat_history(chat_history)
            self.memory_status_label.setText(
                f"Memory gebacken: {result['imported']} importiert, "
                f"{result['baked']} verdichtet"
            )
            self._refresh_memory_from_settings()
        except (OSError, ValueError) as exc:
            self.memory_status_label.setText(f"Memory Bake fehlgeschlagen: {exc}")

    def _create_agent_ecosystem_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        description = QLabel(
            "Trinity trennt interne Trinity-Agenten von externen Agenten im "
            "lokalen Werkzeugkasten. Der Werkzeugkasten wird aus der lokal "
            "konfigurierten Ablage .agents gelesen."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.agent_ecosystem_summary = QLabel()
        self.agent_ecosystem_summary.setWordWrap(True)
        layout.addWidget(self.agent_ecosystem_summary)

        self.agent_catalog_tables = []
        self.local_agent_table = self._create_agent_summary_table()
        self.cloud_agent_table = self._create_agent_summary_table()
        self.agent_catalog_tables.extend([self.local_agent_table, self.cloud_agent_table])

        local_group = QGroupBox("Lokale Trinity-Agenten")
        local_layout = QVBoxLayout(local_group)
        local_layout.addWidget(self.local_agent_table)
        layout.addWidget(local_group)

        cloud_group = QGroupBox("Lokaler Agenten-Werkzeugkasten")
        cloud_layout = QVBoxLayout(cloud_group)
        cloud_layout.addWidget(self.cloud_agent_table)
        layout.addWidget(cloud_group, 1)

        reload_button = QPushButton("Agentenkiste auf Datenträger prüfen")
        reload_button.clicked.connect(self._refresh_agent_ecosystem)
        layout.addWidget(reload_button)

        hint = QLabel(
            "Details wie Rechte, Ursprungspfade und Skripte stehen in der jeweiligen "
            "agent.yaml. Diese Ansicht bleibt bewusst knapp."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8fa3b8; font-size: 11px;")
        layout.addWidget(hint)
        layout.addStretch()
        self._refresh_agent_ecosystem()
        return widget

    def _refresh_agent_ecosystem(self):
        home = os.path.dirname(CORE_DIR)
        records = build_agent_catalog(home, self.config)
        local_records = [
            record for record in records
            if record.tier != "brainvault"
        ]
        cloud_records = [
            record for record in records
            if record.tier == "brainvault"
        ]
        self.agent_ecosystem_summary.setText(
            "Agenten gesamt: {total} | Trinity-intern: {local} | Werkzeugkasten: {cloud}".format(
                total=len(records),
                local=len(local_records),
                cloud=len(cloud_records),
            )
        )
        self._populate_agent_summary_table(self.local_agent_table, local_records)
        self._populate_agent_summary_table(self.cloud_agent_table, cloud_records)

    def _create_agent_summary_table(self):
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Agent", "Status", "Reifegrad", "Harness", "Hinweis"])
        table.verticalHeader().setVisible(False)
        table.setMinimumHeight(220)
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, 5):
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        return table

    def _populate_agent_summary_table(self, table, records):
        table.setRowCount(len(records))
        table.agent_ids = []
        for row, record in enumerate(records):
            table.agent_ids.append(record.agent_id)
            self._set_readonly_cell(
                table,
                row,
                0,
                f"{record.name}\n{record.agent_id}",
                record.description or record.path,
            )
            self._set_readonly_cell(table, row, 1, record.runtime_status)

            quality_combo = QComboBox()
            for status in QUALITY_STATUSES:
                quality_combo.addItem(self._quality_label(status), status)
            current_index = quality_combo.findData(record.quality_status)
            quality_combo.setCurrentIndex(max(0, current_index))
            table.setCellWidget(row, 2, quality_combo)

            harness = record.preferred_harness or "trinity"
            if record.tier == "brainvault" and harness == "auto":
                harness = self._default_brainvault_harness()
            self._set_readonly_cell(table, row, 3, harness)

            notes = []
            if record.synthetic:
                notes.append("verwaltet")
            if record.legacy:
                notes.append("Legacy")
            if record.parent_agent:
                notes.append(f"Parent: {record.parent_agent}")
            if not record.valid:
                notes.append("ungueltig")
            notes.extend(record.errors)
            self._set_readonly_cell(table, row, 4, "; ".join(notes) or "OK")
        table.resizeRowsToContents()

    def _collect_agent_catalog_overrides(self):
        existing = (
            self.config.get("agent_catalog", {})
            .get("agents", {})
            if isinstance(self.config.get("agent_catalog", {}).get("agents", {}), dict)
            else {}
        )
        agents = {}
        for table in getattr(self, "agent_catalog_tables", []):
            for row, agent_id in enumerate(getattr(table, "agent_ids", [])):
                quality_combo = table.cellWidget(row, 2)
                quality_status = (
                    quality_combo.currentData()
                    if isinstance(quality_combo, QComboBox)
                    else existing.get(agent_id, {}).get("quality_status", "unverified")
                )
                previous = existing.get(agent_id, {})
                agents[agent_id] = {
                    "quality_status": quality_status,
                    "allowed_tools": previous.get("allowed_tools", []),
                    "allowed_paths": previous.get("allowed_paths", []),
                    "requires_approval": previous.get("requires_approval", []),
                    "max_attempts": previous.get("max_attempts", 2),
                    "parallel_runs": previous.get("parallel_runs", 1),
                }
        return normalize_catalog_overrides(agents)

    @staticmethod
    def _quality_label(status):
        labels = {
            "unverified": "Nicht erprobt",
            "testing": "Im Test",
            "validated": "Erprobt",
            "stable": "Stabil",
            "deprecated": "Veraltet",
        }
        return labels.get(status, status)

    @staticmethod
    def _list_to_csv(values):
        if not values:
            return ""
        return ", ".join(str(item).strip() for item in values if str(item).strip())

    @staticmethod
    def _csv_to_list(value):
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value or "").split(",") if item.strip()]

    @staticmethod
    def _table_text(table, row, column):
        item = table.item(row, column)
        return item.text().strip() if item else ""

    @staticmethod
    def _table_int(table, row, column, default):
        try:
            return int(SettingsWindow._table_text(table, row, column))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _set_readonly_cell(table, row, column, text, tooltip=""):
        item = QTableWidgetItem(str(text or ""))
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        if tooltip:
            item.setToolTip(str(tooltip))
        table.setItem(row, column, item)

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
        self.auto_rag_cb.setChecked(proactive_conf.get(
            "session_summary_auto_rag_indexing",
            proactive_conf.get("auto_rag_indexing", True),
        ))
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

    # --- TAB: Harnesses ---
    def _create_harnesses_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        description = QLabel(
            "Aktiviere nur die Harnesses, die Trinity verwenden darf. Deaktivierte "
            "Harnesses erscheinen nicht in der Detailansicht, Agentenmatrix oder "
            "Standardauswahl und werden auch nicht ausgefuehrt."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.harness_active_checks = {}
        self.harness_role_checks = {}
        self.harness_agent_ids = []

        layout.addWidget(self._create_harness_activation_group())
        if self._is_harness_active("trinity"):
            layout.addWidget(self._create_trinity_harness_group())
        if self._is_harness_active("codex"):
            layout.addWidget(self._create_codex_harness_group())
        if self._is_harness_active("pi"):
            layout.addWidget(self._create_pi_harness_group())
        if self._is_harness_active("opencode"):
            layout.addWidget(self._create_opencode_harness_group())
        layout.addWidget(self._create_harness_agent_matrix_group(), 1)
        return widget

    def _harness_ids(self):
        return [
            harness_id
            for harness_id in self._all_harness_labels()
            if self._is_harness_active(harness_id)
        ]

    @staticmethod
    def _all_harness_labels():
        return {
            "trinity": "Trinity",
            "codex": "Codex",
            "pi": "Pi",
            "opencode": "OpenCode",
        }

    def _harness_labels(self):
        return {
            harness_id: label
            for harness_id, label in self._all_harness_labels().items()
            if self._is_harness_active(harness_id)
        }

    def _is_harness_active(self, harness_id):
        if harness_id == "trinity":
            return True
        framework = (
            self.config.get("harness_routing", {})
            .get("frameworks", {})
            .get(harness_id, {})
        )
        if "active" in framework:
            return bool(framework["active"])
        return bool(self.config.get(harness_id, {}).get("enabled", False))

    def _create_harness_activation_group(self):
        group = QGroupBox("Aktive Harnesses")
        layout = QVBoxLayout(group)
        hint = QLabel(
            "Nach dem Speichern wird die Ansicht mit den aktivierten Harnesses "
            "neu aufgebaut. Trinity bleibt immer aktiv."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8fa3b8; font-size: 11px;")
        layout.addWidget(hint)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        for harness_id, label in self._all_harness_labels().items():
            checkbox = QCheckBox(label)
            checkbox.setChecked(self._is_harness_active(harness_id))
            if harness_id == "trinity":
                checkbox.setEnabled(False)
            self.harness_active_checks[harness_id] = checkbox
            row_layout.addWidget(checkbox)
        row_layout.addStretch()
        layout.addWidget(row)
        return group

    @staticmethod
    def _role_labels():
        return {
            "agent_builder": "Agentenbuilder",
            "complex_cases": "Harte komplexe Faelle",
            "agent_execution": "Ausfuehrung der Agenten",
        }

    @staticmethod
    def _set_status_label_style(label, ok=True):
        label.setMinimumHeight(28)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if ok:
            label.setStyleSheet(
                "color: #bbf7d0; background: rgba(22, 101, 52, 0.38); "
                "border: 1px solid rgba(34, 197, 94, 0.65); "
                "border-radius: 7px; padding: 4px 8px; font-size: 11px; "
                "font-weight: 600;"
            )
        else:
            label.setStyleSheet(
                "color: #fef3c7; background: rgba(217, 119, 6, 0.18); "
                "border: 1px solid rgba(251, 191, 36, 0.45); "
                "border-radius: 7px; padding: 4px 8px; font-size: 11px; "
                "font-weight: 600;"
            )

    @staticmethod
    def _tidy_form(form):
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)

    def _role_enabled(self, harness_id, role):
        routing = self.config.get("harness_routing", {})
        frameworks = routing.get("frameworks", {})
        roles = frameworks.get(harness_id, {}).get("roles", {})
        return bool(roles.get(role, False))

    def _add_harness_roles(self, form, harness_id):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        for role, label in self._role_labels().items():
            checkbox = QCheckBox(label)
            checkbox.setChecked(self._role_enabled(harness_id, role))
            self.harness_role_checks[(harness_id, role)] = checkbox
            row_layout.addWidget(checkbox)
        row_layout.addStretch()
        form.addRow("Rollen:", row)

    def _create_trinity_harness_group(self):
        group = QGroupBox("Trinity")
        form = QFormLayout()
        self._tidy_form(form)
        status = QLabel("Aktiv: Control Plane, Routing, Memory, Payloads und UI.")
        self._set_status_label_style(status, True)
        form.addRow("Status:", status)
        self._add_harness_roles(form, "trinity")
        hint = QLabel(
            "Trinity bleibt die Control Plane. Externe Harnesses wie Codex, Pi "
            "oder OpenCode werden nur fuer passende Agenten und Rollen zugeschaltet."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8fa3b8; font-size: 11px;")
        form.addRow("", hint)
        group.setLayout(form)
        return group

    def _create_codex_harness_group(self):
        group = QGroupBox("Codex")
        form = QFormLayout()
        self._tidy_form(form)
        codex_conf = self.config.get("codex", {})

        top_row = QWidget()
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        self.codex_cb = QCheckBox("Codex-Auftraege erlauben")
        self.codex_cb.setChecked(codex_conf.get("enabled", False))
        top_layout.addWidget(self.codex_cb)
        test_btn = QPushButton("Anbindung testen")
        test_btn.clicked.connect(lambda: self._test_harness_connection("codex"))
        top_layout.addWidget(test_btn)
        top_layout.addStretch()
        form.addRow(top_row)

        detected = find_codex_executable()
        status = QLabel("Gefunden" if detected else "Nicht gefunden")
        if detected:
            status.setToolTip(str(detected))
        self._set_status_label_style(status, bool(detected))
        form.addRow("Status:", status)
        self._add_harness_roles(form, "codex")

        self.codex_executable_edit = QLineEdit(codex_conf.get("executable", "codex"))
        form.addRow("Programm:", self.codex_executable_edit)

        self.codex_projects_edit = QTextEdit()
        self.codex_projects_edit.setPlainText(self._projects_to_text(codex_conf.get("projects", {})))
        self.codex_projects_edit.setPlaceholderText(
            "Automatismen = /vollstaendiger/Pfad/zum/Projekt\n"
            "Lehre = C:\\Users\\Name\\Projekte\\Lehre"
        )
        self.codex_projects_edit.setMinimumHeight(150)
        form.addRow("Freigegebene Projekte:", self.codex_projects_edit)

        self.codex_default_project_edit = QLineEdit(codex_conf.get("default_project", ""))
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
        self.codex_timeout_spin.setValue(int(codex_conf.get("timeout_seconds", 900)))
        form.addRow("Zeitlimit:", self.codex_timeout_spin)

        self.codex_output_spin = QSpinBox()
        self.codex_output_spin.setRange(500, 12000)
        self.codex_output_spin.setSingleStep(500)
        self.codex_output_spin.setSuffix(" Zeichen")
        self.codex_output_spin.setValue(int(codex_conf.get("max_output_chars", 3200)))
        form.addRow("Antwortlaenge:", self.codex_output_spin)

        self.codex_ephemeral_cb = QCheckBox("Keine dauerhaften Codex-Sitzungen")
        self.codex_ephemeral_cb.setChecked(codex_conf.get("ephemeral", True))
        form.addRow(self.codex_ephemeral_cb)

        self.codex_network_cb = QCheckBox("Netzwerkzugriff fuer Codex erlauben")
        self.codex_network_cb.setChecked(codex_conf.get("network_access", False))
        form.addRow(self.codex_network_cb)

        group.setLayout(form)
        return group

    def _create_pi_harness_group(self):
        group = QGroupBox("Pi")
        form = QFormLayout()
        self._tidy_form(form)
        pi_conf = self.config.get("pi", {})

        top_row = QWidget()
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        self.pi_cb = QCheckBox("Pi-Auftraege erlauben")
        self.pi_cb.setChecked(pi_conf.get("enabled", False))
        top_layout.addWidget(self.pi_cb)
        test_btn = QPushButton("Anbindung testen")
        test_btn.clicked.connect(lambda: self._test_harness_connection("pi"))
        top_layout.addWidget(test_btn)
        top_layout.addStretch()
        form.addRow(top_row)

        detected = find_pi_executable()
        status = QLabel("Gefunden" if detected else "Nicht gefunden")
        if detected:
            status.setToolTip(str(detected))
        self._set_status_label_style(status, bool(detected))
        form.addRow("Status:", status)
        self._add_harness_roles(form, "pi")

        self.pi_executable_edit = QLineEdit(pi_conf.get("executable", "pi"))
        form.addRow("Programm oder Wrapper:", self.pi_executable_edit)

        self.pi_projects_edit = QTextEdit()
        self.pi_projects_edit.setPlainText(self._projects_to_text(pi_conf.get("projects", {})))
        self.pi_projects_edit.setPlaceholderText(
            "SandboxVault = /vollstaendiger/Pfad/zur/Sandbox\n"
            "TrinityVault = /vollstaendiger/Pfad/zum/Vault"
        )
        self.pi_projects_edit.setMinimumHeight(150)
        form.addRow("Freigegebene Projekte:", self.pi_projects_edit)

        self.pi_default_project_edit = QLineEdit(pi_conf.get("default_project", ""))
        form.addRow("Standardprojekt:", self.pi_default_project_edit)

        raw_arguments = pi_conf.get("arguments", [])
        if isinstance(raw_arguments, list):
            arguments_text = " ".join(str(item) for item in raw_arguments)
        else:
            arguments_text = str(raw_arguments or "")
        self.pi_arguments_edit = QLineEdit(arguments_text)
        self.pi_arguments_edit.setPlaceholderText("-p {prompt}")
        form.addRow("Argumente:", self.pi_arguments_edit)

        self.pi_timeout_spin = QSpinBox()
        self.pi_timeout_spin.setRange(30, 3600)
        self.pi_timeout_spin.setSuffix(" Sekunden")
        self.pi_timeout_spin.setValue(int(pi_conf.get("timeout_seconds", 600)))
        form.addRow("Zeitlimit:", self.pi_timeout_spin)

        self.pi_output_spin = QSpinBox()
        self.pi_output_spin.setRange(500, 12000)
        self.pi_output_spin.setSingleStep(500)
        self.pi_output_spin.setSuffix(" Zeichen")
        self.pi_output_spin.setValue(int(pi_conf.get("max_output_chars", 3200)))
        form.addRow("Antwortlaenge:", self.pi_output_spin)

        hint = QLabel(
            "Fuer die Pi-CLI ist meist '-p {prompt}' richtig. Ohne {prompt} "
            "uebergibt Trinity den Auftrag per stdin; das kann bei interaktiven "
            "CLIs haengen."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #d29922; font-size: 11px;")
        form.addRow("", hint)

        group.setLayout(form)
        return group

    def _create_opencode_harness_group(self):
        group = QGroupBox("OpenCode")
        form = QFormLayout()
        self._tidy_form(form)
        opencode_conf = self.config.get("opencode", {})

        top_row = QWidget()
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        self.opencode_cb = QCheckBox("OpenCode-Auftraege erlauben")
        self.opencode_cb.setChecked(opencode_conf.get("enabled", False))
        top_layout.addWidget(self.opencode_cb)
        test_btn = QPushButton("Anbindung testen")
        test_btn.clicked.connect(lambda: self._test_harness_connection("opencode"))
        top_layout.addWidget(test_btn)
        top_layout.addStretch()
        form.addRow(top_row)

        detected = find_opencode_executable()
        status = QLabel("Gefunden" if detected else "Nicht gefunden")
        if detected:
            status.setToolTip(str(detected))
        self._set_status_label_style(status, bool(detected))
        form.addRow("Status:", status)
        self._add_harness_roles(form, "opencode")

        self.opencode_executable_edit = QLineEdit(opencode_conf.get("executable", "opencode"))
        form.addRow("Programm:", self.opencode_executable_edit)

        self.opencode_server_url_edit = QLineEdit(
            opencode_conf.get("server_url", "http://127.0.0.1:4096")
        )
        form.addRow("Laufender OpenCode-Dienst:", self.opencode_server_url_edit)

        self.opencode_projects_edit = QTextEdit()
        self.opencode_projects_edit.setPlainText(self._projects_to_text(opencode_conf.get("projects", {})))
        self.opencode_projects_edit.setPlaceholderText(
            "Automatismen = /vollstaendiger/Pfad/zum/Projekt\n"
            "Mail = C:\\Users\\Name\\Projekte\\MailAutomationen"
        )
        self.opencode_projects_edit.setMinimumHeight(150)
        form.addRow("Freigegebene Projekte:", self.opencode_projects_edit)

        self.opencode_default_project_edit = QLineEdit(opencode_conf.get("default_project", ""))
        form.addRow("Standardprojekt:", self.opencode_default_project_edit)

        self.opencode_agent_edit = QLineEdit(opencode_conf.get("agent", "build"))
        form.addRow("OpenCode-Agent:", self.opencode_agent_edit)

        self.opencode_model_edit = QLineEdit(opencode_conf.get("model", ""))
        form.addRow("Modell:", self.opencode_model_edit)

        self.opencode_timeout_spin = QSpinBox()
        self.opencode_timeout_spin.setRange(30, 7200)
        self.opencode_timeout_spin.setSuffix(" Sekunden")
        self.opencode_timeout_spin.setValue(int(opencode_conf.get("timeout_seconds", 900)))
        form.addRow("Zeitlimit:", self.opencode_timeout_spin)

        self.opencode_output_spin = QSpinBox()
        self.opencode_output_spin.setRange(500, 12000)
        self.opencode_output_spin.setSingleStep(500)
        self.opencode_output_spin.setSuffix(" Zeichen")
        self.opencode_output_spin.setValue(int(opencode_conf.get("max_output_chars", 3200)))
        form.addRow("Antwortlaenge:", self.opencode_output_spin)

        group.setLayout(form)
        return group

    def _create_harness_agent_matrix_group(self):
        group = QGroupBox("Welche Agenten darf welches Framework ausfuehren?")
        group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(group)
        hint = QLabel(
            "Links stehen alle bekannten Trinity-Agenten inklusive Trinity selbst, "
            "Agentenbuilder, Shared/Personal/Staging Skills und Legacy-Agenten. "
            "Pro Zeile wird festgelegt, ob ein aktives Harness diesen "
            "Agenten beziehungsweise diese Agentenfamilie ausfuehren darf."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        harness_ids = self._harness_ids()
        table = QTableWidget(0, len(harness_ids) + 1)
        table.setHorizontalHeaderLabels(["Agent", *[self._harness_labels()[item] for item in harness_ids]])
        table.verticalHeader().setVisible(False)
        table.setMinimumHeight(520)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, len(harness_ids) + 1):
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)

        self._populate_harness_agent_table(table, self._harness_agent_records())
        self.harness_agent_table = table
        layout.addWidget(table, 1)
        return group

    def _populate_harness_agent_table(self, table, records):
        harness_ids = self._harness_ids()
        assignments = self.config.get("harness_routing", {}).get("agent_assignments", {})
        table.setRowCount(len(records))
        self.harness_agent_ids = []
        for row, record in enumerate(records):
            agent_id = record.agent_id
            self.harness_agent_ids.append(agent_id)
            label = f"{record.name} ({agent_id}) · {record.tier}/{record.quality_status}"
            if record.legacy:
                label += " · Legacy"
            if record.synthetic:
                label += " · Managed"
            item = QTableWidgetItem(label)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item.setToolTip(record.description or record.path)
            table.setItem(row, 0, item)
            if agent_id in assignments:
                selected = set(assignments.get(agent_id, []))
            else:
                if getattr(record, "tier", "") == "brainvault":
                    selected = {self._default_brainvault_harness()}
                else:
                    selected = set(default_harnesses_for_agent(agent_id))
            for col, harness_id in enumerate(harness_ids, start=1):
                check_item = QTableWidgetItem()
                check_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                check_item.setCheckState(Qt.Checked if harness_id in selected else Qt.Unchecked)
                table.setItem(row, col, check_item)
        table.resizeRowsToContents()

    def _harness_agent_records(self):
        try:
            return build_agent_catalog(os.path.dirname(CORE_DIR), self.config)
        except Exception as exc:
            print(f"Agentenliste fuer Harness-Matrix konnte nicht geladen werden: {exc}")
            return []

    def _default_brainvault_harness(self):
        value = (
            self.config.get("control_plane", {})
            .get("default_brainvault_harness", "pi")
        )
        if value in self._harness_ids():
            return value
        for harness_id in ("pi", "codex", "opencode", "trinity"):
            if harness_id in self._harness_ids():
                return harness_id
        return "trinity"

    def _apply_default_brainvault_assignments(self, records=None):
        records = records or self._harness_agent_records()
        default_harness = self._default_brainvault_harness()
        assignments = self.config.setdefault("harness_routing", {}).setdefault(
            "agent_assignments", {}
        )
        changed = False
        for record in records:
            if getattr(record, "tier", "") != "brainvault":
                continue
            if record.agent_id not in assignments:
                assignments[record.agent_id] = [default_harness]
                changed = True
        return changed

    def _refresh_brainvault_agents(self):
        try:
            self.config.setdefault("control_plane", {})["brainvault_root"] = (
                self.brainvault_root_edit.text().strip()
            )
            self.config["control_plane"]["external_agents_root"] = (
                self.external_agents_root_edit.text().strip()
            )
            self.config["control_plane"]["default_brainvault_harness"] = (
                self.brainvault_harness_combo.currentText()
            )
            root = brainvault_root_from_config(os.path.dirname(CORE_DIR), self.config)
            ensure_brainvault_layout(root)
            catalog = build_brainvault_catalog(root)
            records = self._harness_agent_records()
            self._apply_default_brainvault_assignments(records)
            if hasattr(self, "harness_agent_table"):
                self._populate_harness_agent_table(self.harness_agent_table, records)
            if hasattr(self, "agent_catalog_tables"):
                self._refresh_agent_ecosystem()
            if hasattr(self, "brainvault_status_label"):
                summary = catalog.get("summary", {})
                self.brainvault_status_label.setText(
                    f"Lokaler Werkzeugkasten gelesen: {root} | Agenten: {summary.get('total', 0)}"
                )
            QMessageBox.information(
                self,
                "Agenten-Werkzeugkasten aktualisiert",
                f"Agentenkatalog neu erzeugt:\n{catalog.get('path')}\n\n"
                "Neue externe Agenten wurden dem Standard-Harness zugewiesen, "
                "falls noch keine manuelle Zuordnung vorhanden war.",
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Agenten-Werkzeugkasten konnte nicht aktualisiert werden",
                str(exc),
            )

    def _sync_cloud_agent_pool_projects(self):
        """Expose only the local .agents directory to active harnesses."""
        root = ""
        if hasattr(self, "external_agents_root_edit"):
            root = self.external_agents_root_edit.text().strip()
        if not root:
            try:
                root = str(brainvault_root_from_config(os.path.dirname(CORE_DIR), self.config))
            except Exception:
                root = ""
        if not root or not os.path.isdir(os.path.expanduser(root)):
            return

        root = os.path.abspath(os.path.expanduser(root))
        agents_dir = root if os.path.basename(root) == ".agents" else os.path.join(root, ".agents")
        if not os.path.isdir(agents_dir):
            return
        for harness_id in ("codex", "pi", "opencode"):
            if not self._is_harness_active(harness_id):
                continue
            harness_conf = self.config.setdefault(harness_id, {})
            projects = harness_conf.setdefault("projects", {})
            if isinstance(projects, dict):
                projects.setdefault("Agenten", agents_dir)

    @staticmethod
    def _projects_to_text(projects):
        if not isinstance(projects, dict):
            return ""
        return "\n".join(f"{alias} = {path}" for alias, path in projects.items())

    @staticmethod
    def _projects_from_text(text):
        projects = {}
        for line in str(text or "").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            alias, path = stripped.split("=", 1)
            alias = alias.strip()
            path = path.strip()
            if alias and path:
                projects[alias] = path
        return projects

    def _test_harness_connection(self, harness_id):
        if harness_id == "trinity":
            QMessageBox.information(
                self,
                "Trinity aktiv",
                "Trinity ist die integrierte Control Plane und muss nicht als "
                "externes Programm getestet werden.",
            )
            return

        executable = self._current_harness_executable(harness_id)
        resolved = self._resolve_harness_executable(harness_id, executable)
        label = self._harness_labels().get(harness_id, harness_id)
        if not resolved:
            QMessageBox.warning(
                self,
                f"{label} nicht gefunden",
                f"{label} wurde nicht gefunden. Bitte Programmpfad pruefen.",
            )
            return

        if harness_id == "pi":
            QMessageBox.information(
                self,
                "Pi gefunden",
                f"Pi-Wrapper gefunden:\n{resolved}\n\n"
                "Da Pi als generischer Wrapper konfiguriert ist, fuehrt Trinity "
                "hier keinen Testauftrag aus.",
            )
            return

        command = [resolved, "--version"]
        use_shell = os.name == "nt" and str(resolved).casefold().endswith((".cmd", ".bat"))
        run_command = subprocess.list2cmdline(command) if use_shell else command
        try:
            completed = subprocess.run(
                run_command,
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
                shell=use_shell,
            )
        except Exception as exc:
            QMessageBox.warning(self, f"{label} Test fehlgeschlagen", str(exc))
            return
        output = (completed.stdout or completed.stderr or "").strip()
        if completed.returncode == 0:
            QMessageBox.information(
                self,
                f"{label} erreichbar",
                f"{label} ist erreichbar:\n{resolved}\n\n{output[:1000]}",
            )
        else:
            QMessageBox.warning(
                self,
                f"{label} Test mit Fehlercode {completed.returncode}",
                f"Gefunden: {resolved}\n\n{output[:1000]}",
            )

    def _current_harness_executable(self, harness_id):
        fields = {
            "trinity": None,
            "codex": getattr(self, "codex_executable_edit", None),
            "pi": getattr(self, "pi_executable_edit", None),
            "opencode": getattr(self, "opencode_executable_edit", None),
        }
        field = fields.get(harness_id)
        if field is not None:
            return field.text().strip()
        return self.config.get(harness_id, {}).get("executable", harness_id)

    @staticmethod
    def _resolve_harness_executable(harness_id, raw_value):
        value = os.path.expandvars(os.path.expanduser(str(raw_value or harness_id).strip()))
        if os.path.dirname(value):
            path = os.path.abspath(value)
            return path if os.path.isfile(path) else ""
        finders = {
            "codex": find_codex_executable,
            "pi": find_pi_executable,
            "opencode": find_opencode_executable,
        }
        if value.casefold() in {harness_id, f"{harness_id}.exe", f"{harness_id}.cmd"}:
            finder = finders.get(harness_id)
            return finder() if finder else ""
        return shutil.which(value) or ""

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
        self._set_status_label_style(status, bool(detected))
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
        self._set_status_label_style(status, bool(detected))
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

    # --- TAB: Pi ---
    def _create_pi_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Lokaler Pi-CLI-Agent")
        form = QFormLayout()
        pi_conf = self.config.get("pi", {})

        self.pi_cb = QCheckBox(
            "Pi-Aufträge per Sprache, Chat, Telegram und Companion erlauben"
        )
        self.pi_cb.setChecked(pi_conf.get("enabled", False))
        form.addRow(self.pi_cb)

        detected = find_pi_executable()
        status_text = (
            f"Pi gefunden: {detected}"
            if detected
            else "Pi wurde im Systempfad noch nicht gefunden."
        )
        status = QLabel(status_text)
        status.setWordWrap(True)
        self._set_status_label_style(status, bool(detected))
        form.addRow("Status:", status)

        self.pi_executable_edit = QLineEdit(pi_conf.get("executable", "pi"))
        self.pi_executable_edit.setPlaceholderText(
            "pi oder vollständiger Pfad zu Deinem Pi-Wrapper"
        )
        form.addRow("Programm:", self.pi_executable_edit)

        raw_arguments = pi_conf.get("arguments", [])
        if isinstance(raw_arguments, list):
            arguments_text = " ".join(str(item) for item in raw_arguments)
        else:
            arguments_text = str(raw_arguments or "")
        self.pi_arguments_edit = QLineEdit(arguments_text)
        self.pi_arguments_edit.setPlaceholderText(
            "optional, z.B. chat --stdin oder ask {prompt}"
        )
        form.addRow("Argumente:", self.pi_arguments_edit)

        self.pi_timeout_spin = QSpinBox()
        self.pi_timeout_spin.setRange(30, 3600)
        self.pi_timeout_spin.setSuffix(" Sekunden")
        self.pi_timeout_spin.setValue(int(pi_conf.get("timeout_seconds", 600)))
        form.addRow("Zeitlimit:", self.pi_timeout_spin)

        self.pi_output_spin = QSpinBox()
        self.pi_output_spin.setRange(500, 12000)
        self.pi_output_spin.setSingleStep(500)
        self.pi_output_spin.setSuffix(" Zeichen")
        self.pi_output_spin.setValue(int(pi_conf.get("max_output_chars", 3200)))
        form.addRow("Antwortlänge:", self.pi_output_spin)

        hint = QLabel(
            "Trinity startet Pi nur auf ausdrückliche Formulierungen wie "
            "„nutze Pi“ oder „frage Pi“. Ohne {prompt} wird der Auftrag per stdin "
            "an den Wrapper übergeben."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #d29922; font-size: 11px;")
        form.addRow("", hint)

        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()
        return widget

    # --- TAB: MainHub ---
    def _create_mainhub_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Trinity: lokale Laufzeit, Inhalte und Agenten")
        form = QFormLayout()
        self._tidy_form(form)
        control_conf = self.config.get("control_plane", {})

        self.control_plane_cb = QCheckBox("Control Plane aktiv")
        self.control_plane_cb.setChecked(control_conf.get("enabled", True))

        runtime_default = control_conf.get("runtime_root") or str(
            default_runtime_root(home=os.path.dirname(CORE_DIR))
        )
        self.runtime_root_edit = QLineEdit(runtime_default)
        self.runtime_root_edit.setPlaceholderText(
            "/lokaler/Pfad/TrinityRuntime"
        )
        form.addRow("Lokale Runtime:", self.runtime_root_edit)

        content_vault_default = control_conf.get("vault_root") or str(
            default_vault_root()
        )
        self.vault_root_edit = QLineEdit(content_vault_default)
        self.vault_root_edit.setPlaceholderText(
            "/Cloud/Pfad/BrainVault"
        )
        form.addRow("Cloud-Vault für Inhalte:", self.vault_root_edit)

        try:
            agents_default = str(
                brainvault_root_from_config(os.path.dirname(CORE_DIR), self.config)
            )
        except Exception:
            agents_default = (
                control_conf.get("external_agents_root")
                or control_conf.get("brainvault_root")
                or str(Path.home())
            )
        self.external_agents_root_edit = QLineEdit(agents_default)
        self.external_agents_root_edit.setPlaceholderText(
            "/lokale/Wurzel/mit/.agents"
        )
        form.addRow("Lokal installierte Agenten:", self.external_agents_root_edit)
        self.brainvault_root_edit = self.external_agents_root_edit

        self.brainvault_harness_combo = QComboBox()
        self.brainvault_harness_combo.addItems(self._harness_ids())
        default_harness = control_conf.get("default_brainvault_harness", "pi")
        if default_harness in self._harness_ids():
            self.brainvault_harness_combo.setCurrentText(default_harness)
        else:
            self.brainvault_harness_combo.setCurrentText("pi")
        form.addRow("Standard-Extern-Harness:", self.brainvault_harness_combo)

        refresh_row = QWidget()
        refresh_layout = QHBoxLayout(refresh_row)
        refresh_layout.setContentsMargins(0, 0, 0, 0)
        refresh_btn = QPushButton("Agenten-Werkzeugkasten aktualisieren")
        refresh_btn.clicked.connect(self._refresh_brainvault_agents)
        refresh_layout.addWidget(refresh_btn)
        self.brainvault_status_label = QLabel("")
        self.brainvault_status_label.setWordWrap(True)
        self.brainvault_status_label.setStyleSheet("color: #8fa3b8; font-size: 11px;")
        refresh_layout.addWidget(self.brainvault_status_label, 1)
        form.addRow("", refresh_row)

        hint = QLabel(
            "Die Runtime bleibt lokal und enthaelt Jobs, Queue, Cache, Temp und Secrets.\n\n"
            "Der lokale Agenten-Werkzeugkasten enthaelt ausfuehrbare externe Agenten. "
            "Dort muessen `.agents` und `AGENTS.md` liegen. Der Cloud-Vault ist "
            "davon getrennt und enthaelt Projekte, Dokumente und Wissen."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #d29922; font-size: 11px;")
        form.addRow("", hint)

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
            "Bilder werden standardmäßig lokal erzeugt: 'Erstelle ein Bild …'.\n"
            "Nur 'externes Bild' oder 'über fal.ai' nutzt die externe API."
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
    VOICE_PROFILE_OPTIONS = (
        (
            "Automatisch passend zu diesem Computer (empfohlen)",
            "eve-trinity",
            "Trinity wählt die passende lokale Eve-Laufzeit für dieses Betriebssystem. "
            "Das ist die beste Wahl, wenn Du Eve direkt an diesem Computer verwendest.",
        ),
        (
            "Dieser Mac: Mikrofon und Lautsprecher lokal",
            "eve-mac-local",
            "Eve hört über das Mikrofon dieses Macs zu und spricht über dessen Audioausgabe. "
            "Geeignet zum ersten Funktionstest ohne iPhone oder iPad.",
        ),
        (
            "Mac als Sprachserver für iPhone und iPad",
            "eve-mac-server",
            "Der Mac führt STT, Trinity und TTS aus. iPhone und iPad übertragen Audio "
            "über den geschützten Realtime-Port, zum Beispiel innerhalb von Tailscale.",
        ),
        (
            "Windows als Sprachserver für iPhone und iPad",
            "eve-windows-server",
            "Wie das Mac-Serverprofil, aber für eine Windows-Workstation mit CUDA. "
            "Dieses Profil auf einem Mac nicht für den normalen Betrieb auswählen.",
        ),
        (
            "Diagnose: Ornith direkt, ohne Trinity",
            "eve-direct-ornith",
            "Technisches Diagnoseprofil. Es verbindet die Sprachpipeline direkt mit Ornith "
            "und umgeht Trinitys Sessions, Memory, RAG und Agenten.",
        ),
    )

    def _selected_voice_profile_id(self):
        profile_id = self.voice_profile_combo.currentData()
        return str(profile_id or self.voice_profile_combo.currentText()).strip()

    def _load_voice_profile_form(self, _selection=None):
        profile_name = self._selected_voice_profile_id()
        profile = self.config.get("voice", {}).get("profiles", {}).get(profile_name, {})
        self.voice_bind_host_edit.setText(str(profile.get("bind_host") or "127.0.0.1"))
        self.voice_public_port_spin.setValue(int(profile.get("public_port") or 8766))
        description = next(
            (
                text
                for _label, profile_id, text in self.VOICE_PROFILE_OPTIONS
                if profile_id == profile_name
            ),
            "Benutzerdefiniertes Eve-Profil.",
        )
        self.voice_profile_description.setText(description)
        realtime = profile_name in {"eve-mac-server", "eve-windows-server"}
        for field in (
            self.voice_bind_host_edit,
            self.voice_public_port_spin,
            self.voice_token_edit,
            self.voice_realtime_hint,
        ):
            field.setVisible(realtime)
            label = self.voice_form.labelForField(field)
            if label is not None:
                label.setVisible(realtime)

    def _create_stt_tts_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        voice_group = QGroupBox("Voice Runtime")
        voice_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        voice_group.setMinimumHeight(570)
        voice_form = QFormLayout()
        self.voice_form = voice_form
        voice_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        voice_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        voice_form.setHorizontalSpacing(18)
        voice_form.setVerticalSpacing(12)
        voice_conf = self.config.get("voice", {})

        self.voice_engine_combo = QComboBox()
        self.voice_engine_combo.setMinimumWidth(440)
        self.voice_engine_combo.addItem(
            "Standard – bisherige Whisper-/System-TTS-Laufzeit", "legacy"
        )
        self.voice_engine_combo.addItem(
            "Eve – natürliches Echtzeitgespräch mit lokaler Stimme", "eve"
        )
        engine_index = self.voice_engine_combo.findData(voice_conf.get("engine", "legacy"))
        self.voice_engine_combo.setCurrentIndex(max(0, engine_index))
        voice_form.addRow("Sprachsystem:", self.voice_engine_combo)

        engine_hint = QLabel(
            "Standard behält Trinitys bisherigen STT/TTS-Weg bei. Eve kombiniert "
            "Parakeet-Spracherkennung, den vollständigen Trinity-Kern und Qwen3-TTS "
            "mit der lokalen Eve-Referenzstimme."
        )
        engine_hint.setWordWrap(True)
        engine_hint.setStyleSheet("color: #8fa3b8; font-size: 12px;")
        voice_form.addRow("", engine_hint)

        self.voice_profile_combo = QComboBox()
        self.voice_profile_combo.setMinimumWidth(440)
        for label, profile_id, _description in self.VOICE_PROFILE_OPTIONS:
            self.voice_profile_combo.addItem(label, profile_id)
        configured_profile = str(voice_conf.get("profile") or "eve-trinity")
        profile_index = self.voice_profile_combo.findData(configured_profile)
        if profile_index < 0:
            self.voice_profile_combo.addItem(
                f"Benutzerdefiniert: {configured_profile}", configured_profile
            )
            profile_index = self.voice_profile_combo.count() - 1
        self.voice_profile_combo.setCurrentIndex(profile_index)
        voice_form.addRow("Einsatz:", self.voice_profile_combo)

        self.voice_profile_description = QLabel()
        self.voice_profile_description.setWordWrap(True)
        self.voice_profile_description.setStyleSheet(
            "color: #8aadf4; font-size: 12px; font-weight: 500;"
        )
        voice_form.addRow("", self.voice_profile_description)

        profile_hint = QLabel(
            "Warum mehrere Profile? Es ist immer dieselbe Eve-Stimme. Die Auswahl "
            "bestimmt nur, auf welchem Computer STT und TTS laufen und ob ein "
            "iPhone oder iPad sein Audio dorthin überträgt."
        )
        profile_hint.setWordWrap(True)
        profile_hint.setStyleSheet("color: #8fa3b8; font-size: 11px;")
        voice_form.addRow("", profile_hint)

        self.voice_fallback_cb = QCheckBox(
            "Bei einem Fehler automatisch auf die bisherige STT/TTS-Laufzeit zurückschalten"
        )
        self.voice_fallback_cb.setChecked(voice_conf.get("fallback_to_legacy", True))
        voice_form.addRow("", self.voice_fallback_cb)

        self.voice_reference_edit = QLineEdit(str(voice_conf.get("reference_audio") or ""))
        self.voice_reference_edit.setPlaceholderText("TrinityRuntime/voices/eve/Eve_Schule.mp3")
        voice_form.addRow("Eve-Referenzaudio:", self.voice_reference_edit)

        profiles = voice_conf.get("profiles", {})
        current_profile = profiles.get(self._selected_voice_profile_id(), {})
        self.voice_bind_host_edit = QLineEdit(str(current_profile.get("bind_host") or "127.0.0.1"))
        voice_form.addRow("Realtime Bind-Adresse:", self.voice_bind_host_edit)

        self.voice_public_port_spin = QSpinBox()
        self.voice_public_port_spin.setRange(1024, 65535)
        self.voice_public_port_spin.setValue(int(current_profile.get("public_port") or 8766))
        voice_form.addRow("Realtime Port:", self.voice_public_port_spin)

        self.voice_token_edit = QLineEdit(str(voice_conf.get("access_token") or ""))
        self.voice_token_edit.setEchoMode(QLineEdit.Password)
        self.voice_token_edit.setPlaceholderText("Erforderlich bei 0.0.0.0 / Tailscale")
        voice_form.addRow("Realtime Token:", self.voice_token_edit)

        self.voice_realtime_hint = QLabel(
            "Diese drei Felder werden nur benötigt, wenn iPhone oder iPad Eve über "
            "den Mac beziehungsweise Windows-PC nutzen. Für Tailscale: 0.0.0.0, "
            "Port 8766 und auf allen Geräten dasselbe lange Token verwenden."
        )
        self.voice_realtime_hint.setWordWrap(True)
        self.voice_realtime_hint.setStyleSheet("color: #d29922; font-size: 11px;")
        voice_form.addRow("", self.voice_realtime_hint)

        self.voice_chunk_size_spin = QSpinBox()
        self.voice_chunk_size_spin.setRange(1, 64)
        self.voice_chunk_size_spin.setValue(int(voice_conf.get("streaming_chunk_size") or 8))
        voice_form.addRow("TTS Streaming-Chunk:", self.voice_chunk_size_spin)

        self.voice_prebuffer_spin = QSpinBox()
        self.voice_prebuffer_spin.setRange(0, 2000)
        self.voice_prebuffer_spin.setSuffix(" ms")
        self.voice_prebuffer_spin.setValue(int(voice_conf.get("audio_prebuffer_ms") if voice_conf.get("audio_prebuffer_ms") is not None else 180))
        voice_form.addRow("Client-Prebuffer:", self.voice_prebuffer_spin)

        self.voice_profile_combo.currentIndexChanged.connect(self._load_voice_profile_form)
        self._load_voice_profile_form()

        voice_hint = QLabel(
            "Legacy bleibt vollständig erhalten. Eve wird erst nach Neustart aktiv. "
            "Vor dem Umschalten: `trinity voice doctor --profile <Profil>`. "
            "Das Profil `eve-direct-ornith` umgeht Trinity und ist nur für Diagnosen gedacht."
        )
        voice_hint.setWordWrap(True)
        voice_hint.setStyleSheet("color: #d29922; font-size: 11px;")
        voice_form.addRow("", voice_hint)
        voice_group.setLayout(voice_form)
        layout.addWidget(voice_group)
        
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
