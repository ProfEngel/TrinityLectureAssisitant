import json
import base64

from trinity_bridge import TrinityBridge, _local_path_value
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
