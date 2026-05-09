# Skill: WebSearch Agent

## Beschreibung
Führt Echtzeit-Webrecherchen via **Tavily API** durch. Der Agent extrahiert die eigentliche Suchanfrage aus dem gesprochenen Satz (LLM-Parsing) und liefert die Ergebnisse als strukturierten HTML-Payload ans UI.

## Trigger-Wörter
`recherchier`, `such `, `suche `, `finde heraus`, `nächste spiel`, `spielplan`, `nachricht`, `online`

## Voraussetzungen
- Tavily API-Key in `core/config.json` unter `apis.tavily`
- Ohne Key: freundlicher Hinweis auf die Einstellungen

## Ausgabe
- **search_context:** Für das LLM aufbereitetes Ergebnis mit Datum und Quellen
- **html_payload:** Klickbare Link-Karten im Content-Fenster

## Beispiel-Sprachbefehle
- *„Trinity, recherchiere die aktuellen KI-News"*
- *„Trinity, finde heraus wann das nächste Spiel von Bayern ist"*

## Abhängigkeiten
- `requests` (HTTP)
- `core/brain.py` → `ask_llm()` für Query-Extraktion
