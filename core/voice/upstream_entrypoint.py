"""Start the pinned speech-to-speech runtime with Trinity compatibility fixes."""

from __future__ import annotations


def _response_requested(runtime_config) -> bool:
    """Return whether a realtime session wants STT to continue into LLM/TTS."""

    session = getattr(runtime_config, "session", None)
    audio = getattr(session, "audio", None)
    audio_input = getattr(audio, "input", None)
    turn_detection = getattr(audio_input, "turn_detection", None)
    if turn_detection is None:
        return True
    if isinstance(turn_detection, dict):
        value = turn_detection.get("create_response", True)
    else:
        value = getattr(turn_detection, "create_response", True)
    return True if value is None else bool(value)


def install_transcription_only_guard() -> None:
    """Honor ``create_response=false`` in speech-to-speech 0.2.11.

    Upstream currently emits the transcript event but still queues an LLM turn.
    Trinity uses short-lived transcription-only sessions when a Windows bridge
    delegates G2 audio to the Ubuntu GPU host. Those sessions must stop after
    Parakeet while normal Eve conversations remain untouched.
    """

    from speech_to_speech.api.openai_realtime.service import RealtimeService

    if getattr(RealtimeService, "_trinity_transcription_guard", False):
        return
    original = RealtimeService._on_transcription_completed

    def guarded(self, conn_id, event):
        state = self._state(conn_id)
        if not _response_requested(state.runtime_config):
            return self.conversation.on_transcription_completed(conn_id, event)
        return original(self, conn_id, event)

    RealtimeService._on_transcription_completed = guarded
    RealtimeService._trinity_transcription_guard = True


def install_session_update_ack() -> None:
    """Acknowledge applied session settings before clients start sending audio."""
    from openai.types.realtime import SessionUpdatedEvent
    from speech_to_speech.api.openai_realtime.service import RealtimeService

    if getattr(RealtimeService, "_trinity_session_ack", False):
        return
    original = RealtimeService.handle_session_update

    def acknowledged(self, conn_id, event):
        result = original(self, conn_id, event)
        if result is not None:
            return result
        created = self.build_session_created(conn_id)
        return SessionUpdatedEvent(type="session.updated", event_id=created.event_id,
                                   session=created.session)

    RealtimeService.handle_session_update = acknowledged
    RealtimeService._trinity_session_ack = True


def main() -> None:
    install_transcription_only_guard()
    install_session_update_ack()
    from speech_to_speech.s2s_pipeline import main as upstream_main

    upstream_main()


if __name__ == "__main__":
    main()
