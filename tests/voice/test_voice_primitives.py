import pytest

from voice.audio.formats import PCMFormat
from voice.audio.jitter_buffer import JitterBuffer
from voice.events import VoiceEvent
from voice.language_policy import enforce_input_language, segment_for_speech
from voice.metrics import VoiceMetrics
from voice.session import VoiceSession


def test_pcm16_format_and_bounded_jitter_buffer():
    PCMFormat().validate(b"\x00\x01" * 10)
    with pytest.raises(ValueError):
        PCMFormat().validate(b"\x00")
    buffer = JitterBuffer(max_chunks=2)
    buffer.push(b"one")
    buffer.push(b"two")
    buffer.push(b"three")
    assert buffer.pop() == b"two"
    assert buffer.pop() == b"three"


def test_old_turn_is_rejected_after_revision():
    session = VoiceSession("session")
    first = session.next_turn()
    second = session.next_turn()
    assert session.is_current(first) is False
    assert session.is_current(second) is True


def test_german_policy_allows_short_technical_terms_but_rejects_english_paragraph():
    assert enforce_input_language("Trinity, öffne Qwen3-TTS.") is None
    assert enforce_input_language("Please tell me what this is and how you would work with the model")
    assert segment_for_speech("Erster Satz. Zweiter Satz.", max_chars=14) == ["Erster Satz.", "Zweiter Satz."]


def test_events_and_metrics_contain_no_prompt_content(tmp_path):
    event = VoiceEvent("transcript.final", "s", "t", {"length": 12})
    assert event.as_dict()["type"] == "transcript.final"
    log = tmp_path / "metrics.jsonl"
    metrics = VoiceMetrics(log)
    metrics.observe("stt", 0.25, session_id="s", turn_id="t")
    content = log.read_text(encoding="utf-8")
    assert "stt" in content
    assert "prompt" not in content
