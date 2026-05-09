# Skill: Image Agent

## Beschreibung
Generiert KI-Bilder und Infografiken via **fal.ai** (Modell: `nano-banana-2`). Der Agent wandelt die gesprochene Beschreibung in einen detaillierten Bildprompt um (LLM-Parsing) und zeigt das fertige Bild im Content-Fenster an.

## Trigger-Wörter
`infografik`, `grafik`, `visualisier`, `schaubild`, `illustration`, `bild erstell`, `zeichnung erstell`

## Voraussetzungen
- fal.ai API-Key in `core/config.json` unter `apis.fal_ai`
- Ohne Key: freundlicher Hinweis auf die Einstellungen

## Ausgabe
- **html_payload:** Das generierte Bild zentriert im Content-Fenster (auto-resizing)

## Beispiel-Sprachbefehle
- *„Trinity, erstelle ein Schaubild zum Thema neuronale Netze"*
- *„Trinity, visualisiere den Unterschied zwischen Machine Learning und Deep Learning"*
- *„Trinity, erstelle eine Infografik zu Prompt Engineering"*

## Abhängigkeiten
- `requests`, `fal-client` (HTTP / fal.ai SDK)
- `core/brain.py` → `ask_llm()` für Prompt-Optimierung
- `gen_images/` → Ablageort für generierte PNGs
