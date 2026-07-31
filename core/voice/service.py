"""Transport-neutral STT -> Trinity -> TTS orchestration.

The production runtime currently delegates streaming media I/O to the pinned
speech-to-speech package.  This service is the stable boundary used by tests
and future native transports; none of its stages owns a microphone or socket.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .events import VoiceEvent
from .interfaces import ConversationBackend, SpeechToTextBackend, TextToSpeechBackend
from .session import VoiceSession, VoiceTurn


EventSink = Callable[[VoiceEvent], None]


class VoiceService:
    def __init__(
        self,
        stt: SpeechToTextBackend,
        conversation: ConversationBackend,
        tts: TextToSpeechBackend,
        *,
        session: VoiceSession | None = None,
        emit: EventSink | None = None,
    ):
        self.stt = stt
        self.conversation = conversation
        self.tts = tts
        self.session = session or VoiceSession()
        self.emit = emit or (lambda _event: None)

    def cancel(self) -> None:
        """Invalidate current output and ask the TTS backend to stop it."""

        current = self.session.current_turn()
        if current is None:
            return
        self.tts.cancel(current.turn_id)
        self.session.cancel_current()
        self._emit("response.cancelled", current)

    def process_audio(self, pcm16: bytes, sample_rate: int = 16_000) -> list[VoiceEvent]:
        """Process one final speech segment and return all emitted events."""

        turn = self.session.next_turn()
        captured: list[VoiceEvent] = []

        def publish(event_type: str, payload: dict | None = None) -> None:
            event = VoiceEvent(event_type, turn.session_id, turn.turn_id, payload or {})
            captured.append(event)
            self.emit(event)

        publish("input_audio.stopped")
        transcript = self.stt.transcribe(pcm16, sample_rate=sample_rate)
        publish("transcript.final", {
            "text": transcript.text,
            "language": transcript.language,
            "confidence": transcript.confidence,
        })
        if not transcript.text.strip() or not self.session.is_current(turn):
            return captured

        text_parts: list[str] = []
        audio_started = False
        for segment in self.conversation.respond(
            transcript.text,
            session_id=turn.session_id,
            turn_id=turn.turn_id,
        ):
            if not self.session.is_current(turn):
                break
            clean = str(segment or "").strip()
            if not clean:
                continue
            text_parts.append(clean)
            publish("assistant.text.delta", {"text": clean})
            for chunk in self._current_chunks(self.tts.synthesize(clean, turn_id=turn.turn_id), turn):
                if not audio_started:
                    publish("audio.started")
                    audio_started = True
                publish("audio.chunk", {"audio": chunk})

        if self.session.is_current(turn):
            final_text = " ".join(text_parts).strip()
            publish("assistant.text.final", {"text": final_text})
            if audio_started:
                publish("audio.completed")
        return captured

    def _current_chunks(self, chunks: Iterable[bytes], turn: VoiceTurn) -> Iterable[bytes]:
        for chunk in chunks:
            if not self.session.is_current(turn):
                return
            if chunk:
                yield bytes(chunk)

    def _emit(self, event_type: str, turn: VoiceTurn) -> None:
        self.emit(VoiceEvent(event_type, turn.session_id, turn.turn_id))
