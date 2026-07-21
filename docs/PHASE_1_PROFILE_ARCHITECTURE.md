# Trinity Profilarchitektur – Phase 1

Status: verbindlich
Beschlossen: 2026-07-20
Namens- und Ablageentscheidung ergaenzt: 2026-07-21
Grundlage: Codex-Aufgabe `019f7b1e-e6c9-7fc0-8c92-aa10c0c3c6b3`

## 1. Grundsatz

Trinity wird als drei strikt getrennte Profile betrieben: **Beruf (BIZ)**,
**Privat (PRIVAT)** und **Testbereich (TEST)**. Jedes produktive Profil hat genau eine autoritative
Trinity-Instanz. Clients koennen sich mit dieser Instanz verbinden, werden
dadurch aber nicht selbst zur Ausfuehrungsautoritaet.

**Gemeinsam** ist kein viertes Datenprofil. Es ist eine Installationsklasse fuer
Agenten, die sowohl in BIZ als auch PRIVAT eingesetzt werden duerfen.

Cloud-Vaults speichern alle dauerhaft benoetigten fachlichen Inhalte,
einschliesslich aktuell bearbeiteter Projekte. Sie sind weder die
aktive Trinity-Runtime noch ein Ersatz fuer ein Backup.

## 2. Verbindliche Begriffe

### BIZ

`BIZ` bezeichnet alle beruflichen Daten und Arbeitsablaeufe, insbesondere
Lehre, Forschung, Hochschulverwaltung, berufliche Kommunikation, Gutachten,
Praesentationen sowie die dafuer bestimmten Agenten und Wissensquellen.

- Autoritaet: Trinity BIZ auf der Windows-VM
- Harnesses: Codex BIZ und Goose BIZ laufen nur auf der Windows-VM
- Memory und aktive Sessions: nur in der lokalen BIZ-Runtime
- Dauerhafte Cloud-Inhalte: `BizVault` in OneDrive
- Mac-Rolle: Remote-Client fuer Trinity BIZ und Dateiclient fuer den BizVault

### PRIVAT

`PRIVAT` bezeichnet persoenliche, familiaere und kreative Daten und
Arbeitsablaeufe. Trinity-Code hat selbst kein fachliches Datenprofil;
Entwicklung und Migration werden im isolierten TEST-Bereich durchgefuehrt.

- Autoritaet: Trinity PRIVAT auf dem Mac
- Harnesses: Codex PRIVAT und Goose PRIVAT laufen nur auf dem Mac
- Memory und aktive Sessions: nur in der lokalen PRIVAT-Runtime
- Dauerhafte Cloud-Inhalte: `BrainVault` in iCloud Drive
- Windows-Rolle: kein Zugriff auf PRIVAT

### TEST

`TEST` ist eine isolierte Umgebung fuer Entwicklung, Migrationen, Agententests
und Ende-zu-Ende-Versuche. TEST ist kein Sammelprofil fuer unklare Daten.

- Autoritaet: zunaechst eine separate lokale Test-Runtime auf dem Mac
- Daten: synthetische Daten oder ausdruecklich freigegebene Kopien
- Memory: eigenes, jederzeit ersetzbares Test-Memory
- Cloud: kein automatischer Cloud-Vault und kein automatisches Publishing
- Produktion: kein Schreibzugriff auf BIZ- oder PRIVAT-Memory

## 3. Autoritaeten

| Profil | Autoritative Instanz | Darf Agenten ausfuehren | Cloud-Vault |
|---|---|---|---|
| BIZ | Windows-VM | Trinity BIZ, Codex BIZ, Goose BIZ | OneDrive/BizVault |
| PRIVAT | Mac | Trinity PRIVAT, Codex PRIVAT, Goose PRIVAT | iCloud/BrainVault |
| TEST | separate Mac-Test-Runtime | nur Test-Harnesses | keiner |

Die Ubuntu-Workstation ist kein eigenes Profil. Sie dient BIZ ausschliesslich
als abgesicherter LLM-Inferenzdienst. Sie besitzt weder BIZ-Memory noch einen
Cloud-Vault.

