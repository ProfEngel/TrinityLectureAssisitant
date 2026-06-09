# Skill: Mail Agent

## Beschreibung
Steuert die lokale macOS **Mail** App per AppleScript. Der Agent kann Mail öffnen, ungelesene Mails im Posteingang zusammenfassen, im Posteingang nach Absendern oder Betreff suchen und sichere Mail-Entwürfe erstellen.

Wichtig: Der Agent sendet keine Mails automatisch. Er öffnet Entwürfe sichtbar in Apple Mail, damit der Nutzer sie prüfen und selbst absenden kann.

## Trigger-Wörter
`mail`, `mails`, `email`, `e-mail`, `postfach`, `eingang`, `inbox`, `ungelesene`

## Unterstützte Befehle
| Sprachbefehl | Aktion |
|---|---|
| „Trinity, öffne Mail" | Öffnet Apple Mail |
| „Trinity, prüfe meine Mails" | Zeigt ungelesene Mails aus dem Posteingang |
| „Trinity, was ist im Posteingang?" | Zeigt ungelesene Mails aus dem Posteingang |
| „Trinity, suche in Mails nach Prüfungsamt" | Sucht im Posteingang nach Absender oder Betreff |
| „Trinity, schreibe eine Mail an max@example.com: Ich komme später" | Erstellt einen sichtbaren Entwurf |

## Ausgabe
- **html_payload:** Übersicht zu ungelesenen Mails, Suchtreffern oder dem erstellten Entwurf.
- **search_context:** Kurze Bestätigung bzw. Zusammenfassung für Trinitys Antwort.

## Voraussetzungen
- Apple Mail ist auf macOS eingerichtet.
- Trinity bzw. Terminal/Python hat unter macOS die nötigen Automationsrechte für Mail.
- Beim ersten Start kann macOS nach Erlaubnis fragen, dass `osascript` oder Python Mail steuern darf.

## Abhängigkeiten
- `subprocess` für `osascript`
- `core/brain.py` → `ask_llm()` für Suchbegriff- und Entwurfs-Extraktion
