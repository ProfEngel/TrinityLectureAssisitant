import json
import base64

from trinity_bridge import TrinityBridge
from chat_protocol import append_chat_event, parse_command


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
