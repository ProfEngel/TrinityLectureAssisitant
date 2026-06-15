from chat_attachments import (
    attachment_kind,
    prepare_attachment_content,
    stage_attachment,
)


def test_supported_attachment_types_are_detected():
    assert attachment_kind("notes.md") == "text"
    assert attachment_kind("paper.pdf") == "pdf"
    assert attachment_kind("diagram.png") == "image"
    assert attachment_kind("archive.zip") is None


def test_text_attachment_is_staged_and_added_to_prompt(tmp_path):
    source = tmp_path / "notes.txt"
    source.write_text("Wichtiger Inhalt", encoding="utf-8")

    attachment = stage_attachment(source, tmp_path / "uploads")
    prepared = prepare_attachment_content("Bitte zusammenfassen.", [attachment])

    assert attachment["path"] != str(source)
    assert "Wichtiger Inhalt" in prepared["fallback_text"]
    assert prepared["primary_image_path"] is None


def test_image_attachment_creates_multimodal_content(tmp_path):
    source = tmp_path / "image.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nsmall-test")
    attachment = stage_attachment(source, tmp_path / "uploads")

    prepared = prepare_attachment_content("Was ist darauf?", [attachment])

    assert isinstance(prepared["content"], list)
    assert prepared["content"][1]["type"] == "image_url"
    assert prepared["content"][1]["image_url"]["url"].startswith(
        "data:image/png;base64,"
    )
    assert prepared["primary_image_path"] == attachment["path"]
