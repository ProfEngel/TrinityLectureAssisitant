import json
import zipfile
from pathlib import Path

from presentation_vision import prepare_visual_context


SLIDE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld><p:spTree>
    <p:sp><p:txBody><a:p><a:r><a:t>Kernaussage der Folie</a:t></a:r></a:p></p:txBody></p:sp>
    <p:pic><p:blipFill><a:blip r:embed="rId2"/></p:blipFill></p:pic>
  </p:spTree></p:cSld>
</p:sld>
"""
RELS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId2"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
    Target="../media/image1.png"/>
</Relationships>
"""


def test_visual_adapter_extracts_pptx_images_with_slide_association(tmp_path):
    source = tmp_path / "Alte Präsentation.pptx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("ppt/slides/slide1.xml", SLIDE_XML)
        archive.writestr("ppt/slides/_rels/slide1.xml.rels", RELS_XML)
        archive.writestr("ppt/media/image1.png", b"\x89PNG\r\n\x1a\nreference")
    output = tmp_path / "Neue Präsentation"
    output.mkdir()

    result = prepare_visual_context(
        [{"name": source.name, "path": source, "sha256": "test"}],
        output,
    )

    assert result["item_count"] == 1
    assert result["attachments"][0].name == "slide-001-image-001.png"
    inventory = json.loads(result["inventory_path"].read_text(encoding="utf-8"))
    assert inventory["items"][0]["id"] == "V001"
    assert inventory["items"][0]["location"] == "Ausgangsfolie 1"
    assert inventory["items"][0]["semantic_description"] is None
    content = result["content_path"].read_text(encoding="utf-8")
    assert "Kernaussage der Folie" in content


def test_visual_adapter_keeps_standalone_image_as_real_model_attachment(tmp_path):
    image = tmp_path / "schaubild.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nstandalone")
    output = tmp_path / "Deck"
    output.mkdir()

    result = prepare_visual_context(
        [{"name": image.name, "path": image, "sha256": "test"}],
        output,
    )

    assert result["attachments"] == [image.resolve()]
    assert "tatsächliches Öffnen" in result["overview_path"].read_text(encoding="utf-8")
