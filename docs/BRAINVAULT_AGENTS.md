# Lokaler Agenten-Werkzeugkasten

Ab v0.16.0 trennt Trinity zwei Agentenwelten strikt:

1. **Trinity-interne Agenten** bleiben im Trinity-Repository. Dazu gehoeren UI,
   STT/TTS, Memory, RAG, Medienfunktionen, Telegram, Companion, Timer,
   Vortragsfunktionen und Control-Plane-Logik.
2. **Werkzeugkasten-Agenten** sind externe, wiederverwendbare Fachagenten. Sie
   liegen kanonisch in der lokalen Ablage `~/.agents/` und koennen von Trinity, Codex,
   Pi, OpenCode, Claude Code, Antigravity und spaeteren Harnesses gelesen,
   getestet und erweitert werden.

Gleichnamige Agenten sind erlaubt. Intern unterscheidet Trinity nach `id`,
`source`, `execution_scope` und `path`.

## Ordnerstruktur

```text
Lokaler-Agenten-Werkzeugkasten/
├── .agents/
│   ├── <bereich>/
│   │   └── <agent-id>/
│   │       ├── agent.yaml
│   │       ├── SKILL.md
│   │       ├── README.md
│   │       ├── workflows/
│   │       ├── scripts/
│   │       ├── templates/
│   │       ├── ui/
│   │       ├── tests/
│   │       ├── fixtures/
│   │       └── adapters/
│   └── _meta/
│       ├── agent_catalog.json
│       ├── AGENT_CATALOG.md
│       ├── agent_catalog.schema.json
│       ├── harnesses.yaml
│       └── models.yaml
├── AGENTS.md
└── CLAUDE.md
```

Nicht benoetigte Unterordner werden nicht kuenstlich angelegt. Die Quelle der
Wahrheit ist immer die jeweilige `agent.yaml`; JSON- und Markdown-Kataloge
werden daraus generiert.

## agent.yaml

Minimaler neuer Agent:

```yaml
id: research.document_reviewer
name: Document Reviewer
version: 0.1.0
source: brainvault
execution_scope: shared_harness
status: draft
enabled: false
path: .agents/research/document-reviewer
compatible_harnesses:
  - trinity
  - codex
  - pi
  - opencode
  - claude-code
  - antigravity
preferred_harness: auto
```

Nach Validierung wird nicht verschoben. Der Status wird direkt im Manifest
geaendert:

```yaml
status: active
enabled: true
validation:
  last_validated: 2026-06-29
```

## agentctl

`agentctl` ist das kleine lokale Werkzeug fuer externe Agenten:

```bash
agentctl init
agentctl list
agentctl inspect <agent-id>
agentctl validate <agent-id>
agentctl catalog build
agentctl create <bereich> <agent-id>
agentctl import <bestehender-agentenordner> --area skills --preferred-harness codex --status active
agentctl register <projekt-oder-dateipfad> --area projects --agent-id mein-agent --preferred-harness codex
agentctl audit <suchpfad> --output BRAINVAULT_AGENT_AUDIT.md
```

Beispiel:

```bash
agentctl create research document-reviewer --name "Document Reviewer"
agentctl import "/pfad/zu/CampusHub/.agents/skills/document-reviewer" --area skills --preferred-harness codex --status active
agentctl register "/pfad/zu/CampusHub/projects/Automatismen/Mail" --area projects --agent-id campushub-mail-automation --preferred-harness codex
agentctl validate research.document_reviewer
agentctl catalog build
```

Der Import kopiert den Agentenordner nach `.agents/<area>/<agent-id>/` im lokalen Werkzeugkasten,
uebernimmt `SKILL.md`, `references/`, Skripte, Templates und Tests, laesst
virtuelle Umgebungen, Caches und Build-Artefakte aber aus. Aus dem `SKILL.md`
werden Name und Beschreibung uebernommen; `preferred_harness` ist beim Import
standardmaessig `codex`.

`register` ist fuer heterogene Quellen gedacht: vorhandene Projektordner,
einzelne Markdown-Agenten, HTML-Werkzeuge, Python-Skripte oder Harness-Konfigs.
Dabei wird eine saubere `agent.yaml`, `SKILL.md` und `README.md` in
`.agents` erzeugt. Grosse Projektordner bleiben am Ursprungspfad und
werden ueber `origin.source_paths`, `workspace` und `permissions` referenziert.
Mit `--copy-source` kann eine einzelne Quelle oder ein kleiner Agentenordner
zusaetzlich als Snapshot unter `source/` abgelegt werden.

## Einstellungen

In **Einstellungen -> Trinity-Ablagen** werden drei verschiedene Pfade gesetzt:
die lokale Runtime, der Cloud-Vault fuer dauerhafte Inhalte und die lokale
Agentenbasis. Die Agentenbasis ist der Ordner, der `.agents`, `AGENTS.md` und
optional `CLAUDE.md` enthaelt. Trinity liest ihn fuer Codex, Pi, OpenCode,
Antigravity und weitere Harnesses aus. Automatisch generierte Metadaten liegen
unter `.agents/_meta`. Der BrainVault bleibt davon getrennt und enthaelt keine
ausfuehrbaren Agenten.

Der `Standard-Harness fuer externe Agenten` steht initial auf `pi`. Codex
bleibt der Builder-Harness fuer neue Agenten, Imports, Refactorings, Tests und
Quality-Gates. Mit
**Agenten-Werkzeugkasten aktualisieren** wird `.agents` erneut gelesen, der Katalog
neu aufgebaut und jeder neue externe Agent ohne bestehende manuelle Zuordnung
diesem Standard-Harness zugewiesen. Die sichtbare Harness-Matrix wird dabei
direkt aktualisiert.

## Trinity-Agentenbuilder

Natuerliche Auftraege wie:

```text
Trinity, hier ist ein Agent aus Antigravity: "/pfad/zum/agenten".
Mach ihn fuer Trinity moeglich.
```

legen nun einen lokalen Entwurf unter `.agents/<bereich>/<agent-id>/` an. Der
Builder schreibt:

- `agent.yaml`
- `README.md`
- `SKILL.md`
- `manifest.json` als Kompatibilitaetsdatei fuer bestehende Trinity-Jobs
- `origin_snapshot/` mit relevanten Ursprungsdateien
- `README_IMPORT.md`
- `BUILDER_PLAN.md`
- `VALIDATION_REPORT.md`
- optional `HARNESS_REPORT.md`

Der Agent ist sofort sichtbar, aber nicht aktiv. Aktivierung erfolgt erst durch
Validierung und ausdrueckliches Setzen von `status: active` und `enabled: true`.

## Sicherheitsregeln

- Trinity-interne Agenten werden nicht in den externen Werkzeugkasten migriert.
- Externe Agenten werden nicht in Trinity-interne Agenten kopiert.
- Keine Originaldateien automatisch loeschen.
- Keine Duplikate blind zusammenfuehren.
- Vor Migrationen zuerst `agentctl audit` ausfuehren.
- Secret-Werte gehoeren nie in `agent.yaml`, Kataloge, Logs oder Git.
- Lokale Secret-Dateien gehoeren weder in den BrainVault noch in Git. Falls ein Agent
  Secret-Referenzen braucht, dann nur als Verweis, nicht als Klartextwert.
