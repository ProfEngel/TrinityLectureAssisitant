import base64
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from core.brain import TrinityBrain
from core.desktop_context import DesktopContextStore, add_current_desktop
from trinity_bridge import TrinityBridge, make_handler
from unified_session import UnifiedSessionStore
from voice.conversation.trinity_backend import TrinityConversationBackend


IMAGE = base64.b64encode(b"\xff\xd8\xfftest").decode()
DEVICE = "desktop:privat:test-mac"


@pytest.fixture(autouse=True)
def selected_output(tmp_path):
    (tmp_path / 'core').mkdir(exist_ok=True)
    (tmp_path / 'core/config.json').write_text(json.dumps({'system': {'speech_output': {
        'kind': 'desktop', 'device_id': DEVICE, 'updated_at': 0}}}))


def payload(sequence=1, **changes):
    return {
        "client_id": "test-mac-process", "device_id": DEVICE, "sequence": sequence,
        "active": True, "title": "Excel - Planung", "image_base64": IMAGE, **changes,
    }


def test_window_context_is_short_lived_scoped_and_cleared(tmp_path, monkeypatch):
    store = DesktopContextStore(tmp_path)
    store.update(payload(), profile="PRIVAT", session_id="one")
    assert store.current(profile="PRIVAT", session_id="one", device_id=DEVICE)["title"] == "Excel - Planung"
    assert store.current(profile="BIZ", session_id="one", device_id=DEVICE) is None
    assert store.current(profile="PRIVAT", session_id="two", device_id=DEVICE) is None
    assert store.current(profile="PRIVAT", session_id="one", device_id="desktop:other") is None
    assert store.path.stat().st_mode & 0o777 == 0o600
    assert store.update(payload(0), profile="PRIVAT", session_id="one")["ignored"]
    store.update(payload(2, active=False), profile="PRIVAT", session_id="one")
    assert store.current(profile="PRIVAT", session_id="one", device_id=DEVICE) is None
    assert not store._read()["image_base64"]
    store.update(payload(3), profile="PRIVAT", session_id="one")
    stamp = store._read()["updated_at"]
    monkeypatch.setattr("core.desktop_context.time.time", lambda: stamp + 21)
    assert store.current(profile="PRIVAT", session_id="one", device_id=DEVICE) is None
    assert not store.path.exists()


@pytest.mark.parametrize("image", ["not-base64", base64.b64encode(b"not jpeg").decode(), "x" * 3000000])
def test_invalid_window_images_are_rejected(tmp_path, image):
    with pytest.raises(ValueError):
        DesktopContextStore(tmp_path).update(payload(image_base64=image), profile="PRIVAT", session_id="one")


def test_only_selected_mac_output_exposes_window_even_with_other_microphone(tmp_path):
    bridge = TrinityBridge(tmp_path, token="test-secret")
    session = UnifiedSessionStore(tmp_path).current()
    bridge.audio_input.update({"action": "claim", "kind": "desktop", "device_id": DEVICE, "label": "Test Mac"})
    DesktopContextStore(tmp_path).update(payload(), profile=bridge.profile, session_id=session.id)
    content = {"content": "Was siehst du hier?", "fallback_text": "Was siehst du hier?"}
    assert add_current_desktop(content, tmp_path)
    assert content["content"][-1]["type"] == "image_url"
    assert "Excel" in content["content"][-2]["text"]
    bridge.audio_input.update({"action": "claim", "kind": "companion", "device_id": "ipad", "label": "iPad"})
    other = {"content": "Was siehst du?", "fallback_text": "Was siehst du?"}
    assert add_current_desktop(other, tmp_path)
    bridge.set_speaker({"kind": "companion", "device_id": "ipad"})
    other = {"content": "Was siehst du?", "fallback_text": "Was siehst du?"}
    assert not add_current_desktop(other, tmp_path)
    assert isinstance(other["content"], str)


def test_authenticated_mac_upload_reaches_voice_vision_model(tmp_path, monkeypatch):
    bridge = TrinityBridge(tmp_path, token="test-secret")
    monkeypatch.setattr(bridge, "is_loopback_request", lambda _handler: False)
    bridge.audio_input.update({"action": "claim", "kind": "desktop", "device_id": DEVICE, "label": "Test Mac"})
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(bridge))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    seen = []
    brain = TrinityBrain.__new__(TrinityBrain)
    brain.config_path = str(tmp_path / "core" / "config.json")
    brain.reload_runtime_config = lambda: None
    brain.api_key = "test-key"
    brain.url = "http://model.invalid"
    brain.model = "test-vision"
    brain.live_skills = []
    brain.unavailable_skills = []
    brain._soul_cache = ""
    brain._user_cache = ""
    monkeypatch.setattr("core.brain.MemoryStore", lambda: SimpleNamespace(context_for_prompt=lambda _: ""))

    def model_request(_url, **kwargs):
        seen.append(kwargs["json"])
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None,
            json=lambda: {"choices": [{"message": {"content": "Die Tabelle enthält 73."}}]})

    monkeypatch.setattr("core.brain.requests.post", model_request)
    backend = TrinityConversationBackend(tmp_path)
    backend._brain = brain
    backend._append_chat_events = lambda *_args: None
    backend._runtime_voice_policy = lambda: ("office", ())

    def upload(value, token="test-secret"):
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/desktop/context",
            data=json.dumps(value).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
        )
        with urllib.request.urlopen(request) as response:
            return json.load(response)

    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            upload(payload(), token="wrong")
        assert error.value.code == 401
        assert upload(payload())["has_image"]
        assert "73" in " ".join(backend.respond("Trinity, was siehst du hier?"))
        content = seen[-1]["messages"][-1]["content"]
        assert any(part.get("type") == "image_url" for part in content)
        assert any("Excel" in part.get("text", "") for part in content)
        upload(payload(2, active=False))
        list(backend.respond("Was siehst du hier?"))
        assert isinstance(seen[-1]["messages"][-1]["content"], str)
        assert "Kein aktuelles Mac-Fenster" in seen[-1]["messages"][0]["content"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
