from types import SimpleNamespace
import sys

from voice.upstream_entrypoint import _response_requested
from voice.upstream_entrypoint import install_session_update_ack


def test_session_update_ack_preserves_errors_and_is_idempotent(monkeypatch):
    class Service:
        def handle_session_update(self, conn_id, event):
            return event.get("error")

        def build_session_created(self, conn_id):
            return SimpleNamespace(event_id="event-1", session={"id": conn_id})

    monkeypatch.setitem(sys.modules, "speech_to_speech.api.openai_realtime.service",
                        SimpleNamespace(RealtimeService=Service))
    monkeypatch.setitem(sys.modules, "openai.types.realtime",
                        SimpleNamespace(SessionUpdatedEvent=SimpleNamespace))
    install_session_update_ack()
    handler = Service.handle_session_update
    install_session_update_ack()
    assert Service.handle_session_update is handler
    result = Service().handle_session_update("session-1", {})
    assert result.type == "session.updated"
    assert result.session == {"id": "session-1"}
    error = object()
    assert Service().handle_session_update("session-1", {"error": error}) is error


def _runtime_config(value):
    return SimpleNamespace(session=SimpleNamespace(audio=SimpleNamespace(
        input=SimpleNamespace(turn_detection=SimpleNamespace(create_response=value))
    )))


def test_transcription_only_session_does_not_request_response():
    assert _response_requested(_runtime_config(False)) is False


def test_normal_realtime_session_requests_response():
    assert _response_requested(_runtime_config(True)) is True
    assert _response_requested(_runtime_config(None)) is True


def test_missing_turn_detection_preserves_upstream_response_behavior():
    config = SimpleNamespace(session=SimpleNamespace(audio=SimpleNamespace(
        input=SimpleNamespace(turn_detection=None)
    )))

    assert _response_requested(config) is True
