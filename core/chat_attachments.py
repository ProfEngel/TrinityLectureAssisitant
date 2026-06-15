"""Attachment staging and LLM context preparation for Trinity chat."""

import base64
import mimetypes
import shutil
import uuid
from pathlib import Path


TEXT_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
    ".log",
    ".py",
    ".js",
    ".html",
    ".css",
}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_TEXT_CHARS_PER_FILE = 24_000
MAX_TOTAL_TEXT_CHARS = 60_000
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def attachment_kind(path):
    suffix = Path(path).suffix.casefold()
    if suffix == ".pdf":
        return "pdf"
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in TEXT_SUFFIXES:
        return "text"
    return None


def stage_attachment(source_path, upload_dir):
    source = Path(source_path).expanduser().resolve()
    kind = attachment_kind(source)
    if not source.is_file() or kind is None:
        raise ValueError(f"Nicht unterstützte Anlage: {source.name}")

    target_dir = Path(upload_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{uuid.uuid4().hex}_{source.name}"
    shutil.copy2(source, target)
    mime, _ = mimetypes.guess_type(source.name)
    return {
        "name": source.name,
        "path": str(target),
        "kind": kind,
        "mime": mime or "application/octet-stream",
        "size": target.stat().st_size,
    }


def _read_text(path):
    return path.read_text(encoding="utf-8", errors="replace")


def _read_pdf(path):
    import fitz

    pages = []
    with fitz.open(path) as document:
        for index, page in enumerate(document):
            text = page.get_text().strip()
            if text:
                pages.append(f"[Seite {index + 1}]\n{text}")
    return "\n\n".join(pages)


def _image_data_url(path, mime):
    data = path.read_bytes()
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(
            f"{path.name} ist größer als {MAX_IMAGE_BYTES // (1024 * 1024)} MB."
        )
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def prepare_attachment_content(user_query, attachments):
    text_sections = []
    image_parts = []
    image_paths = []
    remaining = MAX_TOTAL_TEXT_CHARS

    for item in attachments or []:
        path = Path(str(item.get("path", ""))).expanduser()
        kind = item.get("kind") or attachment_kind(path)
        name = item.get("name") or path.name
        if not path.is_file():
            text_sections.append(f"Anlage `{name}` ist nicht mehr verfügbar.")
            continue

        if kind in {"text", "pdf"} and remaining > 0:
            try:
                content = _read_pdf(path) if kind == "pdf" else _read_text(path)
            except Exception as exc:
                text_sections.append(f"Anlage `{name}` konnte nicht gelesen werden: {exc}")
                continue
            excerpt = content[: min(MAX_TEXT_CHARS_PER_FILE, remaining)]
            remaining -= len(excerpt)
            suffix = "\n[Inhalt gekürzt]" if len(content) > len(excerpt) else ""
            text_sections.append(f"--- Anlage: {name} ---\n{excerpt}{suffix}")
        elif kind == "image":
            mime = item.get("mime") or mimetypes.guess_type(path.name)[0]
            mime = mime or "image/png"
            try:
                image_parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": _image_data_url(path, mime)},
                    }
                )
                image_paths.append(str(path))
            except (OSError, ValueError) as exc:
                text_sections.append(f"Bild `{name}` konnte nicht angehängt werden: {exc}")

    combined_text = user_query.strip()
    if text_sections:
        combined_text += "\n\n" + "\n\n".join(text_sections)
    if image_paths:
        combined_text += (
            "\n\nDie hochgeladenen Bilder gehören zu dieser Anfrage. "
            "Analysiere sie, sofern das aktive Modell Bildeingaben unterstützt."
        )

    if image_parts:
        content = [{"type": "text", "text": combined_text}, *image_parts]
    else:
        content = combined_text
    return {
        "content": content,
        "fallback_text": combined_text,
        "primary_image_path": image_paths[0] if image_paths else None,
    }
