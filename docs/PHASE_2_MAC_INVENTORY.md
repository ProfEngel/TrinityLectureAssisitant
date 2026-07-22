# Phase 2 – Mac-Bestand und Wiederherstellung

Stand: 22. Juli 2026
Status: Inventur fortgeschritten; keine fachlichen Inhalte migriert oder gelöscht

## 1. Aktive private Trinity-Installation

| Merkmal | Festgestellter Stand |
|---|---|
| Installation | `/Users/matmax/Trinity_Assistant` |
| App | `/Users/matmax/Applications/Trinity.app` |
| GitHub | `ProfEngel/TrinityLectureAssisitant` |
| Version | `0.16.50` veröffentlicht; Launcher-Importkorrektur für `0.16.51` in Prüfung |
| Python | Homebrew Python `3.13.13` in lokaler virtueller Umgebung |
| Profil | ausdrücklich `PRIVAT` |
| Runtime | `/Users/matmax/Trinity_Assistant/TrinityRuntime` |
| Inhalts-Vault | iCloud-`BrainVault` |
| lokale Agentenbasis | `/Users/matmax/.agents` über `external_agents_root=/Users/matmax` |
| Companion | aktiviert, Port `8766` |
| Telegram Privat | aktiviert; Token und Chat-ID gesetzt, Secret-Werte nicht ausgegeben |

`trinity doctor --online` meldete Python, SSL, Konfiguration, Desktop-UI,
LLM, Codex, Memory, Logs und Aktualität vollständig als `OK`.

## 2. Wiederherstellungskopien

Es bestehen drei geprüfte lokale Rückfallstände auf dem Mac:

| Wiederherstellung | Umfang | Besonderheiten |
|---|---:|---|
| `/Users/matmax/Trinity-Recovery/2026-07-21-before-repair` | ca. 2,1 GB | Bestand vor der ersten Reparatur, Git-Bundle, Patch, Konfiguration und Datenbanken |
| `/Users/matmax/Trinity-Recovery/installer-20260721_194044` | ca. 2,5 GB | vollständige Installation vor Update auf 0.16.47, Nutzerdaten und Git-Bundle |
| `/Users/matmax/Trinity-Recovery/2026-07-22-creative-canvas-localization` | ca. 3,6 MB | vollständiges Git-Bundle von Creative Canvas und der frühere Cloud-Rest |

Das zweite Bundle enthält den Sicherungs-Branch
`codex/local-trinity-backup-20260721` mit neun früheren lokalen Änderungen.
Der Branch ist zusätzlich wieder in der aktuellen Arbeitskopie lesbar. Die
Recovery-Verzeichnisse `installer-20260721_193918` und
`installer-20260721_193931` sind leer und können später nach der Abnahme
entfernt werden.

Diese Kopien liegen noch auf demselben physischen Mac. Eine verschlüsselte
zweite Kopie auf einem unabhängigen Datenträger fehlt weiterhin. Cloud-Sync
ersetzt diese zweite Kopie nicht.

## 3. Vault-Bestand

| Bereich | Umfang | Dateien/Ordner | Einordnung |
|---|---:|---:|---|
| aktiver BrainVault | ca. 8 KB | 2 Dateien, 8 Ordner | private Datenwahrheit; nur die beschlossene Inhaltsstruktur |
| BizVault auf OneDrive | ca. 8 KB | 2 Dateien, 10 Hauptordner | berufliche Datenwahrheit; Struktur angelegt, noch praktisch leer |
| BrainVault_LEGACY | ca. 42 GB | 79.257 Dateien, 11.475 Ordner | gemischte Migrationsquelle; unverändert erhalten |

Größte Legacy-Bereiche:

- `CampusHub`: ca. 33 GB
- `Ideaverse`: ca. 7,8 GB
- `.agents`: ca. 150 MB
- `MeineAgenten`: ca. 149 MB
- `agents.zip`: ca. 137 MB

Die CampusHub-Struktur bestätigt die beschlossene BizVault-Zuordnung:

- `TeachLab` → `10 Lehre und Lehrmaterial`
- `Prüfungen` → `20 Prüfungen und Bewertungen`
- `Ops` → `30 Hochschulorganisation`
- `ThesisForge` → `60 Abschlussarbeiten und Betreuung`
- `projects/Automatismen` bleibt ausdrücklich außerhalb der fachlichen
  Hauptmigration und wird später separat bewertet.

