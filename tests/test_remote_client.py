import threading
from http.server import ThreadingHTTPServer

from remote_client import RemoteTrinityClient
from trinity_bridge import TrinityBridge, make_handler


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
    finally:
        server.shutdown()
        server.server_close()
