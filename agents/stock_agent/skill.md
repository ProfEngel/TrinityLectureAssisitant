# Skill: Stock Agent

## Beschreibung
Ruft **Live-Aktienkurse** via Yahoo Finance API ab und rendert einen interaktiven SVG-Kurschart im Content-Fenster. Erkennt Aktiennamen auf Deutsch und wandelt sie automatisch in Ticker-Symbole um.

## Trigger-Wörter
`aktienkurs`, `aktie`, `kurs von`, `preis von`, `stock`, `krypto`, `bitcoin`, `ethereum`

## Bekannte Aktien (Mapping)
Apple → AAPL, Microsoft → MSFT, Google → GOOGL, Amazon → AMZN, Tesla → TSLA, Nvidia → NVDA, Meta → META, SAP → SAP, Siemens → SIE.DE, VW → VOW3.DE, BMW → BMW.DE, Bitcoin → BTC-USD, Ethereum → ETH-USD

## Ausgabe
- **html_payload:** SVG-Kurschart der letzten Wochen + aktueller Kurs im Content-Fenster

## Beispiel-Sprachbefehle
- *„Trinity, wie steht der Aktienkurs von Nvidia?"*
- *„Trinity, Preis von Bitcoin"*
- *„Trinity, Aktie Apple"*

## Abhängigkeiten
- `requests` (Yahoo Finance API)
- `re` (Ticker-Erkennung)
