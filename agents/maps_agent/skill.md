# Maps Agent Skill

## Beschreibung
Dieser Live-Skill ermöglicht es Trinity, interaktive Google Maps Karten für bestimmte Orte oder Routen im Glas-Fenster einzublenden.

## Trigger-Erkennung
Der Skill reagiert auf Keywords wie "route", "karte", "navigiere" oder "maps".

## Interface
- `can_handle(query: str) -> bool`: Erkennt Maps-Trigger.
- `execute(query: str) -> dict`: Extrahiert das Ziel und generiert den HTML-Payload für die Karte sowie den System-Prompt für Trinity.
