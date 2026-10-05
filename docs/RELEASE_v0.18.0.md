# Trinity Desktop 0.18.0 — Standalone und Server-Client

Dieser Stand friert den neuen Betriebsmodus ein: Trinity kann weiterhin als
Standalone-Desktop-App laufen oder einen zentralen Linux-Trinity-Server nutzen.
Der Server besitzt Core, Memory, STT, Eve-TTS, Folienkontext und Agenten; Mac,
iPhone und iPad sind Oberflächen desselben Trinity-Profils.

## Verifiziert

- Linux-Bridge und Voice-WebSocket über Tailscale, inklusive Eve-Stimme und
  Folienkontext aus der Companion-App.
- Mac-Client hält den einzigen GPU-Voice-Platz nur, solange er als Sprechstelle
  gewählt ist. Ein explizites „hier antworten“ übernimmt den Platz; der bisherige
  WebSocket wird geschlossen. Ein Test bestätigte Verbindung, Übernahme und Freigabe.
- Websuche nutzt den konfigurierten Tavily-Schlüssel. Abgelehnte Schlüssel werden
  nun als Konfigurationsfehler gemeldet statt als leere Suchergebnisse.
- Desktop-Python-Tests und Companion-Simulator-Build liefen erfolgreich.

## Betrieb und Grenzen

- Der Linux-Host hat nur einen gleichzeitigen Eve-Realtime-Pipeline-Platz. Geräte
  wechseln ihn, statt mehrere GPU-Pipelines zu starten.
- Ältere Companion-Builds müssen zuerst die Lautsprecherausgabe auf diesem Gerät
  übernehmen und danach das Mikro starten. Die Companion-Version 0.18.0 verbindet
  beides beim Mikrostart; sie muss auf dem Gerät installiert sein.
- Zugangstokens und private Konfigurationen gehören nicht in dieses Release.
- Der laufende Linux-Server wurde mit kompatiblen gezielten Änderungen aktualisiert;
  er besitzt eigene private Konfiguration, Memory und Modelle. Ein frischer
  Server-Installationslauf aus diesem Tag wurde noch nicht Ende-zu-Ende geprüft.

## Als Nächstes

1. Companion-App 0.18.0 auf iPhone/iPad installieren und Gerätewechsel real testen.
2. Companion-Ansichten auf iPhone und iPad konsistent machen: Vortrag, Web,
   TrinityHUB, Buchwerkstatt, Medienwerkstatt und benannte eigene URL-Ansichten
   jeweils mit passendem Vollbildmodus.
3. Desktop-Kontext: das aktive Fenster oder einen freigegebenen Bildschirmausschnitt
   sehen und erklären; erst danach bestätigte Änderungen im offenen Programm
   anbieten (Mailentwurf, Excel-Formel/-Analyse, Präsentationsnotiz).
4. Linux-Server-Installation aus einem sauberen Checkout automatisiert prüfen.
