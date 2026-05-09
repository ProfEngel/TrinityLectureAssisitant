# Skill: Timer Agent

## Beschreibung
Startet einen visuellen Countdown im Content-Fenster. Erkennt Zeitangaben in Worten oder Ziffern und rendert einen animierten HTML/JS-Timer.

## Trigger-Wörter
`timer` + Zeitangabe (z.B. `5 Minuten`, `10`, `zwei Minuten`)  
Unterstützt Zahlen als Wörter: `ein`, `zwei`, `drei`, ... `zehn`, `fünfzehn`, `zwanzig`

## Ausgabe
- **html_payload:** Animierter Countdown mit großer Anzeige im Content-Fenster (bleibt offen: `KEEP_OPEN`)

## Beispiel-Sprachbefehle
- *„Trinity, starte einen Timer für 10 Minuten"*
- *„Trinity, Timer 5 Minuten"*
- *„Trinity, stell einen Timer auf zwei Minuten"*

## Abhängigkeiten
- `re` (Regex für Zeitangaben)
- Keine externen APIs nötig
