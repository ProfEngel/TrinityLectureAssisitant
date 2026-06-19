"""Attachment staging and LLM context preparation for Trinity chat."""

import base64
import html
import mimetypes
import shutil
import uuid
import xml.etree.ElementTree as ET
import zipfile
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
SPREADSHEET_SUFFIXES = {".xlsx", ".xlsm"}
MAX_TEXT_CHARS_PER_FILE = 24_000
MAX_TOTAL_TEXT_CHARS = 60_000
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def attachment_kind(path):
    suffix = Path(path).suffix.casefold()
    if suffix == ".pdf":
        return "pdf"
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in SPREADSHEET_SUFFIXES:
        return "spreadsheet"
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


def _xlsx_column_name(index):
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name or "A"


def _xlsx_shared_strings(archive):
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    values = []
    for item in root.findall("x:si", namespace):
        values.append("".join(node.text or "" for node in item.iterfind(".//x:t", namespace)))
    return values


def _read_spreadsheet(path, max_rows=240, max_columns=24):
    """Read simple Office Open XML workbooks without making pandas mandatory."""
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        shared_strings = _xlsx_shared_strings(archive)
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = []
        for index, sheet in enumerate(workbook.findall("x:sheets/x:sheet", namespace), start=1):
            name = sheet.attrib.get("name") or f"Tabelle {index}"
            sheet_path = f"xl/worksheets/sheet{index}.xml"
            try:
                root = ET.fromstring(archive.read(sheet_path))
            except KeyError:
                continue
            rows = []
            for row in root.findall("x:sheetData/x:row", namespace)[:max_rows]:
                values = {}
                for cell in row.findall("x:c", namespace):
                    reference = cell.attrib.get("r", "A1")
                    column = "".join(character for character in reference if character.isalpha()) or "A"
                    if len(values) >= max_columns:
                        break
                    value_node = cell.find("x:v", namespace)
                    raw_value = value_node.text if value_node is not None else ""
                    if cell.attrib.get("t") == "s" and raw_value.isdigit():
                        number = int(raw_value)
                        raw_value = shared_strings[number] if number < len(shared_strings) else raw_value
                    elif cell.attrib.get("t") == "inlineStr":
                        raw_value = "".join(
                            node.text or "" for node in cell.findall(".//x:t", namespace)
                        )
                    values[column] = raw_value or ""
                if values:
                    rows.append(values)
            sheets.append({"name": name, "rows": rows})
    return sheets


def _spreadsheet_text(path):
    sections = []
    for sheet in _read_spreadsheet(path):
        rows = sheet["rows"]
        if not rows:
            continue
        columns = sorted({column for row in rows for column in row})
        sections.append(f"--- Tabelle: {sheet['name']} ---")
        for row in rows:
            sections.append(" | ".join(f"{column}: {row.get(column, '')}" for column in columns))
    return "\n".join(sections)


def spreadsheet_preview_html(path, max_rows=80, max_columns=14):
    """Return a compact HTML preview for the desktop workspace and WebUI."""
    sheets = _read_spreadsheet(path, max_rows=max_rows, max_columns=max_columns)
    blocks = []
    for sheet in sheets:
        rows = sheet["rows"]
        columns = sorted({column for row in rows for column in row})
        header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
        body = "".join(
            "<tr>" + "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns) + "</tr>"
            for row in rows
        )
        blocks.append(
            f"<section><h2>{html.escape(sheet['name'])}</h2>"
            f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></section>"
        )
    return (
        "<html><head><meta charset='utf-8'><style>"
        "body{font-family:system-ui,sans-serif;background:#10151d;color:#e8edf4;padding:24px;}"
        "h1{margin-top:0;}h2{color:#66c7ff;margin-top:26px;}table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #334155;padding:7px;text-align:left;vertical-align:top;}"
        "th{background:#182230;position:sticky;top:0;}tr:nth-child(even){background:#15202d;}"
        "</style></head><body>"
        f"<h1>{html.escape(Path(path).name)}</h1>{''.join(blocks) or '<p>Keine lesbaren Tabellenzeilen gefunden.</p>'}"
        "</body></html>"
    )


def attachment_preview_html(path, kind=None, max_chars=18_000):
    """Render a safe text preview when the native desktop application owns the file."""
    path = Path(path)
    kind = kind or attachment_kind(path)
    try:
        if kind == "spreadsheet":
            return spreadsheet_preview_html(path)
        if kind == "pdf":
            content = _read_pdf(path)
        else:
            content = _read_text(path)
    except Exception as exc:
        content = f"Vorschau konnte nicht erstellt werden: {exc}"
    excerpt = content[:max_chars]
    suffix = "\n\n[Weitere Inhalte in der Originaldatei.]" if len(content) > len(excerpt) else ""
    return (
        "<html><head><meta charset='utf-8'><style>"
        "body{font-family:system-ui,sans-serif;background:#10151d;color:#e8edf4;padding:24px;}"
        "h1{margin-top:0;color:#66c7ff}pre{white-space:pre-wrap;line-height:1.45}"
        "</style></head><body>"
        f"<h1>{html.escape(path.name)}</h1><pre>{html.escape(excerpt + suffix)}</pre>"
        "</body></html>"
    )


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

        if kind in {"text", "pdf", "spreadsheet"} and remaining > 0:
            try:
                if kind == "pdf":
                    content = _read_pdf(path)
                elif kind == "spreadsheet":
                    content = _spreadsheet_text(path)
                else:
                    content = _read_text(path)
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
