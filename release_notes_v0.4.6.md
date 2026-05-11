# Release Notes v0.4.6 - Natural Interaction & Simulation Update 🧞‍♀️

Dieses Update macht Trinity noch intuitiver bedienbarer und intelligenter im Umgang mit Kontext.

## 🚀 Highlights

- **Natürliches Wake-Word Verhalten**: Trinity unterstützt nun "Satz-vor-Wake-Word" und "Wake-Word-vor-Satz". Sie hört aktiv zu, bis Du fertig gesprochen hast, und nutzt den gesamten Kontext (vorher & nachher).
- **Flexibles Fenster-Management**: Content-Fenster (Simulationen etc.) können nun per Drag & Drop verschoben und per "✕" geschlossen werden.
- **Responsive Simulationen**: Alle Simulationen (Raumzeit, Conway, Ameise, Pong) passen sich nun dynamisch an die Fenstergröße an.
- **Neue Simulations-Modelle**:
  - **Bienen-Schwarm**: Agentenbasierte Schwarmintelligenz.
  - **Spieltheorie (Piraten vs. Fischer)**: Interaktive Simulation eines Räuber-Beute-Modells mit Steuerungsmöglichkeit.
- **Bessere RAG-Recherche**: Die Wissensbasis-Suche nutzt nun den vollen Gesprächskontext der letzten 20 Sekunden für präzisere Ergebnisse.
- **Dynamische Persona**: Trinity antwortet nun situationsbedingt – kurz bei Bestätigungen, ausführlich bei komplexen Erklärungen. Ihr Einsatzbereich wurde auf allgemeine PC-Arbeit und Forschung erweitert.

## 🛠 Technische Details
- `max_tokens` für LLM-Antworten auf 1500 erhöht.
- `trinity_app.py` mit `ContentDragFilter` und Fragment-Handling für Fenster-Schließen erweitert.
- `Soul.md` und `User.md` aktualisiert.

---
*Trinity ist jetzt noch mehr Deine Partnerin auf Augenhöhe!*
