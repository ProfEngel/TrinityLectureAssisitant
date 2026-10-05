"""Small, deterministic vocabulary for hands-free TextEdit writing.

Only explicit whole-utterance commands are recognized. In dictation mode every
other utterance is document text, not an instruction for the language model.
"""

from __future__ import annotations

import re
import unicodedata


HELP_TEXT = (
    "Diktat starten oder Trinity, ich diktiere jetzt – beginnt ein Diktat an der Cursorposition.\n"
    "Diktat beenden oder Diktat Ende – beendet das Diktat; Trinity, stopp geht ebenfalls.\n"
    "Trinity, aktives Fenster erfassen – erlaubt Fensterbilder bei Bildschirmfragen.\n"
    "Trinity, Fenstererfassung ausschalten – schaltet diese Bilderfassung aus.\n"
    "Trinity, einfügen – setzt meine letzte Antwort an der Cursorposition ein.\n"
    "Trinity, fasse das Diktat zusammen – schreibt eine Zusammenfassung darunter.\n"
    "Trinity, überarbeite das Diktat – schreibt einen Vorschlag darunter.\n"
    "Trinity, übernimm die neue Fassung – ersetzt den erfassten Diktatblock nach Prüfung.\n"
    "Trinity, lösche unsere Gedanken – fragt vor dem Entfernen des erfassten Blocks nach.\n"
    "Trinity, Bearbeitung abschließen – gibt den erfassten Block frei, ohne Text zu ändern.\n"
    "Trinity, was kannst du hier beim Schreiben tun – liest diese Befehle vor.\n"
    "Trinity, zeig mir die Schreibbefehle – zeigt die Liste kurz auf dem Mac.\n"
    "Trinity, ändere den Text: … – passt den Vorschlag nach deinem Wunsch an.\n"
    "Trinity, schreibe unsere Gedanken zum Thema … – schreibt Gesprächsnotizen an die Cursorposition.\n"
    "Trinity, schreibe die Schreibbefehle hier hinein – fügt diese Liste im aktiven Textfeld ein."
)

SPOKEN_HELP = (
    "In zugänglichen Textfeldern kann ich auf Zuruf diktieren und meine letzte Antwort einsetzen. "
    "Sage: Diktat starten. Zum Schluss: Diktat beenden oder Diktat Ende. Das geht ohne Wakeword. "
    "Mit Trinity, einfügen, setze ich meine letzte Antwort ein. "
    "Mit Trinity, aktives Fenster erfassen, erlaubst du Bildschirmfragen; "
    "Trinity, Fenstererfassung ausschalten, schaltet diese Funktion aus. "
    "Ich kann das Diktat zusammenfassen oder überarbeiten und die neue Fassung "
    "nach deiner Freigabe übernehmen. Löschen bestätigst du ebenfalls per Sprache. "
    "Wenn du die Befehle im Dokument haben möchtest, sage: "
    "Trinity, schreibe die Schreibbefehle hier hinein."
)


def _normalize(text: str) -> str:
    plain = unicodedata.normalize("NFKD", str(text or "").casefold())
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    plain = plain.replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", " ", plain).strip()


def unclear_dictation_request(text):
    """Short, damaged start intents must get clarification, never an LLM ACK."""
    text = _normalize(text)
    return len(text.split()) <= 9 and bool(re.search(r"\b(?:diktiere|diktier) jetzt$", text))


def revision_instruction(text):
    """An explicit parameterized edit, scoped to the owned/selected text only."""
    match = re.match(
        r"^\s*(?:trinity|triniti|drinity|drinit[äa]|trinita|trinidi|tinity|drinete)[\s,.:]+"
        r"((?:ändere|aendere|passe|überarbeite|ueberarbeite|formatiere|formuliere)\s+(?:den|diesen|die|das)\s+.+)$",
        str(text).strip(), re.I,
    )
    return match.group(1).strip() if match and len(match.group(1)) <= 1200 else ""


def notes_topic(text):
    match = re.match(r"^\s*trinity[\s,.:]+(?:schreibe|schreib)\s+(?:unsere gedanken|unser gesp[räa]ch|gespr[aä]chsnotizen)\s+(?:zum thema|über|zu)\s+(.+)$",
                     str(text).strip(), re.I)
    return match.group(1).strip() if match and len(match.group(1)) <= 300 else ""