## 4. Erlaubte Datenfluesse

### BIZ

1. Ein BIZ-faehiger Client sendet einen Auftrag an Trinity BIZ auf Windows.
2. Trinity BIZ verarbeitet ihn in ihrer lokalen Runtime.
3. Freigegebene dauerhafte Ergebnisse werden versioniert in den BizVault
   veroeffentlicht.
4. OneDrive synchronisiert diese Inhalte auf den Mac.
5. Auf dem Mac vorgenommene Dateiaenderungen duerfen zur Windows-Autoritaet
   zurueckfliessen. Vor dem Ueberschreiben sind Version oder Pruefsumme und ein
   Konfliktstatus zu pruefen.

### PRIVAT

1. Ein PRIVAT-faehiger Client sendet einen Auftrag an Trinity PRIVAT auf dem
   Mac.
2. Trinity PRIVAT verarbeitet ihn in ihrer lokalen Runtime.
3. Freigegebene dauerhafte Ergebnisse werden versioniert in den BrainVault
   veroeffentlicht.
4. iCloud verteilt nur die Vault-Inhalte, nicht die aktive Runtime.

### Profiluebergreifend

Ein profiluebergreifender Zugriff ist nur fuer einen konkret benannten Auftrag,
mit expliziter Nutzerfreigabe und Audit-Eintrag erlaubt. Die Freigabe benennt
Quelle, Ziel, Zweck und betroffene Dateien. Es gibt keinen dauerhaften
automatischen BIZ-Zugriff aus PRIVAT und keinen PRIVAT-Zugriff aus BIZ.

Trinity-Code und ausfuehrbare Agentendefinitionen werden ueber Git und
versionierte Releases verteilt und anschliessend lokal installiert. Aktive
Programmdateien werden nicht durch OneDrive oder iCloud zwischen den
Autoritaeten synchronisiert.

## 5. Verbotene Datenfluesse

Nicht in OneDrive oder iCloud gehoeren:

- aktive SQLite- oder andere Runtime-Datenbanken
- laufende Jobs, Queues, Locks und aktive Arbeitsverzeichnisse
- unbereinigte Logs, Cache und temporaere Renderings
- Tokens, Passwoerter, API-Schluessel oder sonstige Secrets
- direkt ausfuehrbarer, nicht versionierter Agentencode als Quelle der Wahrheit

Ausserdem verboten sind:

- lokale Ausfuehrung von BIZ-Agenten auf dem Mac im Normalbetrieb
- lokale Ausfuehrung von PRIVAT-Agenten auf Windows
- automatisches Lernen aus geaenderten Dateien ohne Kennzeichnung als
  akzeptiert, bearbeitet oder abgelehnt
- stilles Ueberschreiben einer neueren Cloud-Fassung

## 6. Client- und Profilmatrix

| Client/System | BIZ | PRIVAT | TEST | Rolle |
|---|:---:|:---:|:---:|---|
| Windows-Desktop/VM | ja | nein | nein | BIZ-Autoritaet |
| Mac-Desktop | remote | ja | ja | PRIVAT-Autoritaet, BIZ-Client, Testhost |
| iPhone-App | ja | ja | nein | Remote-Client |
| iPad-App | ja | ja | nein | Remote-Client |
| Even G2 via Telefon | ja | ja | nein | Remote-HUD/Mikrofon |
| Telegram | ja | ja | nein | getrennte Bots oder strikt getrennte Chats |
| Ubuntu-Host | Backend | nein | nein | BIZ-LLM-Inferenz, kein Nutzerprofil |

Auf iPhone, iPad und G2 werden BIZ und PRIVAT mit getrennten Serveradressen,
Tokens, lokalen Caches und klar sichtbarer Profilkennzeichnung eingerichtet.
TEST bleibt auf dem Mac, bis ein konkreter Test einen weiteren Client verlangt.

## 7. Session-Regel

