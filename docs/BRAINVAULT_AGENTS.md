# BrainVault-Agenten

Ab v0.16.0 trennt Trinity zwei Agentenwelten strikt:

1. **Trinity-interne Agenten** bleiben im Trinity-Repository. Dazu gehoeren UI,
   STT/TTS, Memory, RAG, Medienfunktionen, Telegram, Companion, Timer,
   Vortragsfunktionen und Control-Plane-Logik.
2. **BrainVault-Agenten** sind externe, wiederverwendbare Fachagenten. Sie
   liegen kanonisch unter `BrainVault/.agents/` und koennen von Trinity, Codex,
   Pi, OpenCode, Claude Code, Antigravity und spaeteren Harnesses gelesen,
   getestet und erweitert werden.

Gleichnamige Agenten sind erlaubt. Intern unterscheidet Trinity nach `id`,
`source`, `execution_scope` und `path`.

## Ordnerstruktur

```text
BrainVault/
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
├── .ai/
│   ├── env/
│   ├── secrets/
│   ├── harnesses.yaml
│   └── models.yaml
├── .catalog/
│   ├── agent_catalog.json
│   ├── AGENT_CATALOG.md
│   └── agent_catalog.schema.json
├── AGENTS.md
└── CLAUDE.md
```

Nicht benoetigte Unterordner werden nicht kuenstlich angelegt. Die Quelle der
Wahrheit ist immer die jeweilige `agent.yaml`; JSON- und Markdown-Kataloge
werden daraus generiert.

## agent.yaml

Minimaler neuer Agent:

```yaml
id: research.thesis_reviewer
name: Thesis Reviewer
version: 0.1.0
source: brainvault
execution_scope: shared_harness
status: draft
enabled: false
path: .agents/research/thesis-reviewer
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

`agentctl` ist das kleine lokale Werkzeug fuer BrainVault-Agenten:

```bash
agentctl init
agentctl list
agentctl inspect <agent-id>
agentctl validate <agent-id>
agentctl catalog build
agentctl create <bereich> <agent-id>
agentctl audit <suchpfad> --output BRAINVAULT_AGENT_AUDIT.md
```

Beispiel:

```bash
agentctl create research thesis-reviewer --name "Thesis Reviewer"
agentctl validate research.thesis_reviewer
agentctl catalog build
```

## Trinity-Agentenbuilder

Natuerliche Auftraege wie:

```text
Trinity, hier ist ein Agent aus Antigravity: "/pfad/zum/agenten".
Mach ihn fuer Trinity moeglich.
```

legen nun einen BrainVault-Draft unter `.agents/<bereich>/<agent-id>/` an. Der
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

- Trinity-interne Agenten werden nicht nach BrainVault migriert.
- BrainVault-Agenten werden nicht in Trinity-interne Agenten kopiert.
- Keine Originaldateien automatisch loeschen.
- Keine Duplikate blind zusammenfuehren.
- Vor Migrationen zuerst `agentctl audit` ausfuehren.
- Secret-Werte gehoeren nie in `agent.yaml`, Kataloge, Logs oder Git.
- `.ai/env/*.env` und `.ai/secrets/*` werden durch `.ai/.gitignore`
  ausgeschlossen.
