"""Thin macOS desktop surface for a remote Trinity server."""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineCore import QWebEngineScript
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QTabWidget, QToolBar

from core.configuration import load_config
from core.remote_client import RemoteTrinityClient


class ClientWindow(QMainWindow):
    def __init__(self, home: Path):
        super().__init__()
        config = load_config(home / "core" / "config.json")
        client = config.get("client", {})
        server_url = str(client.get("server_url") or "").rstrip("/")
        if not server_url.startswith(("http://", "https://")):
            raise ValueError("In Einstellungen > Trinity-Server Client fehlt die Server-URL.")
        self.setWindowTitle("Trinity · Client")
        self.remote = RemoteTrinityClient(
            server_url, token=str(client.get("token") or ""), timeout=5,
            profile=str(config.get("system", {}).get("profile") or "PRIVAT"),
        )
        self.profile = str(config.get("system", {}).get("profile") or "PRIVAT").lower()
        self.resize(1350, 900)
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)
        self.pages: dict[str, QWebEngineView] = {}
        self._add_page("Trinity", server_url, token=str(client.get("token") or ""))
        self._add_page("Vortrag", server_url, token=str(client.get("token") or ""), lecture=True)
        self._add_page("TrinityHUB", str(client.get("hub_url") or "http://100.121.209.16:3020/"))
        self._add_page("Medienwerkstatt", str(client.get("media_url") or "http://100.67.185.3:42010/"))
        self._add_page("Web", "https://www.google.com")
        toolbar = QToolBar("Navigation", self)
        self.addToolBar(toolbar)
        toolbar.addAction("Zurück", lambda: self.tabs.currentWidget().back())
        toolbar.addAction("Neu laden", lambda: self.tabs.currentWidget().reload())
        toolbar.addAction("Datei öffnen", self.open_file)
        output_menu = self.menuBar().addMenu("Ausgabe")
        output_menu.addAction("Hier auf dem Mac antworten", self.claim_speaker)
        output_menu.addAction("Stumm", self.mute_speaker)

    def claim_speaker(self):
        hostname = platform.node().strip() or "Desktop"
        try:
            self.remote.set_speaker(
                f"desktop:{self.profile}:{hostname}",
                f"Trinity Desktop · {hostname}",
            )
            self.statusBar().showMessage("Trinity antwortet jetzt auf diesem Mac", 5000)
        except Exception as exc:
            self.statusBar().showMessage(f"Sprechstelle nicht erreichbar: {exc}", 7000)

    def mute_speaker(self):
        try:
            self.remote.release_speaker()
            self.statusBar().showMessage("Trinity-Ausgabe stumm", 5000)
        except Exception as exc:
            self.statusBar().showMessage(f"Sprechstelle nicht erreichbar: {exc}", 7000)

    def _add_page(self, title: str, url: str, token: str = "", lecture: bool = False):
        page = QWebEngineView(self)
        if token:
            script = QWebEngineScript()
            script.setName("trinity-client-token")
            script.setInjectionPoint(QWebEngineScript.DocumentCreation)
            script.setWorldId(QWebEngineScript.MainWorld)
            script.setSourceCode(
                "if (location.origin === " + json.dumps(QUrl(url).scheme() + "://" + QUrl(url).authority())
                + ") localStorage.setItem('trinity.web.token', " + json.dumps(token) + ");"
            )
            page.page().scripts().insert(script)
        if lecture:
            page.loadFinished.connect(
                lambda ok, view=page: ok and view.page().runJavaScript(
                    "if (typeof showWorkspaceView === 'function') showWorkspaceView('lecture');"
                )
            )
        page.loadFinished.connect(
            lambda ok, name=title: print(f"Client-Ansicht {name}: {'geladen' if ok else 'nicht erreichbar'}", flush=True)
        )
        page.setUrl(QUrl(url))
        self.tabs.addTab(page, title)
        self.pages[title] = page

    def open_file(self):
        path, _filter = QFileDialog.getOpenFileName(
            self, "Datei öffnen", "", "Dokumente (*.pdf *.html *.htm *.xlsx *.docx *.pptx);;Alle Dateien (*)"
        )
        if not path:
            return
        url = QUrl.fromLocalFile(path)
        if Path(path).suffix.lower() in {".pdf", ".html", ".htm"}:
            self.pages["Web"].setUrl(url)
            self.tabs.setCurrentWidget(self.pages["Web"])
        else:
            QDesktopServices.openUrl(url)


def main():
    home = Path(__file__).resolve().parent
    app = QApplication(sys.argv)
    window = ClientWindow(home)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
