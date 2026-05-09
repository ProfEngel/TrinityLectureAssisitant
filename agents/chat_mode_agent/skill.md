# Skill: Chat Mode Agent

## Beschreibung
Schaltet Trinity in den **natürlichen Konversationsmodus** (VAD-basiert). In diesem Modus antwortet Trinity automatisch, ohne dass ein Trigger-Wort gesprochen werden muss. Ideal für freie Diskussionen, Brainstorming oder interaktive Q&A-Runden.

## Trigger-Wörter
`lass uns quatschen`, `chat modus`, `gesprächsmodus`, `konversationsmodus`, `quatschen`

## Verhalten
- Trinity wechselt in einen freieren Antwort-Stil
- Kein Trigger-Wort mehr nötig für die Aktivierung
- Rückkehr zum Normal-Modus via: *„Trinity, Vorlesungsmodus"* oder nach Session-Ende

## Beispiel-Sprachbefehle
- *„Trinity, lass uns quatschen"*
- *„Trinity, wechsle in den Chat-Modus"*

## Abhängigkeiten
- Interagiert mit `core/transcriber.py` für die VAD-Einstellungen
- Keine externen APIs nötig
