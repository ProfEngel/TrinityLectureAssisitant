# Auftrag für Codex auf der Windows-Maschine – Phase 2

Stand: 22. Juli 2026

## Ziel

Inventarisiere die berufliche Trinity-Installation und setze ihren bisherigen
Testbestand nach einer geprüften Wiederherstellungskopie auf null. Der BizVault
bleibt unverändert. Agenten werden ausdrücklich noch nicht inventarisiert,
verschoben oder installiert.

## Verbindliche Architektur

- sichtbares Profil: **Arbeit**, interne Kennung: `BIZ`
- Windows ist die Autorität für Arbeit/BIZ
- BizVault ist die dauerhafte berufliche Datenwahrheit in OneDrive
- Installation, Runtime, Memory, Canvas, Agenten und Indizes liegen lokal und
  nicht im OneDrive-BizVault
- Canvas gehört ab Trinity 0.16.49 automatisch zu Trinity Desktop, bleibt aber
  parallel als Standalone-Repository verfügbar

## Sicherheitsregeln

1. Zuerst nur lesen und inventarisieren.
2. Keine Vault-Datei verschieben, umbenennen, löschen oder automatisch
   migrieren.
3. Keine Tokens, Passwörter, Chat-IDs oder sonstigen Secrets ausgeben oder in
   einen Bericht schreiben.
4. Vor dem Memory-Reset Trinity und alle zugehörigen Prozesse sauber beenden.
5. Den Reset nur mit Wiederherstellungskopie durchführen.
6. Agenten vollständig unangetastet lassen.

## 1. BizVault feststellen

Ermittle den OneDrive-Geschäftsordner bevorzugt aus `$env:OneDriveCommercial`
und suche darunter genau einen Ordner `BizVault`. Dokumentiere den auf Windows
tatsächlich aufgelösten absoluten Pfad. Erwartet wird die Windows-Entsprechung
dieses auf dem Mac bestätigten Ordners:

`/Users/matmax/Library/CloudStorage/OneDrive-HochschulefürWirtschaftundUmwelt/BizVault`

Prüfe anschließend nur:

- Ordner vorhanden und synchronisiert
- 10 verständliche Hauptbereiche von `00 Eingang und noch zuordnen` bis
  `90 Überblick und Ablagehilfe`
- `README.md` und `90 Überblick und Ablagehilfe/ÜBERNAHME_AUS_CAMPUSHUB.md`
- Gesamtzahl Dateien/Ordner und Gesamtgröße

## 2. Windows-Trinity inventarisieren

Dokumentiere ohne Secrets:

- Installationspfad und Git-Remote/Branch/Commit
- installierte Trinity-Version und neuestes GitHub-Release
- Python-Version, Architektur, SSL und Pfad der virtuellen Umgebung
- Profil muss `BIZ` sein
- lokale Runtime und deren Trennung vom BizVault
- Anzahl Arbeitsräume und Sessions
- Memory-Dateien und Zähler der Tabellen `sessions`, `messages`, `memories`,
  `memory_tags`, `memory_edges`
- Jobs-, Approvals- und weitere SQLite-Datenbanken einschließlich
  `PRAGMA integrity_check`
- RAG-Quellen nur mit Dateinamen, Typ, Größe und grober Zuordnungskategorie;
  noch nichts verschieben
- Canvas-Status; die gebündelte Komponente soll unter
  `<Trinity>\components\TrinityCanvas` liegen

Führe `trinity doctor --online` aus und dokumentiere Warnungen und Fehler.

## 3. Beruflichen Telegram-Zugang prüfen

Prüfe ohne Ausgabe des Bot-Tokens:

- Telegram ist in der BIZ-Konfiguration aktiviert
- Bot-Token und Chat-ID sind gesetzt
- `getMe` identifiziert einen erreichbaren Bot
- dieser Zugang ist ausschließlich Arbeit/BIZ zugeordnet
- gib nur Bot-Benutzername und einen kurzen SHA-256-Fingerprint des Tokens aus,
  niemals das Token selbst

Sende erst nach ausdrücklicher Bestätigung des Benutzers eine Testnachricht.
Der spätere Vergleich mit der privaten Mac-Trinity muss ergeben, dass es zwei
verschiedene Bot-Fingerprints sind.

## 4. Update und vollständiger Test-Reset

Sobald Trinity 0.16.49 auf GitHub veröffentlicht ist:

1. laufende Trinity-Prozesse beenden
2. Trinity mit dem offiziellen Windows-Installer auf 0.16.49 aktualisieren
3. `trinity doctor --online` erneut ausführen
4. Zustand mit `trinity memory status` dokumentieren
5. vollständigen, rückholbaren Test-Reset ausführen:

```powershell
trinity memory reset --yes --include-generated --include-canvas
```

6. den gemeldeten Recovery-Pfad prüfen; Manifest und gesicherte SQLite-Datei
   müssen vorhanden sein
7. danach erneut `trinity memory status` ausführen
8. Trinity starten und prüfen, dass genau eine neue leere gemeinsame Session
   existiert und Canvas im Desktop ohne manuelle Portangabe öffnet

Der Reset darf BizVault, RAG-Quelldokumente, `Soul.md`, `User.md`,
`config.json` und Telegram-Konfiguration nicht entfernen.

## 5. Ergebnisbericht

Erstelle einen kurzen Bericht mit:

- festgestelltem Ist-Stand
- absolutem BizVault-, Installations- und Runtime-Pfad
- Vorher-/Nachher-Zählern des Resets
- Recovery-Pfad
- Ergebnissen von Doctor, SQLite-Prüfung, Canvas und Telegram
- offenen Punkten und Auffälligkeiten

Committe oder pushe nichts und erstelle kein Release. Gib den Bericht im
Windows-Codex-Task zurück, damit er anschließend hier abgeglichen werden kann.