- Pro Profil gibt es hoechstens eine aktive serverseitige Session.
- Alle Clients eines Profils sehen dieselbe Session und denselben Eventstrom.
- BIZ und PRIVAT koennen gleichzeitig je eine aktive Session besitzen.
- Das Schliessen einer Session wirkt profilweit.
- Transcript, Summary, Manifest und freigegebene Artefakte werden erst nach
  erfolgreichem Sessionabschluss in den jeweiligen Cloud-Vault publiziert.

## 8. Cloud-Strukturen

Beide produktiven Vaults verwenden dieselben portablen Ordnernamen:

```text
<Vault>/
├── README.md
├── Knowledge/
│   ├── Sources/
│   └── Curated/
├── Projects/
├── Sessions/
│   ├── Transcripts/
│   ├── Summaries/
│   ├── Manifests/
│   └── Artifacts/
├── Outputs/
│   ├── Documents/
│   ├── Presentations/
│   ├── Images/
│   ├── Audio/
│   ├── Video/
│   └── HTML/
├── AgentKnowledge/
├── AgentReleases/
└── Catalog/
```

`AgentKnowledge` enthaelt Wissensquellen und freigegebene Feedbackdaten.
`AgentReleases` enthaelt versionierte, wiederherstellbare Releasepakete. Git
bleibt die Quelle der Wahrheit fuer Code. `Catalog` enthaelt spaeter
maschinenlesbare Manifeste und Indizes.

Diese in Phase 1 angelegte technische Grundstruktur ist noch keine endgueltige
Benutzernavigation. Die spaetere, flache und deutsch benannte Zielstruktur ist
im `TRINITY_ARCHITEKTUR_CHEATSHEET.md` beschrieben und wird erst nach der
Bestandsaufnahme umgesetzt.

## 9. Angelegte Pfade

- BIZ auf diesem Mac:
  `/Users/matmax/Library/CloudStorage/OneDrive-HochschulefürWirtschaftundUmwelt/BizVault`
- PRIVAT auf diesem Mac:
  `/Users/matmax/Library/Mobile Documents/com~apple~CloudDocs/BrainVault`
- Alter gemischter Bestand seit 2026-07-21:
  `/Users/matmax/Library/Mobile Documents/com~apple~CloudDocs/BrainVault_LEGACY`
- Windows verwendet denselben synchronisierten BizVault unter seinem lokalen
  OneDrive-Stammpfad.

### Uebergangsgrenze zum heutigen Code

Die neuen Pfade sind Inhalts- und Ergebnis-Vaults. `control_plane.vault_root`
beziehungsweise `TRINITY_VAULT` bezeichnet den dauerhaften Inhalts-Vault.
`control_plane.external_agents_root` beziehungsweise `TRINITY_AGENTS_ROOT`
bezeichnet dagegen die lokale Installation ausfuehrbarer Agenten. Der alte
Cloud-Agentenpool bleibt nur als Migrationsquelle in `BrainVault_LEGACY`.

Die spaetere Implementierung fuehrt dafuer einen getrennten Content-Vault-Pfad
und den Vault-Publisher ein. Bis dahin gilt:

- keine bestehenden Daten automatisch verschieben oder kopieren
- bestehenden Agentenpool in `BrainVault_LEGACY` unveraendert lassen
- keine veralteten Agentenkataloge gegen den neuen BrainVault ausfuehren
- keine Trinity-Runtime auf einen der neuen Cloud-Pfade zeigen lassen
- die neuen Vaults nur als vorbereitete Zielstruktur behandeln

## 10. Abnahmekriterien fuer Phase 1

- BIZ, PRIVAT und TEST sind in diesem Dokument verbindlich definiert.
- Windows ist als einzige BIZ-Autoritaet festgelegt.
- Mac ist als einzige PRIVAT-Autoritaet und initialer TEST-Host festgelegt.
- erlaubte und verbotene Datenfluesse sind dokumentiert.
- die Client- und Profilmatrix ist entschieden.
- BizVault und BrainVault sind mit identischer Grundstruktur angelegt.
- bestehende Daten und Konfigurationen wurden noch nicht migriert.

Diese Entscheidungen werden erst durch eine neue, versionierte
Architekturentscheidung geaendert.
