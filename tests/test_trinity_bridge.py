import json
import base64
import sys
import time

from trinity_bridge import TrinityBridge, _local_path_value
from web_ui import render_web_ui
from chat_protocol import append_chat_event, load_chat_events, pop_next_chat_request
from external_stt_feed import pop_external_stt_events
from memory_store import MemoryStore
from workspace_manager import TrinityWorkspaceManager


def test_bridge_writes_ios_message_to_command_file(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    bridge = TrinityBridge(home)

    result = bridge.send_message(
        {"text": "Hallo Trinity", "session_id": "ios-1", "privacy_mode": "local"}
    )

    assert result["ok"] is True
    request = pop_next_chat_request(home / "core")
    assert request["text"] == "Hallo Trinity"
    assert request["source"] == "ios"
    assert request["session_id"] == result["session"]["id"]
    assert request["client_session_id"] == "ios-1"
    assert request["privacy_mode"] == "local"


def test_bridge_keeps_explicit_web_source(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    bridge = TrinityBridge(home)

    bridge.send_message({"text": "Hallo", "source": "web"})

    request = pop_next_chat_request(home / "core")
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
    for view in ("Talk", "Vortrag", "Web", "Chat", "Live"):
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


def test_bridge_updates_agent_display_name(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    bridge = TrinityBridge(home)

    result = bridge.update_agent_display(
        {"agent_id": "agent-builder", "display_name": "Agentenwerkstatt"}
    )
    config = json.loads((home / "core" / "config.json").read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert config["agent_catalog"]["agents"]["agent-builder"]["display_name"] == "Agentenwerkstatt"


def test_bridge_dashboard_exposes_agent_metadata(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    bridge = TrinityBridge(home)

    result = bridge.dashboard()
    trinity = next(item for item in result["agents"]["items"] if item["id"] == "trinity-core")

    assert trinity["kind_label"] == "Trinity-Kernagent"
    assert "description" in trinity
    assert "allowed_tools" in trinity
    assert "rights" in trinity
    assert result["canvas"]["url"] == "http://127.0.0.1:8787"
    assert result["canvas"]["state"] == "not_installed"
    assert "message" in result["canvas"]


def test_bridge_exposes_profile_scoped_memory_graph(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    bridge = TrinityBridge(home)
    store = MemoryStore(home / "memory" / "trinity_memory.sqlite3")
    store.remember(
        "Trinity kennt den aktuellen Arbeitsraum.",
        tags=["trinity", "arbeitsraum"],
    )

    result = bridge.memory_graph()

    assert result["ok"] is True
    assert result["profile"] == bridge.profile
    assert any(node["type"] == "memory" for node in result["nodes"])
    assert any(node["type"] == "entity" for node in result["nodes"])
    assert result["links"]


def test_bridge_deletes_workspace_session(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    bridge = TrinityBridge(home)
    manager = TrinityWorkspaceManager(home)
    created = manager.create_session("20260702_0900_Test")

    result = bridge.delete_session({"session_id": created.id})

    assert result["ok"] is True
    assert result["deleted"] is True
    assert not created.path.exists()


def test_bridge_imports_companion_offline_events_once(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    bridge = TrinityBridge(home)
    payload = {
        "events": [
            {
                "event_id": "local-user-1",
                "role": "user",
                "source": "companion-offline",
                "text": "Hallo offline",
                "session_id": "session-offline",
                "session_name": "Offline Test",
            },
            {
                "event_id": "local-assistant-1",
                "role": "assistant",
                "source": "apple-foundation-offline",
                "text": "Lokale Antwort",
                "session_id": "session-offline",
                "session_name": "Offline Test",
            },
            {
                "event_id": "local-transcript-1",
                "role": "transcript",
                "source": "companion-offline-stt",
                "text": "Nur mitgeschriebener Offline-Talk",
                "session_id": "session-offline",
                "session_name": "Offline Test",
            },
        ]
    }

    first = bridge.import_offline_events(payload)
    second = bridge.import_offline_events(payload)
    events = load_chat_events(home / "memory" / "classic_chat_history.jsonl", limit=10)

    assert first["ok"] is True
    assert first["imported"] == 3
    assert second["imported"] == 0
    assert [event["text"] for event in events] == [
        "Hallo offline",
        "Lokale Antwort",
        "Nur mitgeschriebener Offline-Talk",
    ]
    assert events[-1]["role"] == "transcript"
    assert all(event["offline_synced"] is True for event in events)


def test_bridge_prompts_include_persona_wakeword_variants(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    (home / "core" / "Soul.md").write_text("Systemprompt", encoding="utf-8")
    (home / "core" / "User.md").write_text("Userprompt", encoding="utf-8")
    (home / "core" / "config.json").write_text(
        json.dumps(
            {
                "persona": {
                    "agent_name": "Trinity",
                    "trigger_variants": ["trinity", "triniti"],
                }
            }
        ),
        encoding="utf-8",
    )
    bridge = TrinityBridge(home)

    prompts = bridge.get_prompts()

    assert prompts["ok"] is True
    assert prompts["soul"] == "Systemprompt"
    assert prompts["user"] == "Userprompt"
    assert prompts["agent_name"] == "Trinity"
    assert prompts["trigger_variants"] == ["trinity", "triniti"]


def test_bridge_exposes_and_mutates_workspace_state(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    bridge = TrinityBridge(home)

    initial = bridge.workspace_state()
    workspace = bridge.create_workspace({"title": "Erendria"})["workspace"]
    session = bridge.create_session(
        {"title": "20260702_0900_Kapitel3", "workspace_id": workspace["id"]}
    )["session"]
    updated = bridge.update_session(
        {"session_id": session["id"], "title": "Kapitel 4", "pinned": True}
    )["session"]
    state = bridge.workspace_state(workspace_id=workspace["id"])
    archived = bridge.delete_session({"session_id": session["id"], "archive": True})

    assert initial["ok"] is True
    assert initial["inbox"] == "_inbox"
    assert workspace["title"] == "Erendria"
    assert updated["title"] == "Kapitel 4"
    assert updated["pinned"] is True
    assert state["selected_workspace_id"] == workspace["id"]
    assert any(item["id"] == session["id"] for item in state["sessions"])
    assert archived["archived"] is True


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


def test_legacy_token_mode_allows_loopback_ui_but_protects_remote_clients(tmp_path):
    class Headers(dict):
        def get(self, key, default=""):
            return super().get(key, default)

    class LocalHandler:
        client_address = ("127.0.0.1", 12345)
        headers = Headers()

    class RemoteHandler:
        client_address = ("100.90.5.25", 12345)
        headers = Headers()

    class AuthorizedRemoteHandler:
        client_address = ("100.90.5.25", 12345)
        headers = Headers({"Authorization": "Bearer secret"})

    bridge = TrinityBridge(tmp_path, token="secret")

    assert bridge.current_user(LocalHandler()) == {}
    assert bridge.current_user(RemoteHandler()) is None
    assert bridge.current_user(AuthorizedRemoteHandler()) == {}


def test_workspace_sessions_are_available_to_authenticated_users(tmp_path):
    class LocalHandler:
        client_address = ("127.0.0.1", 12345)

    class RemoteHandler:
        client_address = ("100.90.5.25", 12345)

    local_bridge = TrinityBridge(tmp_path)
    assert local_bridge.can_manage_workspaces(LocalHandler(), {}) is True
    assert local_bridge.can_manage_workspaces(RemoteHandler(), {}) is True
    assert local_bridge.can_manage_workspaces(RemoteHandler(), None) is False

    token_bridge = TrinityBridge(tmp_path / "token", token="secret")
    assert token_bridge.can_manage_workspaces(RemoteHandler(), {}) is True

    account_bridge = TrinityBridge(tmp_path / "accounts", auth_enabled=True)
    assert account_bridge.can_manage_workspaces(RemoteHandler(), {"role": "user"}) is True
    assert account_bridge.can_manage_workspaces(RemoteHandler(), {"role": "admin"}) is True
    assert account_bridge.can_manage_workspaces(RemoteHandler(), None) is False


def test_bridge_can_allow_tts_for_ios_message(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    bridge = TrinityBridge(home)

    bridge.send_message({"text": "Sag das laut", "speak": True})

    request = pop_next_chat_request(home / "core")
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


def test_bridge_transcribes_g2_audio_and_routes_to_wakeword_feed(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    bridge = TrinityBridge(home)

    class FakeTranscriber:
        def transcribe(self, audio_base64, **kwargs):
            assert audio_base64 == "cGNt"
            assert kwargs["sample_rate"] == 16000
            return {"text": "Trinity erklaere Spieltheorie", "language": "de"}

    bridge._audio_transcriber = FakeTranscriber()
    result = bridge.transcribe_audio(
        {
            "audio_base64": "cGNt",
            "sample_rate": 16000,
            "route": "stt",
            "session_id": "g2-session",
        }
    )

    assert result["ok"] is True
    assert result["routed"] is True
    events = pop_external_stt_events(home / "core" / "ios_stt_feed.jsonl")
    assert events[0]["source"] == "g2-stt"
    assert events[0]["text"] == "Trinity erklaere Spieltheorie"


def test_bridge_transcribes_g2_audio_and_routes_continuous_conversation(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    bridge = TrinityBridge(home)

    class FakeTranscriber:
        def transcribe(self, _audio_base64, **_kwargs):
            return {"text": "Was war letzte Woche offen?", "language": "de"}

    bridge._audio_transcriber = FakeTranscriber()
    result = bridge.transcribe_audio(
        {
            "audio_base64": "cGNt",
            "route": "message",
            "session_id": "g2-session",
        }
    )

    assert result["routed"] is True
    request = pop_next_chat_request(home / "core")
    assert request["source"] == "g2-conversation"
    assert request["session_id"] == result["request"]["session"]["id"]
    assert request["client_session_id"] == "g2-session"


def test_all_channels_share_one_server_authoritative_session(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    (home / "core" / "config.json").write_text(
        json.dumps(
            {
                "system": {"profile": "PRIVAT"},
                "control_plane": {
                    "runtime_root": str(home / "runtime"),
                    "vault_root": str(home / "BrainVault"),
                },
            }
        ),
        encoding="utf-8",
    )
    bridge = TrinityBridge(home)

    ios = bridge.send_message({"text": "vom iPhone", "session_id": "ios-local"})
    telegram = bridge.send_message(
        {"text": "aus Telegram", "source": "telegram", "session_id": "telegram"}
    )
    g2 = bridge.send_message({"text": "von G2", "source": "g2-conversation"})
    requests = [pop_next_chat_request(home / "core") for _ in range(3)]

    assert {item["session_id"] for item in requests} == {ios["session"]["id"]}
    assert telegram["session"]["id"] == ios["session"]["id"] == g2["session"]["id"]
    assert all(item["profile"] == "PRIVAT" for item in requests)
    assert bridge.instance_state()["knowledge"] == {
        "vault_root": str((home / "BrainVault").resolve()),
        "vault_available": False,
        "runtime_root": str((home / "runtime").resolve()),
        "rag_index_scope": "NOT_BUILT",
        "rag_sources": [],
        "graphify_index_scope": "NOT_BUILT",
    }


def test_bridge_can_transcribe_g2_audio_without_routing_a_command(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    bridge = TrinityBridge(home)

    class FakeTranscriber:
        def transcribe(self, _audio_base64, **_kwargs):
            return {"text": "Trinity Modus Konversation", "language": "de"}

    bridge._audio_transcriber = FakeTranscriber()
    result = bridge.transcribe_audio({"audio_base64": "cGNt", "route": "none"})

    assert result["text"] == "Trinity Modus Konversation"
    assert result["routed"] is False
    assert not (home / "core" / "ios_stt_feed.jsonl").exists()


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
    for _ in range(100):
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


def test_bridge_end_session_can_display_summary_in_new_session(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    history = home / "memory" / "classic_chat_history.jsonl"
    append_chat_event(
        history,
        {
            "role": "user",
            "source": "classic",
            "text": "Bitte erklaere Spieltheorie.",
            "session_id": "old-session",
            "session_name": "Alte Session",
        },
    )
    summary_path = home / "memory" / "summaries" / "Summary_old-session.md"
    summary_path.parent.mkdir(parents=True)
    bridge = TrinityBridge(home)

    def fake_summary_agent(**kwargs):
        summary_path.write_text("# Summary\n\nSpieltheorie", encoding="utf-8")
        return {
            "summary": "## Hauptthemen\n- Spieltheorie",
            "summary_path": str(summary_path),
        }

    bridge._run_session_summary_agent = fake_summary_agent
    result = bridge.end_session(
        {
            "session_id": "old-session",
            "session_name": "Alte Session",
            "display_session_id": "new-session",
            "display_session_name": "Neue Session",
            "wait": True,
        }
    )

    event = result["event"]
    assert event["session_id"] == "new-session"
    assert event["session_name"] == "Neue Session"
    assert event["metadata"]["original_session_id"] == "old-session"
    assert event["metadata"]["original_session_name"] == "Alte Session"
    assert "Spieltheorie" in event["text"]


def test_bridge_close_session_summarizes_and_activates_replacement(tmp_path):
    home = tmp_path
    (home / "core").mkdir()
    (home / "memory").mkdir()
    manager = TrinityWorkspaceManager(home)
    lecture = manager.create_workspace("Spieltheorie", kind="lecture")
    session = manager.create_session("Vorlesung 1", workspace_id=lecture.id)
    medium = session.path / "media" / "nash-diagramm.png"
    medium.write_bytes(b"png")
    history = home / "memory" / "classic_chat_history.jsonl"
    append_chat_event(
        history,
        {
            "role": "user",
            "source": "ios",
            "text": "Erkläre das Nash-Gleichgewicht.",
            "session_id": session.id,
            "session_name": session.title,
        },
    )
    source_summary = home / "memory" / "summaries" / "Summary.md"
    source_summary.parent.mkdir(parents=True)
    source_summary.write_text("# Summary", encoding="utf-8")
    bridge = TrinityBridge(home)
    bridge._run_session_summary_agent = lambda **_kwargs: {
        "summary": "## Hauptthemen\n- Nash-Gleichgewicht",
        "summary_path": str(source_summary),
    }

    result = bridge.close_session(
        {
            "session_id": session.id,
            "replacement_title": "Vorlesung 2",
            "mode": "lecture",
            "wait": True,
        }
    )

    closed = manager.get_session(session.id)
    replacement = manager.get_session(result["session"]["id"])
    assert closed.status == "closed"
    assert closed.summary_status == "complete"
    assert (closed.path / "summary.md").is_file()
    assert medium.is_file()
    assert replacement.workspace_id == lecture.id
    assert replacement.title == "Vorlesung 2"
    assert result["active_session"]["id"] == replacement.id

    target = manager.create_workspace("Modularchiv", kind="lecture")
    moved = manager.move_session(closed.id, target.id)
    assert (moved.path / "summary.md").is_file()
    assert (moved.path / "media" / "nash-diagramm.png").is_file()


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
    request = pop_next_chat_request(home / "core")
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

    request = pop_next_chat_request(home / "core")
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


def test_bridge_exposes_payload_image_to_clients_without_inline_html(tmp_path):
    home = tmp_path
    media_dir = home / "gen_images"
    media_dir.mkdir(parents=True)
    image = media_dir / "lecture-result.png"
    image.write_bytes(b"png")
    history = home / "memory" / "classic_chat_history.jsonl"
    append_chat_event(
        history,
        {
            "role": "assistant",
            "source": "runtime",
            "text": "Das Bild ist fertig.",
            "payload_html": f'<img src="{image.resolve().as_uri()}">',
        },
    )
    bridge = TrinityBridge(home)

    events = bridge.events_since(0, include_payload_html=False)

    assert events[0]["has_payload"] is True
    assert events[0]["attachments"][0]["name"] == "lecture-result.png"
    assert events[0]["attachments"][0]["mime"] == "image/png"
    assert events[0]["attachments"][0]["kind"] == "image"
    assert events[0]["attachments"][0]["media_url"].startswith("/media?path=")


def test_bridge_events_can_be_loaded_for_one_session(tmp_path):
    home = tmp_path
    history = home / "memory" / "classic_chat_history.jsonl"
    append_chat_event(
        history,
        {"role": "user", "text": "Session A", "session_id": "session-a"},
    )
    append_chat_event(
        history,
        {"role": "assistant", "text": "Session B", "session_id": "session-b"},
    )
    append_chat_event(
        history,
        {"role": "assistant", "text": "Unscoped Antwort", "request_id": "req-1"},
    )
    bridge = TrinityBridge(home)

    events = bridge.events_since(0, session_id="session-b")

    assert [event["text"] for event in events] == ["Session B"]


def test_bridge_deletes_single_chat_event(tmp_path):
    home = tmp_path
    history = home / "memory" / "classic_chat_history.jsonl"
    kept = append_chat_event(history, {"role": "user", "text": "Bleibt"})
    removed = append_chat_event(history, {"role": "assistant", "text": "Weg"})
    bridge = TrinityBridge(home)

    result = bridge.delete_event({"event_id": removed["event_id"]})

    assert result["ok"] is True
    events = bridge.events_since(0)
    assert [event["event_id"] for event in events] == [kept["event_id"]]


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
    bridge.send_message({"text": "Nur fuer Kollegin"}, user=colleague)

    admin_events = bridge.events_since(0, user=admin)
    colleague_events = bridge.events_since(0, user=colleague)
    assert [event["text"] for event in admin_events] == ["Nur fuer Admin"]
    assert [event["text"] for event in colleague_events] == ["Nur fuer Kollegin"]
    assert bridge.history_path_for(admin) != bridge.history_path_for(colleague)
