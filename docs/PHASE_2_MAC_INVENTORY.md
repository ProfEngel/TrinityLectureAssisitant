# Phase 2 – Mac-Bestand und Wiederherstellung

Stand: 21. Juli 2026
Status: Inventur begonnen; keine fachlichen Inhalte migriert oder geloescht

## 1. Aktive Trinity-Installation

- Lokaler Installationsordner: `/Users/matmax/Trinity_Assistant`
- GitHub-Repository: `ProfEngel/TrinityLectureAssisitant`
- Ausgangsstand der Sicherung: Commit `277cfd9`, Version `0.16.45`
- Beim Sicherungszeitpunkt bestanden neun lokale, noch nicht eingecheckte
  Dateiaenderungen. Sie wurden als Binär-Patch gesichert.
- Die vorherige Umgebung verwendete Apples Python 3.9.6.
- Die erneuerte Umgebung verwendet Homebrew Python 3.13.13.

## 2. Wiederherstellungskopie

Lokale Kopie vor der Reparatur:

`/Users/matmax/Trinity-Recovery/2026-07-21-before-repair`

Enthalten sind:

- Arbeitskopie ohne die neu aufbaubare virtuelle Python-Umgebung
- vollständiges Git-Bundle mit Branches und Tags
- Binär-Patch der lokalen Änderungen
- Git-Status der aktiven und der Legacy-Arbeitskopie
- lokale Konfiguration, Memory, TrinityRuntime und RAG-Bestand
- die beiden Phase-1-Dokumente aus dem Legacy-Projekt
- SHA-256-Prüfsummen aller gesicherten Dateien
- die frühere Python-3.9-Umgebung als lokaler Rückfallstand

Alle vier gefundenen SQLite-Datenbanken bestanden vor der Reparatur
`PRAGMA integrity_check`.

## 3. Gefundene Memory- und Laufzeitquellen

| Quelle | Inhalt | Umfang | Einordnung |
|---|---|---:|---|
| `memory/` | altes Trinity-Memory, Transkripte, Summaries und Freigaben | 77 Dateien, 8,1 MB | lokale Legacy-Runtime; sichern und spaeter kontrolliert uebernehmen |
| `memory/trinity_memory.sqlite3` | Sessions, Nachrichten, Memories, Tags und Beziehungen | 1 Datenbank | private lokale Betriebsdaten; nicht in Git |
| `memory/jobs.sqlite3` | alte Jobs, Schritte und Ereignisse | 1 Datenbank | auf Duplikate zur neuen Runtime pruefen |
| `memory/approvals.sqlite3` | lokale Freigabeentscheidungen | 1 Datenbank | lokal und vertraulich |
| `TrinityRuntime/` | neue Jobs, Arbeitsraeume, Katalog, Richtlinien und Modellprofil | 25 Dateien, 276 KB | vorgesehene lokale Runtime |
| `RAG/` | fuenf Quelldokumente sowie lokaler Embedding-Index | 67 MB | Quellen profilbezogen zuordnen; Index ist neu aufbaubar |
| `BrainVault_LEGACY/Ideaverse/graphify-out` | historischer Graphify-Index | ca. 3,4 MB Graphdaten plus Ausgaben | historische Orientierung; nach Profiltrennung lokal neu bauen |

Das alte `memory/` enthaelt 54 rohe Sitzungen, acht Session-Transkripte und
sechs Zusammenfassungen. Inhalte wurden bei dieser Inventur nicht ausgewertet.

## 4. Korrigierte Pfadtrennung

Vor der Reparatur zeigten Inhalts-Vault und ausführbarer Agentenpool beide auf
den neuen iCloud-`BrainVault`. Das war nach der Umbenennung widersprüchlich:
Der neue BrainVault enthaelt keine maßgebliche Agenteninstallation.

Die aktive Mac-Konfiguration trennt nun:

- `control_plane.runtime_root`: lokale `TrinityRuntime`
- `control_plane.vault_root`: iCloud-`BrainVault` fuer dauerhafte private Inhalte
- `control_plane.external_agents_root`: lokaler Bestand mit `.agents`

Die Installations- und Einstellungsoberflaechen verwenden dieselbe Trennung.
Ausfuehrbarer Agentencode wird nicht mehr als Cloud-Vault-Inhalt bezeichnet.

Der erneuerte Trinity-Katalog erfasst derzeit 27 Eintraege: Trinity selbst,
einen lokalen Agentenentwurf, den Agentenbuilder und 24 integrierte
Legacy-Agenten. Das ist der technische Laufzeitkatalog von Trinity. Die
vollstaendige fachliche Entscheidung „behalten, Beruf, Privat, Test oder
loeschen“ erfolgt weiterhin ueber die gesonderte Agenten-Pruefliste.

## 5. Graphify

Der vorhandene Graphify-Index stammt aus dem Legacy-Bestand und verweist intern
noch auf den Pfad vor der Umbenennung. Er bleibt als historische Kopie erhalten,
ist aber nicht der aktuelle Index des neuen BrainVaults. Nach der Daten- und
Profilzuordnung wird Graphify fuer Privat und Beruf jeweils lokal neu aufgebaut.

## 6. Noch offen

- fachliche Zuordnung der RAG-Quellen zu BIZ, Privat oder Test
- Entscheidung, welche alten Sessions dauerhaft in den BrainVault gehoeren
- Abgleich von altem `memory/jobs.sqlite3` und neuer
  `TrinityRuntime/memory/jobs.sqlite3`
- verschluesselte zweite Wiederherstellungskopie auf einem unabhaengigen Medium
- Neuaufbau der lokalen RAG- und Graphify-Indizes nach der Vault-Migration
- fachliche Pruefung und Bereinigung der 24 integrierten Legacy-Agenten
- `TrinityCreativeCanvas` und seinen LaunchAgent aus dem privaten Cloud-Vault
  in eine lokale Installation ueberfuehren; technische Logs lokal ablegen
