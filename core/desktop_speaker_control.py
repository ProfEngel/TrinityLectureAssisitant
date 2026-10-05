"""Visible desktop controls for the shared Companion speaker selection."""

import json
import platform
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from configuration import load_config


class DesktopSpeakerControl(QWidget):
    def __init__(self, home, parent=None):
        super().__init__(parent)
        self.config_path = Path(home) / "core" / "config.json"
        self.network = QNetworkAccessManager(self)
        self.pending = False
        self.claim_button = QPushButton("Hier antworten · übernehmen", self)
        self.claim_button.setToolTip("Holt die Sprachausgabe vom iPhone oder iPad auf diesen Computer.")
        self.claim_button.clicked.connect(self.claim)
        self.mute_button = QPushButton("Stumm", self)
        self.mute_button.clicked.connect(self.mute)
        self.status = QLabel("Sprechstelle wird geladen …", self)
        self.status.setWordWrap(True)
        self.status.setStyleSheet("font-size: 11px; color: #ddd;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        row = QHBoxLayout()
        row.addWidget(self.claim_button)
        row.addWidget(self.mute_button)
        layout.addLayout(row)
        layout.addWidget(self.status)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1500)
        QTimer.singleShot(0, self.refresh)

    def claim(self):
        config = load_config(self.config_path)
        profile = str(config.get("system", {}).get("profile") or "PRIVAT").lower()
        hostname = platform.node().strip() or "Desktop"
        self._request({
            "device_id": f"desktop:{profile}:{hostname}",
            "label": f"Trinity Desktop · {hostname}",
            "kind": "desktop",
        })

    def mute(self):
        self._request({"device_id": "none", "label": "Stumm", "kind": "none"})

    def refresh(self):
        if not self.pending:
            self._request()

    def _request(self, payload=None):
        if self.pending:
            return
        config = load_config(self.config_path)
        companion = config.get("companion", {})
        host = str(companion.get("host") or "127.0.0.1")
        if host in {"0.0.0.0", "::"}:
            host = "127.0.0.1"
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        port = int(companion.get("port") or 8765)
        request = QNetworkRequest(QUrl(f"http://{host}:{port}/speaker"))
        request.setTransferTimeout(4000)
        token = str(companion.get("token") or "")
        if token:
            request.setRawHeader(b"Authorization", f"Bearer {token}".encode())
        self.pending = True
        self.claim_button.setEnabled(False)
        self.mute_button.setEnabled(False)
        if payload is None:
            reply = self.network.get(request)
        else:
            request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
            reply = self.network.post(request, json.dumps(payload).encode())
        reply.finished.connect(lambda: self._finished(reply))

    def _finished(self, reply):
        self.pending = False
        self.claim_button.setEnabled(True)
        self.mute_button.setEnabled(True)
        try:
            if reply.error() != QNetworkReply.NoError:
                self.status.setText("Sprechstelle nicht erreichbar · Bridge prüfen")
                return
            result = json.loads(bytes(reply.readAll()))
            if not result.get("ok"):
                self.status.setText("Sprechstelle konnte nicht gewählt werden")
                return
            active = result.get("kind") == "desktop"
            self.claim_button.setText("Antwortet hier" if active else "Hier antworten · übernehmen")
            self.status.setText("Ausgabe: " + str(result.get("label") or "Unbekannt"))
        except (ValueError, TypeError):
            self.status.setText("Sprechstelle konnte nicht gelesen werden")
        finally:
            reply.deleteLater()
