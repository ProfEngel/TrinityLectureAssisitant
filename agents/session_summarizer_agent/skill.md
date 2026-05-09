# Skill: Session Summarizer Agent

## Beschreibung
**Post-Processing Skill** – wird nach Ende einer Vorlesung ausgeführt. Liest das vollständige Transkript aus `memory/`, erstellt eine strukturierte Markdown-Zusammenfassung und speichert sie für den Review-Agent.

## Auslösung
- Trigger per Sprachbefehl: *„Trinity, Session beenden und zusammenfassen"*
- Oder automatisch via `trinity_launcher.py` nach Transkript-Abschluss

## Workflow
1. Transkript-Datei aus `memory/` laden
2. LLM-Zusammenfassung erstellen (Themen, Key-Takeaways, offene Fragen)
3. Als `.md`-Datei in `memory/summaries/` ablegen
4. **Zukünftig (Phase 3):** Automatischer Import in den RAG-Index

## Ausgabe-Format (Markdown)
```
# Session Summary – [Datum]
## Hauptthemen
## Key-Takeaways
## Offene Fragen / To-Dos
## Mitschreib-Block
```

## Abhängigkeiten
- `core/brain.py` → `ask_llm()`
- `memory/` → Input-Transkripte
- `memory/summaries/` → Output-Summaries

## Hinweis (Phase 4)
In Phase 4 werden Summaries automatisch in den RAG-Index integriert, um den Heartbeat-Repetitions-Check zu ermöglichen.
