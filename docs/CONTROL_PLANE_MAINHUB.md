# Trinity Control Plane und BrainVault

Dieses Dokument beschreibt den aktuellen Unterbau fuer Trinity als
harness-agnostisches Agenten-Betriebssystem. Trinity bleibt die sichtbare
Ansprechperson; Codex, Pi, OpenCode, Antigravity, lokale Skripte und spaetere
Harnesses werden als austauschbare Hintergrundarbeiter angebunden.

## Zielbild

Trinity trennt drei Ebenen:

- **Trinity Frontend:** iPad/iPhone, Desktop, WebUI, Telegram, Sprache, Dateien,
  Medien, Hinweise und Freigaben.
- **Control Plane:** Intent, Modus, Agentenauswahl, Jobs, Queue, Policy,
  Freigaben, Audit, Statuskarten, Artefakte und Harness-Auswahl.
- **Harness Adapter:** Codex, Pi, OpenCode, lokale Script-Workflows,
  Builder-Harness und spaeter weitere Worker.

Der Nutzer sieht sichere Statuskarten und Ergebnisse. Terminalausgaben,
Roh-JSON und interne Harness-Details bleiben soweit moeglich im Maschinenraum.

## Ordnertrennung

Trinity unterscheidet strikt zwischen lokaler Runtime, synchronisiertem
Inhalts-Vault und lokalem Agenten-Werkzeugkasten.

### Lokale Runtime

Die Runtime liegt lokal, nicht in iCloud, OneDrive, Google Drive oder Dropbox.
Sie enthaelt laufende Jobs, Queues, Workspaces, Logs, Datenbanken, Cache,
temporaere Dateien, Locks und lokale Secrets.

Beispiel:

```bash
/Users/NAME/Trinity_Assistant/TrinityRuntime
```

Wichtige Unterordner sind `jobs/`, `harnesses/`, `sessions/`, `logs/`,
`cache/`, `databases/`, `memory/`, `temp/`, `secrets/` und `locks/`.

### BrainVault / Cloud-Vault fuer Inhalte

Der BrainVault darf synchronisiert werden. Er enthaelt Projekte, Dokumente,
Wissen, Vorlagen und dauerhafte Ergebnisse.

Beispiel:

```bash
/Cloud/BrainVault
```

### Lokaler Agenten-Werkzeugkasten

Ausfuehrbare externe Agenten liegen lokal und werden separat ueber Git
versioniert. Kanonische Struktur:

```text
Lokaler-Agenten-Werkzeugkasten/
├── .agents/
├── AGENTS.md
└── CLAUDE.md
```

Die lokale `.agents`-Ablage ist die Quelle gemeinsamer externer Agenten. Trinity,
Codex, Pi, OpenCode, Antigravity und spaetere Harnesses duerfen denselben Pool
lesen, testen und erweitern, solange die dortigen Regeln gelten.

Alte `MainHub/TrinityVault`- oder `00_registry`/`01_agents`-Layouts sind
historische Zwischenstaende. Sie koennen archiviert werden, wenn die
Trinity-Einstellungen auf den lokalen Agenten-Root zeigen und dort `.agents` sowie
`AGENTS.md` vorhanden sind.

Nicht in den BrainVault gehoeren aktive SQLite-Datenbanken, laufende Sessions,
temporaere ComfyUI-Dateien, aktive Job-Workspaces oder Secrets im Klartext.

## CLI und Status

Initialisierung mit generischen Pfaden:

```bash
trinity control-plane init \
  --runtime-root "/lokaler/pfad/zu/TrinityRuntime" \
  --vault-root "/cloud/pfad/zu/BrainVault" \
  --agents-root "/lokaler/pfad/mit/.agents"
```

Status pruefen:

```bash
trinity control-plane status
agentctl list
```

Die Pfade werden in `core/config.json` gespeichert. In den Einstellungen steht
unter **Trinity-Ablagen** sichtbar:

- lokale Runtime
- Cloud-Vault fuer dauerhafte Inhalte
- lokaler Agenten-Werkzeugkasten
- Standard-Extern-Harness

## Harness-Rollen

Aktuelle Rollenlogik:

- **Pi:** Standard-Harness fuer laufende externe Agentenarbeit.
- **Codex:** Builder-Harness fuer neue Agenten, Imports, Refactorings, Tests und
  Quality-Gates.
- **OpenCode:** optionaler Ausfuehrungs- oder Automations-Harness fuer
  freigegebene Projekte.
- **Trinity:** lokale Control Plane und interne Agenten.

Jeder Harness bleibt an freigegebene Projekt-Aliasse und die Regeln des
jeweiligen Projekts gebunden. Externe Aktionen wie Mailversand, Loeschen,
Publishing, Deployments oder Uploads brauchen explizite Freigabe.

## Externe Agenten

Neue externe Agenten liegen direkt unter:

```text
.agents/<bereich>/<agent-id>/
```

Empfohlener Agentenordner:

```text
agent.yaml
SKILL.md
README.md
policy.yaml
workflow/
scripts/
templates/
ui/
tests/
fixtures/
```

Die Quelle der Wahrheit ist `agent.yaml`; daraus werden Eintraege unter
`.agents/_meta` und UI-Listen aufgebaut. Details stehen in
[Agenten-Werkzeugkasten](BRAINVAULT_AGENTS.md).

## Artefakte und Summaries

Aktive Runtime-Artefakte bleiben lokal. Freigegebene oder dauerhafte Ergebnisse
koennen im BrainVault katalogisiert werden. Session-Summaries werden lokal unter
`memory/summaries/` erzeugt, in Trinitys MemoryStore aufgenommen und fuer RAG
indexiert. Companion/WebUI/Desktop koennen sie als Ergebnis-Asset anzeigen.

## Rueckrollen

Rueckrollen bleibt bewusst einfach:

1. In den Einstellungen **Trinity-Ablagen** deaktivieren oder
   `control_plane.enabled=false` setzen.
2. Trinity neu starten.
3. Bei Bedarf auf einen stabilen GitHub-Release-Tag zurueckgehen.

Der BrainVault kann liegen bleiben, weil dort keine aktiven Runtime-Datenbanken
oder laufenden Job-Workspaces gespeichert werden.
