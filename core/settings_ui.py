import sys
import json
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QCheckBox, QComboBox, QGroupBox, QFormLayout,
                             QTextEdit, QTabWidget, QDoubleSpinBox, QSpinBox,
                             QScrollArea, QFrame, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


CORE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = {
    "llm": {
        "use_local": True,
        "local_url": "http://localhost:1234/v1/chat/completions",
        "local_model": "",
        "remote_url": "https://openrouter.ai/api/v1/chat/completions",
        "remote_model": "",
        "api_key": ""
    },
    "apis": {
        "tavily": "",
        "fal_ai": ""
    },
    "persona": {
        "agent_name": "Trinity",
        "trigger_variants": ["trinity", "triniti", "trindy", "trinnity", "trinitiy", "trenty", "trendy"]
    },
    "image": {
        "primary_model": "fal-ai/nano-banana-2",
        "fallback_model": "fal-ai/nano-banana-pro"
    },
    "stt": {
        "model": "small",
        "silence_threshold": 0.015,
        "chunk_duration": 6,
        "show_volume_meter": False
    },
    "tts": {
        "voice": "Samantha"
    },
    "proactive": {
        "heartbeat_enabled": False,
        "bubbles_enabled": False,
        "visuals_enabled": False,
        "interval_minutes": 2,
        "auto_rag_indexing": False
    },
    "system": {
        "show_terminal": False
    },
    "audio_routing": {
        "private_device": "Standard",
        "public_device": "Standard"
    },
    "telegram": {
        "enabled": False,
        "bot_token": "",
        "chat_id": ""
    },
    "comfyui": {
        "enabled": False,
        "server_url": "http://YOUR_TAILSCALE_NODE:8188",
        "default_workflow": "Flux2_Klein_T2I_API.json"
    }
}