def command_for(text: str, *, dictating: bool = False) -> str | None:
    """Return a command only for an unmistakable, complete utterance."""
    normalized = _normalize(text)
    if not normalized:
        return None
    if notes_topic(text):
        return "write_notes"
    if revision_instruction(text):
        return "revise"
    wake = r"(?:trinity|triniti|trinitie|trinitys|drinity|drinita|trinita|trinidi|tinity|drinete)"
    suffix = re.search(r"\s+" + wake + r"$", normalized)
    has_wakeword = bool(suffix)
    if suffix:
        normalized = normalized[:suffix.start()]
    prefix = re.match(r"^" + wake + r"\s+", normalized)
    if prefix:
        normalized = normalized[prefix.end():]
        has_wakeword = True
    # Strip only known modifiers, never arbitrary dictated prose.
    normalized = re.sub(r"^(?:bitte )|(?: bitte)$", "", normalized)
    normalized = re.sub(r" (?:ich habe (?:es|den text) markiert)$", "", normalized)
    edit = None
    if normalized in {"fasse das diktat zusammen", "fass das diktat zusammen",
                      "kannst du das zusammenfassen", "fasse das zusammen",
                      "fasse den markierten text zusammen"}:
        edit = "summarize"
    elif normalized in {"uberarbeite das diktat", "uberarbeite meinen text",
                        "lass uns das besser uberarbeiten", "lass uns den text uberarbeiten",
                        "formuliere das besser", "formuliere den text besser", "schreibe das besser",
                        "uberarbeite den markierten text"}:
        edit = "revise"
    stop = normalized in {"diktat beenden", "diktat ende", "diktat stoppen"} or (has_wakeword and normalized in {
        "diktat beenden", "beende das diktat", "diktieren beenden", "diktat beendet",
        "stopp", "stop", "abbrechen",
    })
    if stop:
        return "dictation_stop"
    if normalized in {"diktat starten", "starte diktat"} or (
            has_wakeword and normalized in {"ich diktiere jetzt", "ich ich diktiere jetzt"}):
        return "dictation_start"
    if has_wakeword and normalized in {
        "aktives fenster erfassen", "fenstererfassung einschalten", "fenster erfassen",
    }:
        return "window_capture_on"
    if has_wakeword and normalized in {
        "fenstererfassung ausschalten", "fenstererfassung stoppen", "fenster nicht mehr erfassen",
        "aktives fenster nicht mehr erfassen",
    }:
        return "window_capture_off"
    if dictating:
        if has_wakeword and edit:
            return edit
        # Ordinary dictated prose must never turn into an edit command.
        return "dictation_stop" if re.search(
            r"\btrinity (?:diktat beenden|diktat beendet|stopp|stop|abbrechen)$", normalized
        ) else None
    if has_wakeword and normalized.startswith("diktat "):
        # A truncated control command must not become a fictional LLM action.
        return "dictation_invalid"
    if normalized in {"einfugen", "fuge das ein", "letzte antwort einfugen"}:
        return "insert_last"
    if edit:
        return edit
    if normalized in {
        "ubernimm die neue fassung", "ubernehme die neue fassung",
        "ja das klingt viel besser",
    }:
        return "accept_revision"
    if has_wakeword and normalized in {"losche unsere gedanken", "losche den gedankenblock"}:
        return "delete_thoughts"
    if has_wakeword and normalized in {"ja gedankenblock loschen", "ja losche den gedankenblock"}:
        return "confirm_delete_thoughts"
    if has_wakeword and normalized in {"bearbeitung abschliessen", "schreibarbeit abschliessen"}:
        return "close_draft"
    if normalized in {
        "was kannst du hier tun um mir beim schreiben zu helfen",
        "was kannst du hier beim schreiben tun",
        "welche schreibbefehle kennst du",
        "hilf mir beim schreiben",
    } and has_wakeword:
        return "help"
    if normalized in {"zeig mir die schreibbefehle", "zeige mir die schreibbefehle"} and has_wakeword:
        return "show_help"
    if normalized in {
        "schreibe die schreibbefehle hier hinein",
        "schreib die schreibbefehle hier hinein",
        "fuge die schreibbefehle hier ein",
    } and has_wakeword:
        return "help_insert"
    return None
