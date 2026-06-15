# Skill: PowerPoint Agent

## Beschreibung
Steuert **Microsoft PowerPoint** nativ per Sprache:

- macOS: AppleScript (`osascript`)
- Windows 11: Microsoft PowerPoint COM Object Model (`pywin32`)

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
- macOS: Systemzugang für `osascript`
- Windows 11: klassische Desktop-Version von Microsoft PowerPoint und `pywin32`

## Abhängigkeiten
- `core/platform_adapters/powerpoint.py`
- macOS: `osascript`
- Windows 11: `pywin32`
- Keine externen APIs nötig
