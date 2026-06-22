import json
import base64

from trinity_bridge import TrinityBridge, _local_path_value
from web_ui import render_web_ui
from chat_protocol import append_chat_event, load_chat_events, parse_command
from external_stt_feed import pop_external_stt_events


def test_bridge_writes_ios_message_to_command_file(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    bridge = TrinityBridge(home)

    result = bridge.send_message(
        {"text": "Hallo Trinity", "session_id": "ios-1", "privacy_mode": "local"}
    )

    assert result["ok"] is True
    request = parse_command((home / "core" / "cmd.txt").read_text(encoding="utf-8"))
    assert request["text"] == "Hallo Trinity"
    assert request["source"] == "ios"
    assert request["session_id"] == "ios-1"
    assert request["privacy_mode"] == "local"


def test_bridge_keeps_explicit_web_source(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    bridge = TrinityBridge(home)

    bridge.send_message({"text": "Hallo", "source": "web"})

    request = parse_command((home / "core" / "cmd.txt").read_text(encoding="utf-8"))
    assert request["source"] == "web"


def test_web_ui_contains_file_upload_and_token_login():
    page = render_web_ui()

    assert 'id="files"' in page
    assert "Bearer Token" in page
    assert "'/message'" in page
    assert 'id="settingsView"' in page
    assert "'/settings'" in page
    assert 'id="newSession"' in page
    assert 'id="microphoneToggle"' in page
    assert 'id="ttsToggle"' in page
    assert "'/runtime'" in page
    for view in ("Alltag", "Vortrag", "Web", "Presenter", "Chat", "Live"):
        assert view in page
    assert 'id="lectureFrame"' in page
    assert 'id="presenterFrame"' in page
    assert "'/payload'" in page


def test_bridge_runtime_updates_saved_config(tmp_path):
    bridge = TrinityBridge(tmp_path)

    updated = bridge.set_runtime(
        {"mode": "lecture", "microphone_enabled": False, "tts_enabled": False}
    )

    assert updated["mode"] == "lecture"
    assert updated["microphone_enabled"] is False
    assert updated["tts_enabled"] is False
    assert bridge.get_runtime()["mode"] == "lecture"


def test_bridge_web_settings_round_trip_and_keeps_unknown_values(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    bridge = TrinityBridge(home)

    result = bridge.save_web_settings(
        {
            "config": {
                "persona": {"agent_name": "Nova"},
                "codex": {"projects": {"Buch": "/tmp/buch"}},
                "opencode": {"projects": {"Kurse": "/tmp/kurse"}},
            },
            "soul": "Meine Soul",
            "user": "Mein Profil",
        }
    )

    assert result["config"]["persona"]["agent_name"] == "Nova"
    assert result["config"]["persona"]["trigger_variants"]
    assert result["config"]["codex"]["projects"] == {"Buch": "/tmp/buch"}
    assert result["config"]["opencode"]["projects"] == {"Kurse": "/tmp/kurse"}
    assert result["files"] == {"soul": "Meine Soul", "user": "Mein Profil"}


def test_web_settings_are_local_or_administrator_only(tmp_path):
    class LocalHandler:
        client_address = ("127.0.0.1", 12345)

    class RemoteHandler:
        client_address = ("100.90.5.25", 12345)

    local_bridge = TrinityBridge(tmp_path)
    assert local_bridge.can_manage_settings(LocalHandler(), {}) is True
    assert local_bridge.can_manage_settings(RemoteHandler(), {}) is False

    account_bridge = TrinityBridge(tmp_path / "accounts", auth_enabled=True)
    assert account_bridge.can_manage_settings(LocalHandler(), {"role": "user"}) is False
    assert account_bridge.can_manage_settings(RemoteHandler(), {"role": "admin"}) is True


def test_bridge_can_allow_tts_for_ios_message(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    bridge = TrinityBridge(home)

    bridge.send_message({"text": "Sag das laut", "speak": True})

    request = parse_command((home / "core" / "cmd.txt").read_text(encoding="utf-8"))
    assert request["silent"] is False
    assert request["allow_tts"] is True


def test_bridge_writes_live_stt_feed(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    bridge = TrinityBridge(home)

    result = bridge.send_stt(
        {
            "text": "Trinity kannst du das erklaeren",
            "is_final": True,
            "speak": True,
            "session_id": "ios-1",
            "privacy_mode": "local",
        }
    )

    assert result["ok"] is True
    events = pop_external_stt_events(home / "core" / "ios_stt_feed.jsonl")
    assert events[0]["text"] == "Trinity kannst du das erklaeren"
    assert events[0]["is_final"] is True
    assert events[0]["speak"] is True

    history = load_chat_events(home / "memory" / "classic_chat_history.jsonl")
    assert history[0]["role"] == "user"
    assert history[0]["source"] == "ios-stt"
    assert history[0]["text"] == "Trinity kannst du das erklaeren"


def test_bridge_accepts_image_and_pdf_attachments(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    bridge = TrinityBridge(home)

    result = bridge.send_message(
        {
            "text": "Was siehst du?",
            "attachments": [
                {
                    "name": "bild.png",
                    "mime": "image/png",
                    "data_base64": base64.b64encode(b"\x89PNG\r\n\x1a\nsmall").decode("ascii"),
                },
                {
                    "name": "skript.pdf",
                    "mime": "application/pdf",
                    "data_base64": base64.b64encode(b"%PDF-1.4\n").decode("ascii"),
                },
            ],
        }
    )

    assert result["ok"] is True
    request = parse_command((home / "core" / "cmd.txt").read_text(encoding="utf-8"))
    assert [item["kind"] for item in request["attachments"]] == ["image", "pdf"]
    assert all(item["path"] for item in request["attachments"])


def test_bridge_uses_default_prompt_for_attachment_only_message(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    bridge = TrinityBridge(home)

    bridge.send_message(
        {
            "attachments": [
                {
                    "name": "bild.png",
                    "mime": "image/png",
                    "data_base64": base64.b64encode(b"\x89PNG\r\n\x1a\nsmall").decode("ascii"),
                }
            ]
        }
    )

    request = parse_command((home / "core" / "cmd.txt").read_text(encoding="utf-8"))
    assert request["text"] == "Bitte analysiere die beigefügten Anlagen."


def test_bridge_returns_events_and_rewrites_file_urls(tmp_path):
    home = tmp_path
    media_dir = home / "gen_images"
    media_dir.mkdir(parents=True)
    image = media_dir / "result.png"
    image.write_bytes(b"png")
    history = home / "memory" / "classic_chat_history.jsonl"
    append_chat_event(
        history,
        {
            "role": "assistant",
            "source": "runtime",
            "text": "Fertig",
            "payload_html": f'<img src="{image.resolve().as_uri()}">',
        },
    )
    bridge = TrinityBridge(home)

    events = bridge.events_since(0)

    assert events[0]["text"] == "Fertig"
    assert "/media?path=" in events[0]["payload_html"]
    assert "file://" not in events[0]["payload_html"]


def test_bridge_rewrites_core_payload_media_urls(tmp_path):
    home = tmp_path
    core_dir = home / "core"
    core_dir.mkdir(parents=True)
    image = core_dir / "sandbox_screenshot.png"
    image.write_bytes(b"png")
    history = home / "memory" / "classic_chat_history.jsonl"
    append_chat_event(
        history,
        {
            "role": "assistant",
            "source": "runtime",
            "text": "Sandbox fertig",
            "payload_html": f'<img src="{image.resolve().as_uri()}">',
        },
    )
    bridge = TrinityBridge(home)

    events = bridge.events_since(0)

    assert "/media?path=" in events[0]["payload_html"]
    assert "sandbox_screenshot.png" in events[0]["payload_html"]
    assert "file://" not in events[0]["payload_html"]


def test_bridge_returns_media_urls_for_event_attachments(tmp_path):
    home = tmp_path
    upload_dir = home / "memory" / "companion_uploads"
    upload_dir.mkdir(parents=True)
    image = upload_dir / "result.png"
    image.write_bytes(b"png")
    history = home / "memory" / "classic_chat_history.jsonl"
    append_chat_event(
        history,
        {
            "role": "assistant",
            "source": "runtime",
            "text": "Fertig",
            "attachments": [
                {
                    "name": "result.png",
                    "path": str(image),
                    "kind": "image",
                    "mime": "image/png",
                    "size": 3,
                }
            ],
        },
    )
    bridge = TrinityBridge(home)

    events = bridge.events_since(0)

    attachment = events[0]["attachments"][0]
    assert attachment["media_url"].startswith("/media?path=")
    assert "path" not in attachment


def test_bridge_media_urls_include_token_when_configured(tmp_path):
    home = tmp_path
    media_dir = home / "gen_images"
    media_dir.mkdir(parents=True)
    image = media_dir / "result.png"
    image.write_bytes(b"png")
    history = home / "memory" / "classic_chat_history.jsonl"
    append_chat_event(
        history,
        {
            "role": "assistant",
            "source": "runtime",
            "text": "Fertig",
            "payload_html": f'<img src="{image.resolve().as_uri()}">',
        },
    )
    bridge = TrinityBridge(home, token="secret-token")

    events = bridge.events_since(0)

    assert "token=secret-token" in events[0]["payload_html"]


def test_bridge_normalizes_windows_drive_paths_from_media_query():
    raw = "%2FC%3A%2FUsers%2FMatMax%2FAppData%2FLocal%2FTrinity%2Fgen_images%2Fgen.png"

    assert _local_path_value(raw) == "C:/Users/MatMax/AppData/Local/Trinity/gen_images/gen.png"


def test_bridge_rejects_media_outside_allowed_roots(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    bridge = TrinityBridge(home)

    try:
        bridge.media_path_from_query(str(outside))
    except PermissionError:
        pass
    else:
        raise AssertionError("Medien außerhalb erlaubter Ordner dürfen nicht serviert werden.")


def test_authenticated_bridge_separates_user_histories_and_uploads(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    bridge = TrinityBridge(home, auth_enabled=True)
    admin_login = bridge.auth.register_first_admin("Admin", "ein-langes-passwort")
    admin = bridge.auth.authenticate(admin_login["token"])
    colleague = bridge.auth.create_user(admin, "Kollegin", "zweites-langes-passwort")

    bridge.send_message({"text": "Nur fuer Admin"}, user=admin)
    bridge.command_path.unlink()
    bridge.send_message({"text": "Nur fuer Kollegin"}, user=colleague)

    admin_events = bridge.events_since(0, user=admin)
    colleague_events = bridge.events_since(0, user=colleague)
    assert [event["text"] for event in admin_events] == ["Nur fuer Admin"]
    assert [event["text"] for event in colleague_events] == ["Nur fuer Kollegin"]
    assert bridge.history_path_for(admin) != bridge.history_path_for(colleague)
