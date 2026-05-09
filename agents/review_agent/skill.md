# Skill: Review Agent

## Beschreibung
Liest die **Zusammenfassung der letzten Session** vor. Ideal zum Einstieg in eine neue Vorlesung, um den Anknüpfungspunkt zur letzten Stunde herzustellen.

## Trigger-Wörter
`review`, `letzte sitzung`, `letzte vorlesung`, `zusammenfassung der letzten`

## Verhalten
- Lädt die aktuellste Zusammenfassung aus `memory/`
- Zeigt einen Review-Header im Content-Fenster (`KEEP_OPEN`)
- Liest den Inhalt per TTS vor

## Beispiel-Sprachbefehle
- *„Trinity, Zusammenfassung der letzten Vorlesung"*
- *„Trinity, kurzes Review"*

## Abhängigkeiten
- `memory/` → Ablageort der Session-Summaries
- `session_summarizer_agent` → Erstellt die Summaries
