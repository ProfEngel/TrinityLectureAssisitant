# Phase 2 – Mac-Bestand und Wiederherstellung

Stand: 22. Juli 2026
Status: Mac-Inventur und externe Sicherung abgeschlossen; keine fachlichen Inhalte migriert oder gelöscht

## 1. Aktive private Trinity-Installation

| Merkmal | Festgestellter Stand |
|---|---|
| Installation | `/Users/matmax/Trinity_Assistant` |
| App | `/Users/matmax/Applications/Trinity.app` |
| GitHub | `ProfEngel/TrinityLectureAssisitant` |
| Version | `0.16.52` veröffentlicht; kombinierter Launcher-/Canvas-Start erneut lokal geprüft |
| Python | Homebrew Python `3.13.13` in lokaler virtueller Umgebung |
| Profil | ausdrücklich `PRIVAT` |
| Runtime | `/Users/matmax/Trinity_Assistant/TrinityRuntime` |
| Inhalts-Vault | iCloud-`BrainVault` |
| lokale Agentenbasis | `/Users/matmax/.agents` über `external_agents_root=/Users/matmax` |
| Companion | aktiviert, Port `8766`; Apple-Companion `0.16.56` gebaut |
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

Die lokalen Rückfallstände liegen weiterhin auf demselben physischen Mac.
Zusätzlich wurde am 22. Juli 2026 eine unabhängige, verschlüsselte
Gesamtsicherung auf dem USB-Laufwerk `BACKUP_M5` erstellt:

`Trinity_Gesamtsicherung_2026-07-22_123626.sparsebundle`

Der rund 50 GB große AES-256-verschlüsselte APFS-Container enthält den aktuellen
BrainVault, den synchronisierten BizVault-Stand, BrainVault_LEGACY,
Trinity-Recovery, die aktuellen Trinity- und Canvas-Arbeitsstände sowie eine
reine Sicherheitskopie der lokalen Agentendateien. Alle sieben Bereiche wurden
objektgenau mit ihren Quellen verglichen. Das schreibgeschützt eingebundene
APFS-Dateisystem bestand `fsck_apfs` mit Exit-Code 0 und wurde danach sicher
ausgeworfen. Passwort und sonstige Secrets wurden weder protokolliert noch im
Repository gespeichert.

Die ausschließlich lokal auf Windows liegende BIZ-Installation und BIZ-Runtime
sind nicht Teil dieser Mac-Sicherung. Sie benötigen nach der Windows-Inventur
eine eigene Windows-kompatible verschlüsselte Sicherung auf demselben externen
Datenträger. Das vorhandene Mac-Sparsebundle darf dabei nicht verändert werden.

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

Die laufende Bridge wurde anschließend authentifiziert geprüft: Profil
`PRIVAT`, genau ein Arbeitsraum `Schnellsessions`, genau eine gemeinsame
Session und HTTP 403 bei einem absichtlich falschen erwarteten BIZ-Profil.
Canvas antwortete am konfigurierten Tailnet-Endpunkt mit HTTP 200.

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
- [ ] Apple-Companion 0.16.56 mit Profilanzeige, Canvas und kompakter
  Arbeitsraumleiste auf echtem iPhone/iPad abnehmen
- [x] Creative Canvas lokal aus dem Cloud-Vault herauslösen
- [x] privaten Testbestand rückholbar auf null setzen
- [ ] RAG-Quellen einzeln Arbeit, Privat oder Development zuordnen
- [ ] gesicherte alte Sessions prüfen und nur wertvolle Summaries übernehmen
- [x] Mac-Bestand verschlüsselt auf unabhängigem Medium sichern und prüfen
- [ ] Windows-lokale BIZ-Runtime separat verschlüsselt auf unabhängigem Medium sichern
- [x] Windows-Installation, Windows-Runtime und BIZ-Reset inventarisieren
- [x] getrennte Telegram-Zugänge ohne Testnachricht technisch prüfen
- [ ] Agenten erst nach Abschluss der übrigen Punkte manuell bearbeiten

Bestätigt: Privat verwendet `Trinity_M5_bot` mit Fingerprint `-roZaf1bcMsO`,
Arbeit verwendet `Trinity_HFWU_bot` mit Fingerprint `02N8LCwzPked`. Beide Bots
sind erreichbar und die Fingerprints verschieden. Es wurde keine Testnachricht
gesendet.

Der Windows-Ergebnisbericht und die kontrollierte Vault-/RAG-Nacharbeit sind in
`PHASE_2_WINDOWS_RESULT.md` festgehalten. Die Windows-Inventur ist abgeschlossen;
die BIZ-Vault-Zuordnung und die unabhängige Windows-Sicherung bleiben offen.

Das unabhängige USB-Laufwerk `BACKUP_M5` wurde am 22. Juli 2026 erfolgreich für
die geprüfte Mac-Gesamtsicherung verwendet. Der verschlüsselte Container ist
geschlossen; das äußere ExFAT-Volume bleibt bis zum manuellen Auswerfen
eingehängt. Die Windows-Sicherung muss als eigener verschlüsselter Container
daneben angelegt werden, weil Windows das Mac-APFS-Sparsebundle nicht als
Arbeitsformat verwenden soll.
