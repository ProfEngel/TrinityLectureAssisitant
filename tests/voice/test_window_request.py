import base64
import json
import os
import threading
import time

import pytest
from core.desktop_context import DesktopContextStore, wait_for_requested_desktop, add_current_desktop
from core.voice.window_request import wants_window, fingerprint


@pytest.mark.parametrize("text", ["Trinity, was siehst du hier?", "Schau mal hier",
    "Siehst du die Tabelle in diesem Fenster?", "Analysiere die offene App",
    "Trinity, lies den Wert in diesem freigegebenen Fenster."])
def test_visual_questions(text):
    assert wants_window(text)


@pytest.mark.parametrize("text", ["Trinity, hörst du mich?", "Fasse unser Gespräch zusammen",
    "Wie funktioniert ein Transformer?", "Trinity einfügen"])
def test_normal_questions_have_no_capture(text):
    assert not wants_window(text)
    assert not add_current_desktop({}, "/unused", query=text)


def test_capture_rendezvous_ack_and_no_stale_reuse(tmp_path):
    (tmp_path / 'core').mkdir()
    (tmp_path / 'core/config.json').write_text(json.dumps({'system': {'speech_output': {
        'kind': 'desktop', 'device_id': 'desktop:mac'}}}))
    query = "Trinity, was siehst du hier?"
    store = DesktopContextStore(tmp_path)
    payload = {"client_id": "voice", "device_id": "desktop:mac", "sequence": 1,
        "request_fingerprint": fingerprint("another question"), "active": True,
        "image_base64": base64.b64encode(b"\xff\xd8\xfftest").decode()}
    store.update(payload, profile="PRIVAT", session_id="one")
    assert not wait_for_requested_desktop(tmp_path, query, "desktop:mac", timeout=.04)
    def upload():
        time.sleep(.04)
        store.update({**payload, "sequence": 2, "request_fingerprint": fingerprint(query)},
                     profile="PRIVAT", session_id="one")
    thread = threading.Thread(target=upload)
    thread.start()
    assert wait_for_requested_desktop(tmp_path, query, "desktop:mac", timeout=.3)
    thread.join()
    # GUI can revoke a frame uploaded by the same device's audio process.
    store.update({**payload, "client_id": "gui", "active": False,
                  "request_fingerprint": fingerprint(query)}, profile="PRIVAT", session_id="one")
    assert not wait_for_requested_desktop(tmp_path, query, "desktop:mac", timeout=.3)


def test_diagnostic_is_small_private_and_contains_no_image(tmp_path):
    from core.voice.diagnostics import diagnostic
    diagnostic(tmp_path, "Wakeword", "No wakeword")
    path = tmp_path / "TrinityRuntime/voice/diagnostic_events.jsonl"
    event = json.loads(path.read_text())
    assert event["type"] == "trinity.debug"
    assert "image_base64" not in event
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600


def test_diagnostics_relay_only_to_selected_clients(tmp_path):
    from core.voice.transport.multiplex_proxy import MultiplexingVoiceRouter
    from core.voice.diagnostics import diagnostic
    from unittest.mock import Mock
    router = MultiplexingVoiceRouter("localhost", 1, 2, ["token"], tmp_path / "core/config.json")
    router._clients = {"mac": "desktop:mac", "old": "ipad:old"}
    router._enqueue = Mock()
    diagnostic(tmp_path, "LLM", "Antwort fertig")
    router._relay_diagnostics({"desktop:mac"})
    assert router._enqueue.call_count == 1
    peer, data = router._enqueue.call_args.args
    assert peer == "mac"
    assert json.loads(data)["stage"] == "LLM"
    router._relay_diagnostics({"desktop:mac"})
    assert router._enqueue.call_count == 1


def test_mac_capture_uploads_once_off_audio_callback(tmp_path, monkeypatch):
    import core.voice.local_realtime_client as module
    import mac_window_vision
    import PySide6.QtCore
    from core.voice.config import load_voice_config, default_voice_config
    from types import SimpleNamespace
    (tmp_path / "core").mkdir()
    (tmp_path / "core/config.json").write_text(json.dumps({
        "system": {"profile": "PRIVAT"}, "client": {"enabled": True,
        "server_url": "http://example.test:8765", "token": "test-secret"}}))
    client = module.LocalRealtimeAudioClient(load_voice_config(tmp_path, {"voice": default_voice_config()}))
    client._desktop_input_enabled = False
    client._desktop_output_enabled = True
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(PySide6.QtCore, "QSettings", lambda *_: SimpleNamespace(value=lambda *_args, **_kwargs: True))
    monkeypatch.setattr(mac_window_vision, "foreground_pid", lambda: 42)
    monkeypatch.setattr(mac_window_vision, "capture_window_jpeg", lambda pid: (b"\xff\xd8\xfftest", "Test"))
    done = threading.Event()
    uploads = []
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self):
            return b'{"has_image": true}'
    def upload(request, **kwargs):
        uploads.append(json.loads(request.data))
        assert request.full_url == "http://example.test:8765/desktop/context"
        done.set()
        return Response()
    monkeypatch.setattr(module, "urlopen", upload)
    client._capture_requested_window("Trinity, hörst du mich?")
    assert not uploads
    query = "Trinity, was siehst du hier?"
    client._capture_requested_window(query)
    assert done.wait(1)
    assert len(uploads) == 1
    assert uploads[0]["active"]
    assert uploads[0]["request_fingerprint"] == fingerprint(query)
