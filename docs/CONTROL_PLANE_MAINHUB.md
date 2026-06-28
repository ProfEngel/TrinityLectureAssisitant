# Trinity Control Plane und MainHub

Dieses Dokument beschreibt den neuen Unterbau fuer Trinity als
harness-agnostisches Agenten-Betriebssystem. Trinity bleibt die sichtbare
Ansprechperson; Codex, OpenCode, Pi, lokale Skripte und spaetere Harnesses
werden als austauschbare Hintergrundarbeiter angebunden.

## Zielbild

Trinity trennt kuenftig drei Ebenen:

- **Trinity Frontend:** iPad/iPhone, Desktop, WebUI, Telegram, Sprache, Dateien,
  Medien, Hinweise und Freigaben.
- **Control Plane:** Intent, Modus, Agentenauswahl, Jobs, Queue, Policy,
  Freigaben, Audit, Statuskarten, Artefakte und Harness-Auswahl.
- **Harness Adapter:** Codex, OpenCode, lokale Script-Workflows, Builder-Harness
  und spaeter weitere Worker.

Der Nutzer sieht sichere Statuskarten und Ergebnisse. Terminalausgaben,
Roh-JSON und interne Harness-Details bleiben im Maschinenraum.

## Ordnertrennung

Trinity unterscheidet strikt zwischen lokaler Runtime und synchronisiertem Vault.

### Lokale Runtime

Standard auf macOS:

```bash
/Users/matmax/Trinity_Assistant/TrinityRuntime
```

Hier liegen laufende Jobs, Queues, Workspaces, Logs, Datenbanken, Cache, temporaere
Dateien, Locks und lokale Secrets. Dieser Ordner gehoert nicht in iCloud.

Wichtige Unterordner:

- `gateway/`
- `jobs/queue/`, `jobs/active/`, `jobs/workspaces/`, `jobs/finished/`, `jobs/failed/`
- `harnesses/codex/`, `harnesses/pi/`, `harnesses/opencode/`, `harnesses/future/`
- `sessions/`, `logs/`, `cache/`, `containers/`, `databases/`, `memory/`, `temp/`, `secrets/`, `locks/`

### Synchronisierter Vault

Standard in diesem Setup:

```bash
/Users/matmax/Library/Mobile Documents/com~apple~CloudDocs/BrainVault/MainHub/TrinityVault
```

Hier liegen freigegebene Agenten, Projekte, Ergebnisse, Vorlagen, Wissen,
Audit-Berichte und Exporte.

Wichtige Unterordner:

- `00_registry/agent_catalog.json`
- `00_registry/policies/`
- `00_registry/releases/`
- `00_registry/model_profiles/`
- `01_agents/`
- `02_projects/`
- `03_results/`
- `04_templates/`
- `05_knowledge/`
- `06_audit/`
- `07_exports/`
- `99_archive/`

Der Agentenkatalog wird seit v0.15.2 als Schema v2 exportiert und enthaelt
dieselbe Agentenbasis wie ClassicUI/WebUI: Trinity, Agentenbuilder,
Shared/Personal/Staging-Skills und Legacy-Agenten mit Reifegrad, Rechten,
Freigaben, Pfaden, Laufgrenzen und Jobzaehlern.

Nicht in den Vault gehoeren API-Keys, Secrets, aktive SQLite-Datenbanken,
laufende Sessions, temporaere ComfyUI-Dateien oder aktive Job-Workspaces.

## CLI

Initialisierung mit den von Mathias gewuenschten Pfaden:

```bash
trinity --home /Users/matmax/Trinity_Assistant control-plane init \
  --runtime-root /Users/matmax/Trinity_Assistant/TrinityRuntime \
  --vault-root "/Users/matmax/Library/Mobile Documents/com~apple~CloudDocs/BrainVault/MainHub/TrinityVault"
```

Status pruefen:

```bash
trinity --home /Users/matmax/Trinity_Assistant control-plane status
```

Agentenkatalog neu schreiben:

```bash
trinity --home /Users/matmax/Trinity_Assistant control-plane catalog
```

Die Pfade werden in `core/config.json` gespeichert. Danach reicht normalerweise
`trinity control-plane status`.

## Adapter-Vertrag

Jeder Harness-Adapter folgt demselben Vertrag:

- `health_check()`
- `start_job(request)`
- `get_job_status(job_id)`
- `get_job_events(job_id, cursor)`
- `send_input(job_id, input_data)`
- `cancel_job(job_id)`
- `collect_artifacts(job_id)`

Aktuell enthalten:

- **ScriptWorkflowAdapter:** fuer deterministische, lokale Python-Workflows.
- **BuilderHarnessAdapter:** erzeugt sichere Capability Requests fuer neue
  Agenten, aktiviert aber keinen Code automatisch.
