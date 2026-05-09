# Skill: Summary Agent

## Beschreibung
Erstellt ein **„Big Picture"** der aktuellen Vorlesung – eine strukturierte Zusammenfassung des bisherigen Transkripts als visuell aufbereitetes HTML-Dokument im Content-Fenster.

## Trigger-Wörter
`big picture`, `big-picture`, `überblick der vorlesung`, `überblick der sitzung`, `zusammenfassung der vorlesung`, `zusammenfassung der heutigen`, `infografik der vorlesung`, `visualisiere die vorlesung`

## Ausgabe
- **html_payload:** Strukturierte Zusammenfassung mit Themen, Key-Takeaways und Zeitstempeln im Content-Fenster (`KEEP_OPEN`)

## Beispiel-Sprachbefehle
- *„Trinity, Big Picture"*
- *„Trinity, gib mir einen Überblick der heutigen Vorlesung"*
- *„Trinity, Zusammenfassung der Sitzung"*

## Abhängigkeiten
- `core/brain.py` → `read_transcript()`, `ask_llm()`
- `memory/` → Aktives Transkript der laufenden Session
