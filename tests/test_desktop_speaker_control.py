import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from core.desktop_speaker_control import DesktopSpeakerControl


def test_companion_to_desktop_takeover_mute_and_external_reclaim(tmp_path):
    selected = {"ok": True, "kind": "companion", "device_id": "ipad", "label": "iPad"}
    posted = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == "/speaker"
            assert self.headers["Authorization"] == "Bearer test-only"
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(selected).encode())

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            posted.append(payload)
            selected.update(payload)
            self.do_GET()

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "config.json").write_text(json.dumps({
        "companion": {"host": "0.0.0.0", "port": server.server_port, "token": "test-only"},
        "system": {"profile": "TEST"},
    }))
    app = QApplication.instance() or QApplication([])
    control = DesktopSpeakerControl(tmp_path)
    control.timer.stop()

    def wait_for(text):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            app.processEvents()
            if not control.pending and control.status.text() == text:
                return
            time.sleep(0.01)
        raise AssertionError(control.status.text())

    try:
        wait_for("Ausgabe: iPad")
        control.claim_button.click()
        deadline = time.monotonic() + 3
        while not posted and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert posted[0]["kind"] == "desktop"
        assert posted[0]["device_id"].startswith("desktop:test:")
        wait_for("Ausgabe: " + posted[0]["label"])
        control.mute_button.click()
        wait_for("Ausgabe: Stumm")
        assert posted[-1]["kind"] == "none"
        selected.update(kind="companion", device_id="iphone", label="iPhone")
        control.refresh()
        wait_for("Ausgabe: iPhone")
        assert "übernehmen" in control.claim_button.text()
    finally:
        control.close()
        server.shutdown()
        server.server_close()
