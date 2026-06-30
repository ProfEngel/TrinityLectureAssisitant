import json
import base64
import sys
import time

from trinity_bridge import TrinityBridge, _local_path_value
from web_ui import render_web_ui
from chat_protocol import append_chat_event, load_chat_events, parse_command
from external_stt_feed import pop_external_stt_events
from memory_store import MemoryStore


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
                "harness_routing": {
                    "frameworks": {
                        "codex": {
                            "label": "Codex",
                            "roles": {
                                "agent_builder": False,
                                "complex_cases": True,
                                "agent_execution": False,
                            },
                        }
                    },
                    "agent_assignments": {"codex_agent": ["codex"]},
                },
                "agent_catalog": {
                    "agents": {
                        "agent-builder": {
                            "quality_status": "validated",
                            "allowed_tools": ["filesystem", "tests"],
                            "max_attempts": 4,
                        }
                    }
                },
            },
            "soul": "Meine Soul",
            "user": "Mein Profil",
        }
    )

    assert result["config"]["persona"]["agent_name"] == "Nova"
    assert result["config"]["persona"]["trigger_variants"]
    assert result["config"]["codex"]["projects"] == {"Buch": "/tmp/buch"}
    assert result["config"]["opencode"]["projects"] == {"Kurse": "/tmp/kurse"}
    assert result["config"]["harness_routing"]["frameworks"]["codex"]["roles"][
        "agent_builder"
    ] is False
    assert result["config"]["harness_routing"]["agent_assignments"] == {
        "codex_agent": ["codex"]
    }
    assert result["config"]["agent_catalog"]["agents"]["agent-builder"][
        "quality_status"
    ] == "validated"
    assert result["config"]["agent_catalog"]["agents"]["agent-builder"][
        "allowed_tools"
    ] == ["filesystem", "tests"]
    assert result["files"] == {"soul": "Meine Soul", "user": "Mein Profil"}


def test_bridge_can_test_harness_executable_without_running_agent_task(tmp_path):
    bridge = TrinityBridge(tmp_path)

    result = bridge.test_harness({"harness": "codex", "executable": sys.executable})
    pi_result = bridge.test_harness({"harness": "pi", "executable": sys.executable})
    trinity_result = bridge.test_harness({"harness": "trinity"})

    assert result["ok"] is True
    assert result["found"] is True
    assert result["path"] == sys.executable
    assert pi_result["ok"] is True
    assert pi_result["message"].startswith("Pi-Wrapper gefunden")
    assert trinity_result["ok"] is True
    assert trinity_result["message"].startswith("Trinity ist")


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


