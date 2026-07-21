import threading
from http.server import ThreadingHTTPServer

from remote_client import RemoteTrinityClient
from trinity_bridge import TrinityBridge, make_handler
import pytest


def test_remote_client_registers_and_receives_own_events(tmp_path):
    (tmp_path / "core").mkdir()
    bridge = TrinityBridge(tmp_path, auth_enabled=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(bridge))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = RemoteTrinityClient(f"http://127.0.0.1:{server.server_port}")
    try:
        assert client.auth_status()["bootstrap_required"] is True
        client.login("Admin", "ein-langes-passwort", register=True)
        created = client.create_user("Kollegin", "zweites-langes-passwort")
        assert created["user"]["username"] == "Kollegin"
        client.send_message("Vom Desktop-Client")
        events = client.events_since(0)
        assert [event["text"] for event in events] == ["Vom Desktop-Client"]
        assert client.latest_payload()["html"] == ""
    finally:
        server.shutdown()
        server.server_close()


def test_remote_client_rejects_a_profile_mixup(tmp_path):
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "config.json").write_text(
        '{"system":{"profile":"PRIVAT"}}', encoding="utf-8"
    )
    bridge = TrinityBridge(tmp_path, token="secret")
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(bridge))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = RemoteTrinityClient(
        f"http://127.0.0.1:{server.server_port}",
        token="secret",
        profile="BIZ",
    )
    try:
        with pytest.raises(RuntimeError, match="Profil verwechselt"):
            client.current_session()
    finally:
        server.shutdown()
        server.server_close()