Der OneDrive-BizVault wurde am 22. Juli 2026 zusätzlich über den auf dem Mac
synchronisierten Pfad bestätigt:

`/Users/matmax/Library/CloudStorage/OneDrive-HochschulefürWirtschaftundUmwelt/BizVault`

Er enthält weiterhin nur die vorbereitete Struktur: 2 Dateien, 11 Ordner und
rund 8 KB. Damit kann der fachliche OneDrive-Bestand vom Mac aus inventarisiert
werden; die lokale Windows-Installation und Windows-Runtime sind darüber nicht
zugänglich.

## 4. Sessions, Arbeitsräume und Memory

Vor dem kontrollierten Reset enthielt die lokale private Runtime fünf
Arbeitsräume und sechs dateibasierte Sessions. Darunter befanden sich
historische berufliche Namen
wie `Wirtschaftsinformatik`, `Wissenschaftliches Arbeiten` und mehrere
Vortragssessions. Sie werden nicht automatisch in Arbeit/BIZ verschoben.
Der vollständige Vorzustand wurde gesichert, sodass wertvolle Summaries später
gezielt aus der Recovery-Kopie bewertet werden können.

Das ältere `memory/` enthält aktuell:

- 62 rohe Session-Dateien
- 10 Session-Transkripte
- 7 Zusammenfassungen
- `trinity_memory.sqlite3`: 16 Sessions, 1.829 Nachrichten,
  1.799 Memories, 8.386 Tags und 16.638 Beziehungen
- `jobs.sqlite3`: 22 Jobs, 89 Schritte und 123 Ereignisse
- `approvals.sqlite3`: eine lokale Freigabeentscheidung

Die neue Runtime-Datenbank `TrinityRuntime/memory/jobs.sqlite3` war leer. Es
besteht daher aktuell kein Job-Duplikat zwischen alter und neuer Jobdatenbank.
Alle vier SQLite-Datenbanken bestanden am 22. Juli 2026 erneut
`PRAGMA integrity_check` mit `ok`.

Am 22. Juli 2026 wurde der private Testbestand vollständig und rückholbar
zurückgesetzt. Die Sicherung liegt unter:

`/Users/matmax/Trinity-Recovery/reset-privat-2026-07-22_120749`

Nach dem Reset bestehen genau ein leerer Eingang und eine neue gemeinsame
Session. Die Memory-Datenbank enthält 0 Sessions, 0 Nachrichten, 0 Memories,
0 Tags und 0 Beziehungen. Backup- und neue SQLite-Datenbank bestanden erneut
`PRAGMA integrity_check` mit `ok`. BrainVault, neun RAG-Dateien, Soul,
User-Profil, Konfiguration und Telegram-Zugang blieben unverändert.

## 5. RAG und Graphify

Der lokale RAG-Bestand umfasst rund 67 MB. Die vorhandenen Quellen sind
überwiegend Kandidaten für Arbeit/BIZ:

- Business-Computing-Skript
- Entscheidungsökonomik-Buch
- Exposé-Evaluation einer wissenschaftlichen Arbeit
- GenAI-Brainshell-Buch
- ein technisches PDF-Testdokument

Die Quellen bleiben bis zur fachlichen Prüfung unverändert. Der Index ist
lokal und neu aufbaubar. Er darf später nicht gleichzeitig private und
berufliche Quellen enthalten.

Der historische Graphify-Index unter
`BrainVault_LEGACY/Ideaverse/graphify-out` verweist noch auf den früheren
gemischten Bestand. Er bleibt nur Orientierung. Neue Graphify-Indizes werden
erst nach der Inhaltszuordnung getrennt für Arbeit und Privat lokal aufgebaut.

## 6. Duplikate – erster technischer Scan

Ein Metadatenvergleich über BrainVault, BizVault und BrainVault_LEGACY fand
8.364 Gruppen mit gleichem Dateinamen und gleicher Dateigröße, zusammen
26.135 Kandidatendateien. Der weitaus größte Teil liegt innerhalb des
Legacy-Bestands und stammt erkennbar aus Python-Umgebungen, `node_modules`,
Build-Artefakten, Caches und kompilierten Dateien.

Zwischen den drei Vault-Wurzeln wurde nur eine triviale namens- und
größengleiche Gruppe (`README.md`) gefunden. Das ist noch kein Beweis für
identischen Inhalt. Ein vollständiger Hashlauf wurde bewusst nicht gestartet,
weil er bis zu 42 GB iCloud-Daten herunterladen könnte. Exakte Hashprüfung
erfolgt später nur für fachliche Dokumentordner, nicht für Software-Caches.

