# Skill: Settings Agent

## Beschreibung
Öffnet das grafische **Konfigurations-UI** von Trinity (`core/settings_ui.py`) asynchron als separates Fenster, ohne den laufenden Trinity-Prozess zu blockieren.

## Trigger-Wörter
`öffne einstellungen`, `konfiguration öffnen`, `settings öffnen`, `einstellungen öffnen`, `konfiguration anzeigen`

## Verhalten
- Startet `settings_ui.py` als Sub-Prozess
- Trinity bestätigt kurz, dass das Einstellungsfenster geöffnet wird

## Konfigurierbare Felder (im UI)
- LLM: Lokale URL / Remote URL / Modell / API-Key
- STT: Whisper-Modell (`tiny`, `small`, `medium`)
- APIs: Tavily Key, fal.ai Key
- Persona: Agent-Name

## Beispiel-Sprachbefehle
- *„Trinity, öffne Einstellungen"*
- *„Trinity, Konfiguration anzeigen"*

## Abhängigkeiten
- `core/settings_ui.py`
- `subprocess`, `sys`
