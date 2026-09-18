"""Exercise the real upload -> scoped store -> voice backend -> brain path."""
import base64
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

from core.brain import TrinityBrain
from trinity_bridge import TrinityBridge, make_handler
from voice.conversation.trinity_backend import TrinityConversationBackend


def test_authenticated_slide_upload_reaches_voice_model_and_clear_removes_it(tmp_path, monkeypatch):
    bridge = TrinityBridge(tmp_path, token="test-secret")
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
            json=lambda: {"choices": [{"message": {"content": "Die Tabelle zeigt 73."}}]})

    monkeypatch.setattr("core.brain.requests.post", model_request)
    backend = TrinityConversationBackend(tmp_path)
    backend._brain = brain
    backend._append_chat_events = lambda *_args: None
    backend._runtime_voice_policy = lambda: ("office", ())

    def upload(sequence, active, token="test-secret"):
        payload = {"client_id": "ipad-test", "sequence": sequence, "active": active,
            "title": "Vorlesung", "page": 7, "text": "Tabelle Q4",
            "image_base64": base64.b64encode(b"\xff\xd8\xfftest").decode()}
        request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/lecture/context",
            data=json.dumps(payload).encode(), headers={"Content-Type": "application/json",
            "Authorization": "Bearer " + token})
        with urllib.request.urlopen(request) as response:
            return json.load(response)

    try:
        assert upload(1, True)["has_image"]
        assert "73" in " ".join(backend.respond("Trinity, erkläre diese Tabelle."))
        content = seen[-1]["messages"][-1]["content"]
        assert any(p.get("type") == "image_url" for p in content)
        assert any("Seite 7" in p.get("text", "") for p in content)
        upload(2, False)
        list(backend.respond("Was steht auf der aktuellen Folie?"))
        assert isinstance(seen[-1]["messages"][-1]["content"], str)
        assert "Keine aktuelle Folie" in seen[-1]["messages"][0]["content"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
