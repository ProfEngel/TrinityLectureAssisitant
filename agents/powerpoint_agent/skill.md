# Skill: PowerPoint Agent

## Beschreibung
Steuert **Microsoft PowerPoint** nativ auf macOS via AppleScript (`osascript`). Ermöglicht die vollständige Hands-free-Kontrolle der Präsentation per Sprache.

## Trigger-Wörter
`nächste folie`, `nächstes bild`, `weiter`, `vorherige folie`, `zurück`, `präsentation starten`, `präsentation beenden`

## Unterstützte Befehle
| Sprachbefehl | Aktion |
|---|---|
| „nächste Folie" / „weiter" | Nächste Folie (Go Forward) |
| „vorherige Folie" / „zurück" | Vorherige Folie (Go Back) |
| „Präsentation starten" | Startet die Diashow |
| „Präsentation beenden" | Beendet die Diashow |

## Voraussetzungen
- Microsoft PowerPoint muss installiert und offen sein
- macOS Systemzugang für `osascript`

## Abhängigkeiten
- `os`, `subprocess` (AppleScript-Ausführung)
- Keine externen APIs nötig
