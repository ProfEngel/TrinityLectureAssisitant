# Timer Agent Skill

## Beschreibung
Dieser Live-Skill ermöglicht es Trinity, auf Zuruf einen visuellen Countdown-Timer im Glas-Fenster einzublenden.

## Trigger-Erkennung
Der Skill reagiert auf Keywords wie "timer" in Kombination mit einer Zeitangabe (z.B. "5 minuten"). Zahlwörter (eins, zwei, ...) werden automatisch erkannt und konvertiert.

## Interface
- `can_handle(query: str) -> bool`: Erkennt Timer-Trigger.
- `execute(query: str) -> dict`: Generiert den HTML-Payload für den Timer und den System-Prompt für Trinity.
