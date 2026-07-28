"""Prepare presentation media for semantic inspection by a vision-capable model."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree


RASTER_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".webp"}
IMAGE_SUFFIXES = RASTER_SUFFIXES | {".svg"}
MAX_VISION_ATTACHMENTS = 80
DRAWINGML_TEXT = "{http://schemas.openxmlformats.org/drawingml/2006/main}t"
DRAWINGML_BLIP = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
REL_EMBED = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
REL_ID = "Id"
REL_TARGET = "Target"


def prepare_visual_context(preserved: list[dict], output_path: Path) -> dict:
    """Extract inspectable visuals and write a stable vision inventory.

    The function never changes the original files in ``reference-material``.
    PPTX media is extracted with slide associations. PDF pages are rendered
    when PyMuPDF is installed. The selected harness receives the resulting
    raster files as actual image attachments.
    """

    vision_root = output_path / "reference-material" / "visual-analysis"
    extracted_root = vision_root / "extracted"
    extracted_root.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    slide_text: list[dict] = []
    warnings: list[str] = []

    for preserved_item in preserved:
        source = Path(preserved_item["path"]).resolve()
        suffix = source.suffix.casefold()
        if suffix in IMAGE_SUFFIXES:
            entries.append(
                _entry(
                    source=source,
                    inspect_path=source,
                    origin="standalone-image",
                    location="eigenständige Bildanlage",
                )
            )
        elif suffix == ".pptx":
            try:
                pptx_entries, pptx_text = _extract_pptx(
                    source, extracted_root / _safe_stem(source)
                )
                entries.extend(pptx_entries)
                slide_text.extend(pptx_text)
            except (OSError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
                warnings.append(
                    f"{source.name}: PPTX-Inhalte konnten nicht extrahiert werden ({exc})."
                )
        elif suffix == ".pdf":
            try:
                pdf_entries, pdf_text = _render_pdf(
                    source, extracted_root / _safe_stem(source)
                )
                entries.extend(pdf_entries)
                slide_text.extend(pdf_text)
            except (ImportError, OSError, RuntimeError, ValueError) as exc:
                warnings.append(
                    f"{source.name}: PDF-Seiten konnten nicht gerendert werden ({exc})."
                )

    for index, item in enumerate(entries, start=1):
        item["id"] = f"V{index:03d}"
        item["analysis_status"] = "pending-vision-model"

    vision_attachments = [
        Path(item["inspect_path"])
        for item in entries
        if Path(item["inspect_path"]).suffix.casefold() in RASTER_SUFFIXES
    ]
    if len(vision_attachments) > MAX_VISION_ATTACHMENTS:
        warnings.append(
            "Es sind mehr als "
            f"{MAX_VISION_ATTACHMENTS} Bildansichten vorhanden. "
            "Der erste Modelllauf erhält die ersten Ansichten; alle übrigen "
            "bleiben im Inventar und müssen in einem Folgelauf geprüft werden."
        )
        vision_attachments = vision_attachments[:MAX_VISION_ATTACHMENTS]

    inventory = {
        "schema_version": 1,
        "purpose": (
            "Verbindliche Eingangsliste für den Vision-Adapter. Semantische "
            "Beschreibungen dürfen nur nach tatsächlicher Bildinspektion ergänzt werden."
        ),
        "items": entries,
        "warnings": warnings,
    }
    inventory_path = vision_root / "visual-inventory.json"
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    overview_path = vision_root / "visual-inventory.md"
    overview_path.write_text(
        _inventory_markdown(entries, warnings),
        encoding="utf-8",
    )
    content_path = vision_root / "source-deck-content.md"
    content_path.write_text(
        _source_content_markdown(slide_text),
        encoding="utf-8",
    )
    return {
        "inventory_path": inventory_path,
        "overview_path": overview_path,
        "content_path": content_path,
        "attachments": vision_attachments,
        "item_count": len(entries),
        "warnings": warnings,
    }


def _extract_pptx(source: Path, target_root: Path) -> tuple[list[dict], list[dict]]:
    target_root.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    slide_text: list[dict] = []
    with zipfile.ZipFile(source) as archive:
        slide_names = sorted(
            (
                name
                for name in archive.namelist()
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
            ),
            key=lambda name: int(re.search(r"(\d+)", Path(name).stem).group(1)),
        )
        for slide_name in slide_names:
            slide_number = int(re.search(r"(\d+)", Path(slide_name).stem).group(1))
            root = ElementTree.fromstring(archive.read(slide_name))
            texts = [
                (node.text or "").strip()
                for node in root.iter(DRAWINGML_TEXT)
                if (node.text or "").strip()
            ]
            rel_name = (
                PurePosixPath(slide_name).parent
                / "_rels"
                / f"{PurePosixPath(slide_name).name}.rels"
            ).as_posix()
            relationships = {}
            if rel_name in archive.namelist():
                rel_root = ElementTree.fromstring(archive.read(rel_name))
                for relationship in rel_root:
                    relationships[relationship.attrib.get(REL_ID, "")] = (
                        relationship.attrib.get(REL_TARGET, "")
                    )
            slide_images = []
            for image_index, blip in enumerate(root.iter(DRAWINGML_BLIP), start=1):
                target = relationships.get(blip.attrib.get(REL_EMBED, ""))
                if not target:
                    continue
                member = _resolve_pptx_target(slide_name, target)
                if member not in archive.namelist() or not member.startswith("ppt/media/"):
                    continue
                suffix = Path(member).suffix.casefold() or ".bin"
                target_name = (
                    f"slide-{slide_number:03d}-image-{image_index:03d}{suffix}"
                )
                extracted = target_root / target_name
                extracted.write_bytes(archive.read(member))
                slide_images.append(str(extracted))
                entries.append(
                    _entry(
                        source=source,
                        inspect_path=extracted,
                        origin="pptx-embedded-image",
                        location=f"Ausgangsfolie {slide_number}",
                        source_member=member,
                    )
                )
            slide_text.append(
                {
                    "source": source.name,
                    "position": slide_number,
                    "text": texts,
                    "images": slide_images,
                }
            )
    return entries, slide_text


def _render_pdf(source: Path, target_root: Path) -> tuple[list[dict], list[dict]]:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise ImportError("PyMuPDF ist nicht installiert") from exc

    target_root.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    page_text: list[dict] = []
    try:
        document = fitz.open(source)
    except Exception as exc:  # PyMuPDF uses several private exception classes.
        raise RuntimeError(str(exc)) from exc
    try:
        for page_index, page in enumerate(document, start=1):
            target = target_root / f"page-{page_index:03d}.png"
            page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False).save(target)
            entries.append(
                _entry(
                    source=source,
                    inspect_path=target,
                    origin="pdf-page-preview",
                    location=f"Ausgangsseite {page_index}",
                )
            )
            page_text.append(
                {
                    "source": source.name,
                    "position": page_index,
                    "text": [page.get_text("text").strip()],
                    "images": [str(target)],
                }
            )
    finally:
        document.close()
    return entries, page_text


def _entry(
    *,
    source: Path,
    inspect_path: Path,
    origin: str,
    location: str,
    source_member: str = "",
) -> dict:
    return {
        "source_file": source.name,
        "source_path": str(source),
        "origin": origin,
        "location": location,
        "source_member": source_member,
        "inspect_path": str(inspect_path),
        "sha256": hashlib.sha256(inspect_path.read_bytes()).hexdigest(),
        "semantic_description": None,
        "relevant_content": None,
        "recommended_slide_ids": [],
        "reuse_decision": None,
    }


def _resolve_pptx_target(slide_name: str, target: str) -> str:
    base = PurePosixPath(slide_name).parent
    parts: list[str] = []
    for part in (base / target).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return PurePosixPath(*parts).as_posix()


def _safe_stem(path: Path) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip("-._")
    return clean or "presentation"


def _inventory_markdown(entries: list[dict], warnings: list[str]) -> str:
    lines = [
        "# Visuelles Eingangsinventar",
        "",
        "Diese Liste beschreibt nur Herkunft und Position. Die inhaltliche "
        "Bedeutung muss ein Vision-Modell durch tatsächliches Öffnen jedes "
        "Bildes bestimmen und in `visual-analysis.md` dokumentieren.",
        "",
    ]
    for item in entries:
        lines.extend(
            [
                f"## {item['id']} · {item['location']}",
                "",
                f"- Quelle: `{item['source_file']}`",
                f"- Ansicht: `{item['inspect_path']}`",
                f"- Typ: `{item['origin']}`",
                "- Status: noch nicht visuell analysiert",
                "",
            ]
        )
    if warnings:
        lines.extend(["## Technische Hinweise", ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    return "\n".join(lines)


def _source_content_markdown(slides: list[dict]) -> str:
    lines = [
        "# Extrahierter Text und Medienbezug der Ausgangspräsentation",
        "",
        "Diese Datei ergänzt die visuelle Inspektion; sie ersetzt sie nicht.",
        "",
    ]
    for slide in slides:
        lines.extend(
            [
                f"## {slide['source']} · Position {slide['position']}",
                "",
                "Text:",
                "",
            ]
        )
        lines.extend(f"- {text}" for text in slide["text"] if text)
        if not any(slide["text"]):
            lines.append("- (kein extrahierbarer Text)")
        lines.extend(["", "Zugeordnete Ansichten:", ""])
        lines.extend(f"- `{path}`" for path in slide["images"])
        if not slide["images"]:
            lines.append("- (keine extrahierbare Ansicht)")
        lines.append("")
    return "\n".join(lines)
