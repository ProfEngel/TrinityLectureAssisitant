"""Exact, conservative ownership tracking for a single TextEdit draft."""

from __future__ import annotations

from dataclasses import dataclass


def utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def utf16_slice(text: str, start: int, length: int) -> str:
    raw = text.encode("utf-16-le")
    return raw[start * 2:(start + length) * 2].decode("utf-16-le")


def utf16_replace(text: str, start: int, length: int, replacement: str) -> str:
    raw = text.encode("utf-16-le")
    return (raw[:start * 2] + replacement.encode("utf-16-le") + raw[(start + length) * 2:]).decode("utf-16-le")


@dataclass
class TextEditDraft:
    pid: int
    window_id: int
    document: str
    start: int
    original: str = ""
    summary: str = ""
    revision: str = ""
    field_id: str = ""

    def check(self, snapshot: dict, window_id: int) -> None:
        if int(snapshot["pid"]) != self.pid or window_id != self.window_id:
            raise RuntimeError("TextEdit-Dokument wurde gewechselt.")
        if self.field_id and str(snapshot.get("field_id") or "") != self.field_id:
            raise RuntimeError("Aktives Textfeld wurde gewechselt.")
        if snapshot["text"] != self.document:
            raise RuntimeError("Dokument wurde außerhalb des Trinity-Schreibmodus geändert. Bitte Diktat neu beginnen.")
        if utf16_slice(self.document, self.start, utf16_length(self.original)) != self.original:
            raise RuntimeError("Erfasster Diktatblock stimmt nicht mehr mit dem Dokument überein.")

    @property
    def original_end(self) -> int:
        return self.start + utf16_length(self.original)

    @property
    def summary_end(self) -> int:
        return self.original_end + utf16_length(self.summary)

    @property
    def revision_end(self) -> int:
        return self.summary_end + utf16_length(self.revision)

    def record_dictation(self, text: str) -> tuple[int, int, str]:
        if self.summary or self.revision:
            raise RuntimeError("Nach einer Fassung bitte ein neues Diktat beginnen.")
        start = self.original_end
        self.document = utf16_replace(self.document, start, 0, text)
        self.original += text
        return start, 0, text

    def record_summary(self, text: str) -> tuple[int, int, str]:
        if not self.original.strip():
            raise RuntimeError("Kein neues Diktat zum Zusammenfassen vorhanden.")
        insert = "\n\nZusammenfassung:\n" + text.strip() + "\n"
        start = self.original_end
        length = utf16_length(self.summary)
        self.document = utf16_replace(self.document, start, length, insert)
        self.summary = insert
        return start, length, insert

    def summary_body(self) -> str:
        return self.summary.split("\n", 3)[3].rstrip("\n") if self.summary else ""

    def record_revision(self, text: str) -> tuple[int, int, str]:
        if not self.original.strip():
            raise RuntimeError("Kein neues Diktat zur Überarbeitung vorhanden.")
        insert = "\n\nÜberarbeitung:\n" + text.strip() + "\n"
        start = self.summary_end
        length = utf16_length(self.revision)
        self.document = utf16_replace(self.document, start, length, insert)
        self.revision = insert
        return start, length, insert

    def revision_body(self) -> str:
        if not self.revision:
            raise RuntimeError("Es liegt noch keine Überarbeitung vor.")
        return self.revision.split("\n", 3)[3].rstrip("\n")

    def record_replace_original(self) -> tuple[int, int, str]:
        replacement = self.revision_body()
        length = utf16_length(self.original)
        self.document = utf16_replace(self.document, self.start, length, replacement)
        self.original = replacement
        return self.start, length, replacement

    def record_remove_revision_preview(self) -> tuple[int, int, str]:
        if not self.revision:
            raise RuntimeError("Keine Überarbeitungsvorschau vorhanden.")
        start = self.summary_end
        length = utf16_length(self.revision)
        self.document = utf16_replace(self.document, start, length, "")
        self.revision = ""
        return start, length, ""

    def record_delete_original(self) -> tuple[int, int, str]:
        if not self.summary:
            raise RuntimeError("Ohne vorhandene Zusammenfassung wird der Gedankenblock nicht gelöscht.")
        length = utf16_length(self.original)
        if not length:
            raise RuntimeError("Der Gedankenblock ist bereits leer.")
        self.document = utf16_replace(self.document, self.start, length, "")
        self.original = ""
        return self.start, length, ""