def test_bridge_end_session_creates_summary_asset_and_memory(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    history = home / "memory" / "classic_chat_history.jsonl"
    append_chat_event(
        history,
        {
            "role": "user",
            "source": "ios",
            "text": "Trinity, erklaere Spieltheorie.",
            "session_id": "session-1",
            "session_name": "Testsession",
        },
    )
    append_chat_event(
        history,
        {
            "role": "assistant",
            "source": "runtime",
            "text": "Spieltheorie analysiert strategische Entscheidungen.",
            "session_id": "session-1",
            "session_name": "Testsession",
        },
    )
    summary_path = home / "memory" / "summaries" / "Summary_Session_session-1.md"
    summary_path.parent.mkdir(parents=True)
    summary_path.write_text("# Summary\n\n## Hauptthemen\nSpieltheorie", encoding="utf-8")
    bridge = TrinityBridge(home)

    def fake_summary_agent(**kwargs):
        return {
            "summary": "## Hauptthemen\n- Spieltheorie\n\n## Key-Takeaways\n- Strategisches Verhalten.",
            "summary_path": str(summary_path),
            "html_payload": "<!-- SESSION_SUMMARY_PAYLOAD --><h2>Summary</h2>",
        }

    bridge._run_session_summary_agent = fake_summary_agent

    result = bridge.end_session({"session_id": "session-1", "session_name": "Testsession", "wait": True})

    assert result["ok"] is True
    assert result["created"] is True
    events = load_chat_events(history, limit=10)
    summary_event = events[-1]
    assert summary_event["source"] == "session-summary"
    assert summary_event["session_id"] == "session-1"
    assert "Spieltheorie" in summary_event["text"]
    assert summary_event["payload_html"].startswith("<!-- SESSION_SUMMARY_PAYLOAD")
    assert summary_event["attachments"][0]["kind"] == "summary"
    assert (home / "core" / "payload.html").read_text(encoding="utf-8").startswith(
        "<!-- SESSION_SUMMARY_PAYLOAD"
    )
    memories = MemoryStore(home / "memory" / "trinity_memory.sqlite3").search(
        "Spieltheorie", tags=["summary"], limit=5
    )
    assert memories[0]["kind"] == "session-summary"


def test_bridge_end_session_returns_before_background_summary_finishes(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    history = home / "memory" / "classic_chat_history.jsonl"
    append_chat_event(
        history,
        {
            "role": "user",
            "source": "ios",
            "text": "Trinity, fasse den Vortrag zu Decision Trees zusammen.",
            "session_id": "session-bg",
            "session_name": "Background",
        },
    )
    summary_path = home / "memory" / "summaries" / "Summary_Session_session-bg.md"
    summary_path.parent.mkdir(parents=True)
    bridge = TrinityBridge(home)

    def slow_summary_agent(**kwargs):
        time.sleep(0.08)
        summary_path.write_text("# Summary\n\nDecision Trees", encoding="utf-8")
        return {
            "summary": "## Hauptthemen\n- Decision Trees",
            "summary_path": str(summary_path),
            "html_payload": "<!-- SESSION_SUMMARY_PAYLOAD --><h2>Summary</h2>",
        }

    bridge._run_session_summary_agent = slow_summary_agent
    started = time.monotonic()
    result = bridge.end_session({"session_id": "session-bg", "session_name": "Background"})

    assert result["ok"] is True
    assert result["accepted"] is True
    assert result["created"] is False
    assert time.monotonic() - started < 0.05

    summary_event = None
    for _ in range(30):
        events = load_chat_events(history, limit=10)
        matches = [event for event in events if event.get("source") == "session-summary"]
        if matches:
            summary_event = matches[-1]
            break
        time.sleep(0.02)

    assert summary_event is not None
    assert summary_event["session_id"] == "session-bg"
    assert "Decision Trees" in summary_event["text"]
    assert summary_event["attachments"][0]["kind"] == "summary"


def test_bridge_end_session_can_summarize_unscoped_desktop_window(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    history = home / "memory" / "classic_chat_history.jsonl"
    old_event = append_chat_event(
        history,
        {
            "role": "user",
            "source": "classic",
            "text": "Alte Nachricht vor dem App-Start.",
        },
    )
    started_at = old_event["timestamp"] + 0.01
    time.sleep(0.02)
    append_chat_event(
        history,
        {
            "role": "user",
            "source": "classic",
            "text": "Neue Desktop-Frage zur Vorlesung.",
        },
    )
    summary_path = home / "memory" / "summaries" / "Summary_unscoped.md"
    summary_path.parent.mkdir(parents=True)
    bridge = TrinityBridge(home)
    captured = {}

    def fake_summary_agent(**kwargs):
        captured["transcript"] = kwargs["transcript_path"].read_text(encoding="utf-8")
        summary_path.write_text("# Summary\n\nNeue Desktop-Frage", encoding="utf-8")
        return {
            "summary": "## Hauptthemen\n- Neue Desktop-Frage",
            "summary_path": str(summary_path),
            "html_payload": "<!-- SESSION_SUMMARY_PAYLOAD --><h2>Summary</h2>",
        }

    bridge._run_session_summary_agent = fake_summary_agent
    result = bridge.end_session(
        {
            "session_id": "classic-unscoped-test",
            "session_name": "Classic Desktop",
            "include_unscoped": True,
            "started_at": started_at,
            "wait": True,
        }
    )

    assert result["created"] is True
    assert "Neue Desktop-Frage" in captured["transcript"]
    assert "Alte Nachricht" not in captured["transcript"]


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
