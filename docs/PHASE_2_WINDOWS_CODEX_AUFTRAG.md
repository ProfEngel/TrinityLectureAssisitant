# Auftrag für Codex auf der Windows-Maschine – Phase 2

> **Ausgeführt und historisch:** Dieser Reset-/Inventurauftrag wurde am
> 22. Juli 2026 abgearbeitet und darf nicht erneut als aktueller Auftrag
> ausgeführt werden. Das Ergebnis und die verbliebenen reinen Nachprüfungen
> stehen in `PHASE_2_WINDOWS_RESULT.md`; die einzige aktuelle Resteliste ist
> `IMPLEMENTIERUNGSPLAN_TRINITY.md`.

> Ergebnisstand: Die Inventur und der Reset wurden am 22. Juli 2026 ausgeführt.
> Festgestellte Abweichungen und die kontrollierte Nacharbeit stehen in
> `PHASE_2_WINDOWS_RESULT.md`.

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
7. Auf `BACKUP_M5` das vorhandene
   `Trinity_Gesamtsicherung_2026-07-22_123626.sparsebundle` weder öffnen noch
   verändern, umbenennen oder löschen. Es ist die geprüfte Mac-Sicherung.

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

Verwende Trinity 0.16.51 oder neuer:

1. laufende Trinity-Prozesse beenden
2. Trinity mit dem offiziellen Windows-Installer auf die neueste Version,
   mindestens 0.16.51, aktualisieren
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

## 5. Unabhängige Windows-Sicherung

Wenn das USB-Laufwerk `BACKUP_M5` physisch mit Windows verbunden ist, lege
daneben einen neuen, eindeutig benannten und Windows-kompatiblen
AES-256-verschlüsselten Container oder ein verschlüsseltes Archiv an. Nutze
eine auf dem konkreten Windows-System verfügbare, überprüfbare Methode; speichere
das Passwort weder im Skript noch im Bericht oder Repository.

Die Windows-Sicherung muss mindestens enthalten:

- lokale BIZ-Trinity-Installation und Runtime
- den beim Reset erzeugten Recovery-Ordner einschließlich des Vorzustands
- Konfiguration, Soul, User-Profil, lokale RAG-Quellen und Memory-Dateien
- einen kurzen Prüfbericht ohne Secrets

Der OneDrive-BizVault ist bereits im Mac-Container als synchronisierter Stand
gesichert und muss nicht erneut als unverschlüsselte Kopie abgelegt werden.
Öffne den neuen Windows-Container nach dem Schreiben erneut schreibgeschützt
oder nutze die Prüffunktion des gewählten Archivformats. Vergleiche Datei- und
Ordnerzahlen und dokumentiere Methode, Ergebnis und absoluten Sicherungspfad.

Falls `BACKUP_M5` noch am Mac angeschlossen ist, fahre mit Inventur, Update und
Reset fort und kennzeichne nur diesen externen Sicherungsschritt als ausstehend.
Das lokale Recovery-Paket darf bis zur nachgeholten externen Sicherung nicht
gelöscht werden.

## 6. Ergebnisbericht

Erstelle einen kurzen Bericht mit:

- festgestelltem Ist-Stand
- absolutem BizVault-, Installations- und Runtime-Pfad
- Vorher-/Nachher-Zählern des Resets
- Recovery-Pfad
- Pfad, Verfahren und Prüfergebnis der externen Windows-Sicherung oder klarer
  Status `ausstehend`, falls das Laufwerk noch nicht verbunden ist
- Ergebnissen von Doctor, SQLite-Prüfung, Canvas und Telegram
- offenen Punkten und Auffälligkeiten

Committe oder pushe nichts und erstelle kein Release. Gib den Bericht im
Windows-Codex-Task zurück, damit er anschließend hier abgeglichen werden kann.