- **Pi-Agent:** generischer CLI-/Wrapper-Agent fuer lokale Pi-Setups. Er ist
  deaktiviert per Default und wird nur durch ausdrueckliche Pi-Formulierungen
  gestartet.

Codex und OpenCode bleiben produktiv ueber die bestehenden Trinity-Agenten
angebunden; ihre naechste Ausbaustufe ist, sie ebenfalls vollstaendig ueber den
einheitlichen Adapter-Vertrag zu kapseln.

## Artefakte

Trinity fuehrt im Vault einen append-only Index:

```text
TrinityVault/03_results/artifact_index.jsonl
```

Darueber koennen Bilder, Songs, Videos, Pyodide-/Simulationsergebnisse,
Rechercheberichte, Timer und spaetere Agentenoutputs wiedergefunden werden.
Die Registrierung kopiert zunaechst keine Datei automatisch, sondern speichert
Metadaten, Typ, Titel, Job-ID und Quelle. Das ist absichtlich konservativ, damit
aktive Runtime-Dateien nicht unkontrolliert in iCloud landen.

## Agentenvertrag

Neue Agenten sollen langfristig als Ordner nach diesem Muster entstehen:

```text
agent.yaml
SKILL.md
input.schema.json
output.schema.json
policy.yaml
workflow/
scripts/
templates/
ui/
tests/
fixtures/
README.md
```

Bestehende Trinity-Skills werden weiterhin im aktuellen Shared/Personal/Staging-
System gefunden. Der neue `agent_catalog.json` exportiert zunaechst diesen
Bestand, damit keine Migration blind passieren muss.

## Maturity und Freigabe

Agenten sollen in Stufen reifen:

- `draft`
- `test`
- `guided`
- `trusted`
- `automated`
- `protected`

Policy-Klassen:

- **Gruen:** autonome Analyse, Zusammenfassung, lokale Artefakte.
- **Gelb:** nur mit Freigabe, etwa Mailversand, Upload, Loeschen, Publishing,
  Aktivierung neuer Skills oder Netzwerkzugriff.
- **Rot:** niemals autonom, etwa Zahlungen, rechtliche Signaturen,
  finale Notenabgabe oder Paketinstallation.

## Migration aus Ideaverse und CampusHub

Wichtig: Die Initialisierung kopiert keine bestehenden Agenten aus Ideaverse oder
CampusHub. Erst wenn der Unterbau stabil ist, sollten Agenten kontrolliert in
`TrinityVault/01_agents/` und Projekte in `TrinityVault/02_projects/` ueberfuehrt
werden.

Empfohlene Reihenfolge:

1. Control Plane initialisieren.
2. Agentenkatalog erzeugen und pruefen.
3. Einen kleinen Test-Agenten als `draft` anlegen.
4. Tests und Policy definieren.
5. Freigabe in `staging`.
6. Erst danach bestehende Ideaverse-/CampusHub-Agenten einzeln uebernehmen.
7. Alte Speicherorte erst deaktivieren, wenn der jeweilige Agent im MainHub
   erfolgreich genutzt wurde.

## Onboarding und Rueckrollen

Beim ersten `trinity onboarding` werden Runtime und Vault erklaert und abgefragt.
Runtime sollte lokal liegen; Vault kann iCloud, OneDrive, Google Drive, Dropbox
oder ein anderer synchronisierter Ordner sein.

Falls v0.15.0 auf einem Rechner nicht passt:

1. In den Einstellungen **MainHub / Control Plane** deaktivieren oder
   `control_plane.enabled=false` setzen.
2. Trinity neu starten.
3. Bei Bedarf auf den vorherigen Release-Tag `v0.14.1` zurueckgehen.

Der Vault kann liegen bleiben, weil dort keine aktiven SQLite-Datenbanken oder
laufenden Job-Workspaces gespeichert werden.

## Aktueller Stand

Implementiert ist Phase 1 als Fundament:

- Runtime-/Vault-Pfadmodell.
- CLI-Befehl `control-plane`.
- Vault-Layout inklusive Registry, Policies und Model-Profilen.
- Export von `agent_catalog.json` im Schema v2.
- Artefakt-Index in `03_results/artifact_index.jsonl`.
- Harness-Adapter-Basisvertrag.
- ScriptWorkflowAdapter.
- sicherer BuilderHarnessAdapter fuer Capability Requests.
- generischer Pi-CLI-Agent.
- lokale Job-Datenbank innerhalb der Runtime.

Noch nicht migriert:

- bestehende Agenten aus Ideaverse/CampusHub,
- vollstaendige Codex-/OpenCode-Kapselung im neuen Adaptermodell,
- DCM-Pilot,
- automatische Agentenentwicklung mit Quality-Gates bis zur Freigabe.