## 7. Creative Canvas – Standalone und Trinity-Komponente

Creative Canvas bleibt als eigenständiges Repository und Standalone-Anwendung
unter `/Users/matmax/TrinityCreativeCanvas` verfügbar. Trinity bindet denselben
Repository-Stand zusätzlich als fest versionierte Komponente unter
`components/TrinityCanvas` ein. Damit gibt es einen gepflegten Quellcode, aber
zwei zulässige Installationsformen. Typecheck und Produktions-Build waren für
die eingebundene Komponente erfolgreich.

Die zuvor vier lokalen Commits und die Produktionsintegration wurden über
Canvas-PR #1 in den GitHub-Stand übernommen. Diese Historie wurde vor der
Umstellung zusätzlich als vollständiges und geprüftes Git-Bundle gesichert.
Der vollständige Legacy-Quellbestand blieb unverändert.
Der frühere minimale Cloud-Rest wurde nicht gelöscht, sondern in denselben
Recovery-Ordner verschoben. Im aktiven BrainVault liegen damit weder Runtime-
noch Build- oder Logdateien von Creative Canvas.

Der Paketmanager meldet sechs bekannte Abhängigkeitswarnungen (eine niedrige,
eine mittlere und vier hohe). Eine erzwungene automatische Aktualisierung wurde
nicht durchgeführt, weil sie inkompatible Versionssprünge verursachen könnte;
die Abhängigkeiten werden später kontrolliert aktualisiert.

Der frühere eigenständige LaunchAgent im Entwicklungsmodus wurde deaktiviert;
künftig startet
Trinity seine eingebundene Canvas-Komponente selbst über einen einzigen
internen Produktionsdienst.

## 8. Agenten – bewusst zurückgestellt

Die Agentenbestände werden in dieser Phase weder verteilt noch fachlich
klassifiziert. Sie bleiben gesichert in `~/.agents`, `BrainVault_LEGACY` und
den Recovery-Kopien. Nach Abschluss der übrigen Architektur werden benötigte
Agenten einzeln und manuell über Codex in Arbeit oder Privat für Goose, Codex,
OpenCode oder andere Harnesses übernommen. Es gibt keine pauschale
Vorinstallation und keine automatische Agentenmigration.

## 9. Nächste kontrollierte Schritte

- [x] aktive Mac-Installation, Profil und Pfade erfassen
- [x] Memory-Quellen und SQLite-Zustand erfassen
- [x] aktive und historische Sessions mengenmäßig erfassen
- [x] Vault-Größen und Hauptbestände erfassen
- [x] ersten nicht-invasiven Duplikat-Scan durchführen
- [x] lokale Wiederherstellungskopien erstellen und prüfen
- [ ] Companion-Fix für profilbezogene Session-/Projektlisten auf echtem Gerät abnehmen
- [x] Creative Canvas lokal aus dem Cloud-Vault herauslösen
- [x] privaten Testbestand rückholbar auf null setzen
- [ ] RAG-Quellen einzeln Arbeit, Privat oder Development zuordnen
- [ ] gesicherte alte Sessions prüfen und nur wertvolle Summaries übernehmen
- [ ] verschlüsselte zweite Wiederherstellungskopie auf unabhängigem Medium erstellen
- [ ] Windows-Installation und Windows-Runtime inventarisieren
- [ ] getrennte Telegram-Zugänge praktisch prüfen
- [ ] Agenten erst nach Abschluss der übrigen Punkte manuell bearbeiten

Vom Mac aus bestätigt: Die private Telegram-Konfiguration besitzt genau einen
aktivierten und vollständig konfigurierten Botzugang. Ob der Windows-BIZ-Zugang
einen getrennten zweiten Bot verwendet, muss auf Windows anhand eines
Secret-freien Fingerprints geprüft werden.

Am Mac war am 22. Juli 2026 kein unabhängiger Datenträger eingehängt und kein
Time-Machine-Ziel konfiguriert. Eine verschlüsselte zweite Sicherung kann daher
erst nach Anschluss oder Bereitstellung eines unabhängigen Zielmediums erstellt
werden; eine weitere Datei auf der internen SSD würde die Backup-Regel nicht
erfüllen.