class SettingsWindow(QMainWindow):
    def __init__(self, config_path):
        super().__init__()
        self.config_path = config_path
        self.soul_path = os.path.join(CORE_DIR, "Soul.md")
        self.user_path = os.path.join(CORE_DIR, "User.md")
        self.setWindowTitle("Trinity Assistant – Einstellungen")
        self.setMinimumSize(600, 700)
        
        self.load_config()
        self.init_ui()
        self.apply_stylesheet()
        
    def load_config(self):
        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
            # Fehlende Sektionen mit Defaults auffüllen
            for key, val in DEFAULT_CONFIG.items():
                if key not in self.config:
                    self.config[key] = val
                elif isinstance(val, dict):
                    for k2, v2 in val.items():
                        if k2 not in self.config[key]:
                            self.config[key][k2] = v2
        except (FileNotFoundError, json.JSONDecodeError):
            self.config = DEFAULT_CONFIG.copy()

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
        # LLM
        self.config["llm"]["use_local"] = self.local_llm_cb.isChecked()
        self.config["llm"]["local_url"] = self.local_url_edit.text()
        self.config["llm"]["local_model"] = self.local_model_edit.text()
        self.config["llm"]["remote_url"] = self.remote_url_edit.text()
        self.config["llm"]["remote_model"] = self.remote_model_edit.text()
        self.config["llm"]["api_key"] = self.remote_key_edit.text()
        
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
        self.config["system"]["show_terminal"] = getattr(self, 'terminal_cb', QCheckBox()).isChecked()
        
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

        # ComfyUI
        if "comfyui" not in self.config:
            self.config["comfyui"] = {}
        if hasattr(self, 'comfyui_cb'):
            self.config["comfyui"]["enabled"] = self.comfyui_cb.isChecked()
            self.config["comfyui"]["server_url"] = self.comfyui_url_edit.text().strip()
            self.config["comfyui"]["default_workflow"] = self.comfyui_workflow_edit.text().strip()
            
        # Proactive Additions
        if hasattr(self, 'auto_rag_cb'):
            self.config["proactive"]["auto_rag_indexing"] = self.auto_rag_cb.isChecked()
        
        # Config-Datei speichern
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)
        
        # Soul.md speichern
        self.save_text_file(self.soul_path, self.soul_edit.toPlainText())
        
        # User.md speichern
        self.save_text_file(self.user_path, self.user_edit.toPlainText())
        
        QMessageBox.information(self, "Gespeichert", 
            "Einstellungen gespeichert.\nBitte starte Trinity neu, damit die Änderungen wirksam werden.")

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a2e; }
            QTabWidget::pane { border: 1px solid #333; background: #16213e; border-radius: 8px; }
            QTabBar::tab { background: #1a1a2e; color: #888; padding: 10px 18px; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: #16213e; color: #00bfff; border-bottom: 2px solid #00bfff; }
            QGroupBox { color: #00bfff; font-weight: bold; border: 1px solid #333; border-radius: 8px; margin-top: 12px; padding-top: 16px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QLabel { color: #ccc; }
            QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox { 
                background: #0f3460; color: #eee; border: 1px solid #444; border-radius: 4px; padding: 6px; 
            }
            QLineEdit:focus, QComboBox:focus { border-color: #00bfff; }
            QTextEdit { background: #0f3460; color: #eee; border: 1px solid #444; border-radius: 4px; padding: 6px; font-family: monospace; }
            QCheckBox { color: #ccc; }
            QCheckBox::indicator:checked { background: #00bfff; border: 1px solid #00bfff; }
            QPushButton { background: #333; color: #ccc; border: 1px solid #444; border-radius: 6px; padding: 8px 16px; }
            QPushButton:hover { background: #444; }
            QPushButton#saveBtn { background: #00bfff; color: #000; font-weight: bold; }
            QPushButton#saveBtn:hover { background: #33ccff; }
        """)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # Header
        header = QLabel("⚙️ Trinity Assistant – Einstellungen")
        header.setFont(QFont("", 18, QFont.Bold))
        header.setStyleSheet("color: #00bfff; margin-bottom: 8px;")
        main_layout.addWidget(header)
        
        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self._create_persona_tab(), "🤖 Persona")
        tabs.addTab(self._create_llm_tab(), "🧠 LLM")
        tabs.addTab(self._create_api_tab(), "🔑 APIs & Bild")
        tabs.addTab(self._create_stt_tts_tab(), "🎙️ Sprache")
        tabs.addTab(self._create_audio_tab(), "🔊 Audio-Routing")
        tabs.addTab(self._create_proactive_tab(), "🚀 Proaktiv")
        tabs.addTab(self._create_system_tab(), "🖥️ System")
        tabs.addTab(self._create_soul_tab(), "📝 Soul")
        tabs.addTab(self._create_user_tab(), "👤 User")
        main_layout.addWidget(tabs)
        
        # Buttons
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.close)
        
        save_btn = QPushButton("💾 Speichern")
        save_btn.setObjectName("saveBtn")
        save_btn.clicked.connect(self.save_config)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        main_layout.addLayout(btn_layout)

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

    # --- TAB: System ---
    def _create_system_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("System & App-Verhalten")
        form = QFormLayout()
        
        system_conf = self.config.get("system", {})
        self.terminal_cb = QCheckBox("Terminal-Fenster im Hintergrund anzeigen (Log-Ausgabe)")
        self.terminal_cb.setChecked(system_conf.get("show_terminal", False))
        form.addRow(self.terminal_cb)
        
        hint = QLabel("Wenn aktiv, öffnet die native macOS App beim Starten zusätzlich das Terminal, damit du Logs sehen kannst.\nBenötigt einen Neustart der App.")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)
        form.addRow("", hint)
        
        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()
        return widget

    # --- TAB: Audio-Routing (Souffleur) ---
    def _create_audio_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("Souffleur-Skill (Dynamisches Audio-Routing)")
        form = QFormLayout()
        
        # Lese verfügbare Audio-Ausgänge (Mac-only)
        devices = ["Standard"]
        try:
            import subprocess
            out = subprocess.check_output(["say", "-a", "?"], stderr=subprocess.STDOUT).decode("utf-8")
            for line in out.strip().split("\n"):
                parts = line.strip().split(" ", 1)
                if len(parts) == 2:
                    devices.append(parts[1])
        except Exception as e:
            print("Konnte Audio-Geräte nicht auslesen:", e)
            
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
        layout = QVBoxLayout(widget)
        
        # Lokal
        local_group = QGroupBox("Lokales LLM (LMStudio)")
        local_form = QFormLayout()
        
        self.local_llm_cb = QCheckBox("Lokales LLM aktivieren")
        self.local_llm_cb.setChecked(self.config["llm"]["use_local"])
        local_form.addRow(self.local_llm_cb)
        
        self.local_url_edit = QLineEdit(self.config["llm"]["local_url"])
        local_form.addRow("URL:", self.local_url_edit)
        
        self.local_model_edit = QLineEdit(self.config["llm"]["local_model"])
        local_form.addRow("Modell:", self.local_model_edit)
        
        local_group.setLayout(local_form)
        layout.addWidget(local_group)
        
        # Remote
        remote_group = QGroupBox("Remote LLM (OpenRouter / API)")
        remote_form = QFormLayout()
        
        self.remote_url_edit = QLineEdit(self.config["llm"]["remote_url"])
        remote_form.addRow("URL:", self.remote_url_edit)
        
        self.remote_model_edit = QLineEdit(self.config["llm"]["remote_model"])
        remote_form.addRow("Modell:", self.remote_model_edit)
        
        self.remote_key_edit = QLineEdit(self.config["llm"]["api_key"])
        self.remote_key_edit.setEchoMode(QLineEdit.Password)
        remote_form.addRow("API Key:", self.remote_key_edit)
        
        remote_group.setLayout(remote_form)
        layout.addWidget(remote_group)
        layout.addStretch()
        return widget

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

        self.comfyui_cb = QCheckBox("ComfyUI aktivieren")
        self.comfyui_cb.setChecked(comfyui_conf.get("enabled", False))
        comfy_form.addRow(self.comfyui_cb)

        self.comfyui_url_edit = QLineEdit(comfyui_conf.get("server_url", ""))
        self.comfyui_url_edit.setPlaceholderText("z.B. http://100.122.13.123:8188")
        comfy_form.addRow("Server URL:", self.comfyui_url_edit)

        self.comfyui_workflow_edit = QLineEdit(comfyui_conf.get("default_workflow", "Flux2_Klein_T2I_API.json"))
        self.comfyui_workflow_edit.setPlaceholderText("Flux2_Klein_T2I_API.json")
        comfy_form.addRow("Standard-Workflow:", self.comfyui_workflow_edit)

        test_btn = QPushButton("🔗 Verbindung testen")
        test_btn.clicked.connect(self._test_comfyui_connection)
        comfy_form.addRow("", test_btn)

        comfy_hint = QLabel(
            "Trigger: 'lokales Bild erstellen', 'flux render', 'auf meinem Server' …\n"
            "Workflows liegen in: agents/comfyui_agent/workflows/\n"
            "Generierte Bilder: agents/comfyui_agent/media/output/"
        )
        comfy_hint.setStyleSheet("color: #666; font-size: 11px;")
        comfy_hint.setWordWrap(True)
        comfy_form.addRow("", comfy_hint)

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
        tts_form.addRow("macOS Stimme:", self.tts_voice_edit)
        
        hint = QLabel("Verfügbare Stimmen: Samantha, Daniel, Anna, etc.\nPrüfe mit: say -v '?' im Terminal.")
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
