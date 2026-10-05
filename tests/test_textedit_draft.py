import pytest

from core.textedit_draft import TextEditDraft, utf16_length, utf16_slice


def snapshot(draft):
    return {"pid": draft.pid, "text": draft.document}


def test_summary_revision_accept_and_delete_only_owned_text():
    draft = TextEditDraft(pid=42, window_id=9, document="Titel\n\nEnde", start=utf16_length("Titel\n"))
    draft.check(snapshot(draft), 9)
    draft.record_dictation("Gedanken 🧠. ")
    assert utf16_slice(draft.document, draft.start, utf16_length(draft.original)) == "Gedanken 🧠. "
    draft.record_summary("Kurze Fassung.")
    assert "Zusammenfassung:\nKurze Fassung." in draft.document
    draft.record_revision("Bessere Fassung.")
    assert draft.revision_body() == "Bessere Fassung."
    draft.check(snapshot(draft), 9)
    draft.record_replace_original()
    draft.record_remove_revision_preview()
    assert "Gedanken" not in draft.document
    assert "Bessere Fassung." in draft.document
    assert "Überarbeitung" not in draft.document
    draft.record_delete_original()
    assert "Bessere Fassung." not in draft.document
    assert "Kurze Fassung." in draft.document
    assert draft.document.endswith("Ende")


def test_external_edit_or_other_window_blocks_destructive_actions():
    draft = TextEditDraft(pid=42, window_id=9, document="Alter Text", start=0)
    draft.record_dictation("Eigener Satz.")
    draft.record_summary("Kurz.")
    with pytest.raises(RuntimeError, match="außerhalb"):
        draft.check({"pid": 42, "text": draft.document + "!"}, 9)
    with pytest.raises(RuntimeError, match="gewechselt"):
        draft.check(snapshot(draft), 10)


def test_delete_without_summary_is_rejected():
    draft = TextEditDraft(pid=42, window_id=9, document="", start=0)
    draft.record_dictation("Gedanken")
    with pytest.raises(RuntimeError, match="Zusammenfassung"):
        draft.record_delete_original()


def test_iterative_revision_replaces_only_preview_and_keeps_original():
    draft = TextEditDraft(pid=42, window_id=9, document="Original. Ende.", start=0, original="Original.")
    draft.record_revision("Erster Vorschlag.")
    start, length, replacement = draft.record_revision("• Neuer Vorschlag.")
    assert length > 0 and start == draft.summary_end
    assert draft.original == "Original."
    assert "Erster Vorschlag" not in draft.document
    assert "• Neuer Vorschlag." in draft.document
    assert draft.document.endswith(" Ende.")


def test_identical_text_in_another_field_is_not_the_owned_draft():
    draft = TextEditDraft(pid=42, window_id=9, document="Text", start=0, original="Text", field_id="one")
    with pytest.raises(RuntimeError, match="Textfeld"):
        draft.check({"pid": 42, "text": "Text", "field_id": "two"}, 9)
