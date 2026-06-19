import zipfile

from chat_attachments import (
    attachment_preview_html,
    attachment_kind,
    prepare_attachment_content,
    stage_attachment,
)


def test_supported_attachment_types_are_detected():
    assert attachment_kind("notes.md") == "text"
    assert attachment_kind("paper.pdf") == "pdf"
    assert attachment_kind("diagram.png") == "image"
    assert attachment_kind("archive.zip") is None
    assert attachment_kind("punkte.xlsx") == "spreadsheet"


def test_spreadsheet_attachment_is_added_to_prompt(tmp_path):
    source = tmp_path / "punkte.xlsx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            """<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheets><sheet name=\"Punkte\" sheetId=\"1\"/></sheets></workbook>""",
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            """<sst xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><si><t>Name</t></si><si><t>Person XY</t></si></sst>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetData><row r=\"1\"><c r=\"A1\" t=\"s\"><v>0</v></c><c r=\"B1\"><v>42</v></c></row><row r=\"2\"><c r=\"A2\" t=\"s\"><v>1</v></c><c r=\"B2\"><v>17</v></c></row></sheetData></worksheet>""",
        )

    attachment = stage_attachment(source, tmp_path / "uploads")
    prepared = prepare_attachment_content("Wie viele Punkte?", [attachment])

    assert "Tabelle: Punkte" in prepared["fallback_text"]
    assert "Person XY" in prepared["fallback_text"]
    assert "B: 17" in prepared["fallback_text"]
    assert "Person XY" in attachment_preview_html(attachment["path"], attachment["kind"])


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
