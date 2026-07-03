from answer_sanitizer import clean_visible_answer


def test_clean_visible_answer_strips_thinking_process_with_final_answer():
    raw = """Here's a thinking process:
1. Analyse.
2. Draft.

Final Answer:
Heute wird es heiter und meist trocken.
"""

    assert clean_visible_answer(raw) == "Heute wird es heiter und meist trocken."


def test_clean_visible_answer_extracts_output_generation_quote():
    raw = """Here's a thinking process:
Long internal scratchpad.

[Output Generation] -> "Das Schaubild ist im Nebenfenster sichtbar."
"""

    assert clean_visible_answer(raw) == "Das Schaubild ist im Nebenfenster sichtbar."


def test_clean_visible_answer_handles_curly_thinking_marker():
    raw = "Here’s a thinking process:\nHidden.\n\nAntwort:\nJa, kurz und klar."

    assert clean_visible_answer(raw) == "Ja, kurz und klar."


def test_clean_visible_answer_keeps_normal_answer():
    assert clean_visible_answer("Kurze Antwort.") == "Kurze Antwort."
