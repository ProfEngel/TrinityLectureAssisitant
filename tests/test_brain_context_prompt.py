from brain import build_context_prompt
from brain import reply_token_budget


def test_spoken_budget_preserves_explicit_detail_and_writing():
    assert reply_token_budget('Was ist Overfitting?', True) == 320
    assert reply_token_budget('Erkläre das ausführlich', True) == 650
    assert reply_token_budget('Fasse das Diktat zusammen', True) == 650
    assert reply_token_budget('Überarbeite den Text', True) == 650
    assert reply_token_budget('Was ist Overfitting?', False) == 1500


def test_first_speech_chunk_is_short_and_no_words_are_lost():
    from voice.language_policy import segment_for_speech
    text = ' '.join(['Gedanke'] * 80) + '.'
    chunks = segment_for_speech(text)
    assert len(chunks[0]) <= 120
    assert ' '.join(chunks) == text
    assert all(len(chunk) <= 280 for chunk in chunks)


def test_everyday_question_does_not_receive_absent_slide_warning():
    prompt = build_context_prompt(
        "Du bist Trinity.", "Der Nutzer hat viele Interessen.",
        "Keine aktuelle Folie von der Companion-App verfügbar.", "", "", "Früher ging es um eine Vorlesung.",
        "Wie wird morgen das Wetter?",
    )
    assert "FOLIENKONTEXT" not in prompt
    assert "AKTUELLES VORLESUNGS-TRANSKRIPT" not in prompt
    assert "Unterstelle keinen Vorlesungskontext" in prompt


def test_slide_question_keeps_accurate_vision_status():
    prompt = build_context_prompt(
        "Du bist Trinity.", "Nutzerprofil", "Keine aktuelle Folie von der Companion-App verfügbar.",
        "", "", "", "Was steht auf der Folie?",
    )
    assert "FOLIENKONTEXT" in prompt
    assert "Keine aktuelle Folie" in prompt
