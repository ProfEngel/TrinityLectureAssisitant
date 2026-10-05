# Biz-Windows: Foliensehen und saubere Sprachausgabe

Dieser Stand ergänzt v0.17.11 um die Entfernung des internen `[SPEAKER]`-Tags
aus gesprochenen Antworten. Der Folienweg vom Companion über `/lecture/context`
bis zur multimodalen Anfrage an das konfigurierte LLM ist bereits in v0.17.11
enthalten. Die iPad-/iPhone-App wird getrennt aktualisiert.

## Update der bestehenden Windows-VM

1. Die aktive Installation, den Git-Stand und lokale Änderungen ermitteln.
   Vor dem Update die Konfiguration, `Soul.md`, `User.md`, den gesamten
   `TrinityRuntime`-Ordner und die Voice-Referenzdateien sichern. Backups
   außerhalb des Git-Repositories ablegen.
2. Den geprüften Git-Stand beziehen und Änderungen an der bestehenden
   Installation vergleichen. Windows-spezifische oder lokale Anpassungen
   übernehmen, statt sie durch Mac-Dateien zu ersetzen.
3. `system.profile=BIZ`, Modell-Endpunkt, Bridge- und Voice-Tokens,
   Ubuntu-Verbindungen, Eve-Stimmprobe, Vault-Pfade und Wakeword-Varianten
   aus der Windows-Konfiguration beibehalten. `core/config.json` nicht aus
   dem Repository oder vom Mac übernehmen.
4. Die Windows-Trinity kontrolliert neu starten. Bestehende Chat- und
   Sprachtests wiederholen; eine Modellantwort mit `[SPEAKER]` muss ohne
   dieses Wort gesprochen werden. Die öffentliche Lautsprecherumschaltung
   der älteren Desktop-Sprachausgabe separat prüfen.
5. Das Companion mit dem Tailscale-Endpunkt der Windows-Bridge verbinden und
   eine PDF- und eine HTML-Folie testen: Seitenwechsel, Bildbestätigung in
   den Companion-Einstellungen und eine Frage nach einem Detail, das nur
   im Bild steht. Die Antwort muss über die Windows-Trinity laufen.

## Verteilung der Dienste

Die bestehende VM-/Ubuntu-Aufteilung ist unterstützt: Die Windows-VM hält
Sessions, Memory, Agenten und Freigaben; Ubuntu berechnet STT, TTS und das
Vision-LLM. Companion-Clients wählen die Windows-Bridge. Die Tailscale-
Verbindungen müssen für Bridge, Voice und Modell vorhanden bleiben.

Der Gemma4-Dienst auf Ubuntu benötigt für Bildanfragen eine ausreichend große
`batch-size` und `ubatch-size`. Auf der Workstation wurde am 22.09.2026 die
vorherige Kombination 512/128 nach einem reproduzierbaren Bild-Absturz auf
2048/2048 angehoben. Zwei synthetische Bildwerte und eine echte Companion-
Folie wurden anschließend korrekt gelesen. Dieser Serverwert gehört nicht
in die Windows-Trinity-Konfiguration.

Eine gemeinsame PRIVAT-/BIZ-Instanz ist eine eigene Migration. Sie benötigt
eine Entscheidung über Daten- und Zugriffsgrenzen sowie eine geprüfte
Übernahme der bisherigen Sessions und Memory-Datenbanken. Das Update hier
führt diese Migration nicht aus.
