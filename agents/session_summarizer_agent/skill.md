# Skill: Session Summarizer

## Overview
Dieser Skill dient der strukturierten Nachbereitung von Vorlesungs- oder Meetings-Sessions, die als Trinity-Logdateien vorliegen. Er extrahiert Lerninhalte, identifiziert Verbesserungspotenziale im Lehrmaterial und bereinigt Transkriptionsfehler der Spracherkennung.

## Output-Struktur
Jede Zusammenfassung muss zwingend folgende Sektionen enthalten:

1. **Themen der Session (Worüber wurde gesprochen?):**
   - Zusammenfassung der inhaltlichen Blöcke.
   - Verwendete Beispiele und Analogien.

2. **Besondere Hinweise & Fokus-Themen (Mitschreib-Block):**
   - Explizite Markierung von Inhalten, bei denen der Dozent Hinweise wie "das würde ich mitschreiben" oder "das ist wichtig" gibt.
   - Zusammenfassung essenzieller Definitionen und Prüfungsschwerpunkte.

3. **Erforderliche Verbesserungen am Skript/Material:**
   - Identifikation von Fehlern in Folien oder Skripten (z. B. Tippfehler, fehlende Kommata).
   - Hinweise auf fehlende oder veraltete Inhalte (z. B. "Folie aktualisieren", "Beispiel nachreichen").

3. **Transkriptionsfehler & Missverständnisse (Mac/Spracherkennung):**
   - Liste von Wörtern, die durch die Spracherkennung akustisch falsch interpretiert wurden.
   - Zuordnung zur korrekten Bedeutung (z. B. *"Machbock"* -> **MacBook**, *"Chef Baser"* -> **Jeff Bezos**).

## Workflow
- **Input:** Eine Session-Logdatei (z. B. aus `memory/`).
- **Analyse:** Suche nach expliziten Triggern wie "das würde ich mitschreiben", "Fehler im Skript", "Folie fehlt" oder "Wichtig für die Prüfung".
- **Bereinigung:** Kontextsensitive Korrektur von Eigennamen und Fachbegriffen.
- **Speicherung:** Ablage als neue Markdown-Datei im Unterordner `memory/summaries/` mit dem Präfix `Summary_`.

## Beispiele für Korrektur-Mappings
- *Nagelfeinde* -> **Nagelfeile**
- *80-60-Fan* -> **1860-Fan**
- *E-Presie* -> **E-Präsi**
- *Glacifikator* -> **Klassifikator**
