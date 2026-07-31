from voice.interfaces import ConversationBackend, SpeechToTextBackend, TextToSpeechBackend, Transcript
from voice.service import VoiceService


class STT(SpeechToTextBackend):
    def transcribe(self, pcm16, sample_rate=16_000):
        assert pcm16 == b"input"
        assert sample_rate == 16_000
        return Transcript("Wie geht es dir?", "de", 0.99)


class Conversation(ConversationBackend):
    def respond(self, text, *, session_id="", turn_id=""):
        assert text == "Wie geht es dir?"
        yield "Mir geht es gut."
        yield "Danke der Nachfrage."


class TTS(TextToSpeechBackend):
    def __init__(self):
        self.cancelled = []

    def synthesize(self, text, *, turn_id=""):
        yield text.encode("utf-8")

    def cancel(self, turn_id):
        self.cancelled.append(turn_id)


def test_mocked_pipeline_emits_text_and_audio_in_order():
    events = VoiceService(STT(), Conversation(), TTS()).process_audio(b"input")

    assert [event.type for event in events] == [
        "input_audio.stopped",
        "transcript.final",
        "assistant.text.delta",
        "audio.started",
        "audio.chunk",
        "assistant.text.delta",
        "audio.chunk",
        "assistant.text.final",
        "audio.completed",
    ]
    assert events[-2].payload["text"] == "Mir geht es gut. Danke der Nachfrage."
    assert events[4].payload["audio"] == b"Mir geht es gut."


def test_cancel_invalidates_the_current_turn():
    emitted = []
    tts = TTS()
    service = VoiceService(STT(), Conversation(), tts, emit=emitted.append)
    service.session.next_turn()

    service.cancel()

    assert tts.cancelled
    assert emitted[-1].type == "response.cancelled"
