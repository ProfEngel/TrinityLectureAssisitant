# Skill: Notes Agent

## Beschreibung
Ein Agent zur Verwaltung von Notizen und Checklisten (To-Do-Listen). Er erlaubt es, per Sprachbefehl neue Notizen anzulegen, bestehende Notizen zu erweitern und Checklisten-Elemente abzuhaken. Die Notizen werden als Markdown-Dateien im Verzeichnis `memory/notes/` gespeichert und visuell im Content-Fenster angezeigt.

## Trigger-Wörter
`notiere`, `mache eine notiz`, `schreibe auf`, `füge zur notiz hinzu`, `erweitere die notiz`, `lese die notiz`, `zeig mir die notiz`, `hake ab`, `checkliste`, `to-do`, `todo`

## Ausgabe
- **html_payload:** Visuelle Darstellung der Notiz oder Checkliste im Content-Fenster (Post-it / Task-List Design).
- **search_context:** Bestätigung für die Sprachausgabe (z.B. "Die Notiz wurde gespeichert.").

## Beispiel-Sprachbefehle
- *„Trinity, notiere mir zum Projekt Alpha, dass das Meeting verschoben wurde."*
- *„Füge zur Notiz Projekt Alpha hinzu, dass Max auch teilnimmt."*
- *„Mach eine To-Do Notiz für heute: Milch kaufen, E-Mails beantworten."*
- *„Hake auf der To-Do Notiz Milch kaufen ab."*
- *„Zeig mir die Notiz Projekt Alpha."*

## Abhängigkeiten
- `core/brain.py` → `ask_llm()` für die Extraktion von Thema und Inhalt.
- `memory/notes/` → Speicherort für die Notizdateien.
