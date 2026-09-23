"""Conversational, structured Microsoft Word editing and guided saving."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from platform_adapters.microsoft_word import create_word_controller
from trinity_paths import TrinityPaths
from word_control import WordControlService


PRIORITY = 130
ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "TrinityRuntime" / "desktop_control" / "word_dialog.json"

WORD_MARKERS = ("word", "dokument")
NEW_MARKERS = ("neu", "neues", "erstelle", "erzeuge", "anlegen")
WRITE_MARKERS = ("schreibe", "schreib", "füge", "fuege", "tippe")
SAVE_MARKERS = ("speichere", "speichern", "sichern")
CANCEL_MARKERS = ("abbrechen", "abbruch", "vergiss das", "stopp speichern")


def can_handle(query: str) -> bool:
    text = _fold(query)
    if _state():
        return True
    if not any(marker in text for marker in WORD_MARKERS + ("auswahl", "markiert", "absatz")):
        return False
    return bool(_intent(query))


def execute(query: str, context: dict | None = None) -> dict:
    config = (context or {}).get("full_config", {})
    desktop_config = dict(config.get("desktop_control", {}))
    controller = create_word_controller()
    service = WordControlService(desktop_config, controller, ROOT)

    try:
        pending = _state()
        if pending:
            return _answer(_continue_save(query, config, controller, service, pending))

        intent = _intent(query)
        if intent is None:
            return _answer("Ich konnte die gewuenschte Word-Aktion nicht erkennen.")
        action, value = intent

        if action == "new":
            name = service.modify("desktop_type_text", controller.create_document)
            return _answer(f"Ein neues Word-Dokument ist geoeffnet ({name}).")
        if action == "write":
            if not value:
                return _answer("Welchen Text soll ich an der Cursorposition einfuegen?")
            message = service.modify(
                "desktop_type_text", lambda: controller.insert_text(value)
            )
            return _answer(message)
        if action == "format":
            message = service.modify(
                "desktop_format_document", lambda: controller.format_selection(value)
            )
            return _answer(message)
        if action == "rewrite":
            brain = (context or {}).get("brain")
            if brain is None:
                return _answer("Die Textueberarbeitung ist gerade nicht verfuegbar.")
            selected = controller.selection()
            if selected.is_empty:
                return _answer("Bitte markiere zuerst den Absatz in Word.")
            improved = brain.ask_llm(
                [{"role": "user", "content": _rewrite_prompt(selected.text, query)}]
            ).strip()
            if not improved:
                return _answer("Ich habe keinen belastbaren Ueberarbeitungsvorschlag erhalten.")
            service.modify(
                "desktop_replace_selection", lambda: controller.replace_selection(improved)
            )
            return _answer("Ich habe den markierten Absatz sprachlich ueberarbeitet.")
        if action == "save":
            root = _preferred_vault(config)
            if root is None:
                return _answer(
                    "Bitte hinterlege zuerst unter Control Plane einen Cloud-Vault."
                )
            _write_state({"stage": "destination", "root": str(root), "folder": str(root)})
            return _answer(
                f"Wo soll ich das Word-Dokument speichern? Die freigegebene "
                f"Ablage ist {root.name}."
            )
    except (OSError, RuntimeError, ValueError, FileExistsError) as exc:
        return _answer(str(exc))

    return _answer("Die Word-Aktion konnte nicht ausgefuehrt werden.")


def _intent(query: str):
    text = _fold(query)
    if any(marker in text for marker in SAVE_MARKERS) and any(
        marker in text for marker in WORD_MARKERS + ("datei",)
    ):
        return "save", ""
    if any(marker in text for marker in ("besser ausformulieren", "formuliere", "umformulieren", "ueberarbeite", "verbessere den absatz", "verbessere die auswahl")):
        return "rewrite", ""
    formats = (
        (("stichpunkt", "spiegelpunkt", "aufzaehlung", "bullet"), "bullets"),
        (("nummeriert", "nummerierung"), "numbering"),
        (("ueberschrift 1", "heading 1"), "heading1"),
        (("ueberschrift 2", "heading 2"), "heading2"),
        (("untertitel",), "subtitle"),
        (("titel",), "title"),
        (("fett",), "bold"),
        (("kursiv",), "italic"),
        (("normal", "standardformat"), "normal"),
    )
    if any(marker in text for marker in ("auswahl", "markiert", "absatz", "word")):
        for markers, style in formats:
            if any(marker in text for marker in markers):
                return "format", style
    if any(marker in text for marker in WRITE_MARKERS) and any(
        marker in text for marker in WORD_MARKERS
    ):
        return "write", _extract_written_text(query)
    if any(marker in text for marker in NEW_MARKERS) and "word" in text:
        return "new", ""
    return None


def _continue_save(query: str, config: dict, controller, service, state: dict) -> str:
    text = _fold(query)
    if any(marker in text for marker in CANCEL_MARKERS):
        _clear_state()
        return "Das Speichern wurde abgebrochen."

    root = Path(state["root"]).resolve()
    folder = Path(state["folder"]).resolve()
    if state.get("stage") == "destination":
        if _fold(root.name) in text or any(
            marker in text
            for marker in ("brainvault", "cloud-vault", "cloud vault", "freigegebene ablage", "dort")
        ):
            state["stage"] = "folder"
            _write_state(state)
            controller.open_folder(root)
            return _folder_prompt(root)
        return (
            f"Aus Sicherheitsgruenden kann ich aktuell in {root.name} speichern. "
            f"Sage zum Beispiel 'in {root.name}' oder 'abbrechen'."
        )

    if state.get("stage") == "filename":
        filename = _filename(query)
        if not filename:
            return "Bitte nenne einen kurzen Dateinamen."
        target = folder / filename
        try:
            saved = service.save(target, [root])
        except FileExistsError as exc:
            return str(exc)
        _clear_state()
        controller.open_folder(folder)
        return f"Das Word-Dokument wurde als {Path(saved).name} gespeichert."

    if "hier speichern" in text or text in {"hier", "dieser ordner", "in diesem ordner"}:
        state["stage"] = "filename"
        _write_state(state)
        return "Wie soll die Word-Datei heissen?"
    if text in {"zurueck", "einen ordner zurueck", "ordner zurueck"}:
        parent = folder.parent
        try:
            parent.relative_to(root)
            folder = parent
        except ValueError:
            folder = root
        state["folder"] = str(folder)
        _write_state(state)
        controller.open_folder(folder)
        return _folder_prompt(folder)
    if "zeige" in text and "ordner" in text:
        return _folder_prompt(folder)

    match = _match_subfolder(folder, query)
    if match is None:
        return "Diesen Unterordner habe ich hier nicht eindeutig gefunden. " + _folder_prompt(folder)
    state["folder"] = str(match)
    _write_state(state)
    controller.open_folder(match)
    return _folder_prompt(match)


def _folder_prompt(folder: Path) -> str:
    names = [item.name for item in sorted(folder.iterdir(), key=lambda p: p.name.casefold()) if item.is_dir() and not item.name.startswith(".")]
    shown = ", ".join(names[:8]) if names else "keine Unterordner"
    suffix = " ..." if len(names) > 8 else ""
    return (
        f"Finder zeigt jetzt {folder.name}. Unterordner: {shown}{suffix}. "
        "Nenne einen Ordner oder sage 'hier speichern'."
    )


def _match_subfolder(folder: Path, query: str) -> Path | None:
    requested = _fold(query)
    prefixes = ("in den ordner ", "in ordner ", "oeffne ", "in ")
    for prefix in prefixes:
        if requested.startswith(prefix):
            requested = requested[len(prefix):].strip()
            break
    candidates = [item for item in folder.iterdir() if item.is_dir() and not item.name.startswith(".")]
    exact = [item for item in candidates if _fold(item.name) == requested]
    if len(exact) == 1:
        return exact[0]
    contained = [item for item in candidates if requested in _fold(item.name) or _fold(item.name) in requested]
    return contained[0] if len(contained) == 1 else None


def _preferred_vault(config: dict) -> Path | None:
    allowed = [Path(item).expanduser().resolve() for item in config.get("desktop_control", {}).get("allowed_paths", []) if str(item)]
    if allowed:
        return allowed[0]
    paths = TrinityPaths.from_config(ROOT, config)
    return paths.vault_root if paths.vault_root.is_dir() else None


def _extract_written_text(query: str) -> str:
    if ":" in query:
        return query.split(":", 1)[1].strip()
    match = re.search(r"(?:in word|ins word-dokument|im word-dokument)\s+(?:ein|hinein)?\s*(.*)$", query, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _filename(query: str) -> str:
    value = str(query or "").strip().strip('"\' ')
    value = re.sub(r"^(?:nenne|nenn|dateiname|als)\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"[\\/:*?\"<>|]", "-", value).strip(". ")
    if not value or value in {".", ".."}:
        return ""
    if not value.casefold().endswith(".docx"):
        value += ".docx"
    return value[:180]


def _rewrite_prompt(selection: str, request: str) -> str:
    return f"""Ueberarbeite ausschließlich den folgenden markierten Word-Text.
Bewahre Aussage, Fakten, Sprache und Perspektive. Erfinde nichts. Formuliere klarer,
fluessiger und angemessen ausfuehrlich. Antworte nur mit dem Ersatztext, ohne
Erklaerung oder Anfuehrungszeichen.

Auftrag: {request}

Text:
{selection}
"""


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join("".join(char for char in normalized if not unicodedata.combining(char)).split())


def _state() -> dict:
    try:
        value = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) and value.get("stage") else {}
    except (OSError, ValueError, TypeError):
        return {}


def _write_state(value: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True), encoding="utf-8")
    temporary.replace(STATE_PATH)


def _clear_state() -> None:
    STATE_PATH.unlink(missing_ok=True)


def _answer(message: str) -> dict:
    return {
        "has_payload": False,
        "html_payload": "",
        "search_context": "",
        "direct_answer": message,
    }
