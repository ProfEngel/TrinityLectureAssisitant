# Skill: Focus Agent

## Beschreibung
Aktiviert und deaktiviert den **Fokus-Modus** (auch: „Hör-weg-Modus"). Wenn Trinity in den Fokus-Modus wechselt, hört sie auf zu antworten, bis sie wieder aktiviert wird. Nützlich z.B. während Gruppenarbeiten oder Pausen.

## Trigger-Wörter
**Aktivieren:** `hör kurz weg`, `hör weg`, `bitte nicht zuhören`, `nicht zuhören`  
**Deaktivieren:** `weiter geht's`, `hör wieder zu`, `du kannst wieder zuhören`

## Verhalten
- **Aktivierung:** Trinity bestätigt kurz, dass sie in den passiven Modus wechselt.
- **Deaktivierung:** Trinity meldet sich mit einer kurzen Begrüßung zurück.

## Beispiel-Sprachbefehle
- *„Trinity, hör kurz weg"*
- *„Weiter geht's"*

## Abhängigkeiten
- Keine externen APIs oder Libraries nötig
- Interagiert mit dem `search_context`-Feld, um Trinity's Verhalten zu steuern
