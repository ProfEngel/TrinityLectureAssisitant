# BrainVault Agent Migration Report

Stand: 2026-06-29

## Ergebnis dieses Releases

Dieses Release fuehrt die BrainVault-Agentenbasis ein, migriert aber bewusst
keine privaten BrainVault-, CampusHub- oder Ideaverse-Agenten automatisch.
Grund: Der Auftrag verlangt vor jeder echten Konsolidierung eine
Bestandsaufnahme, Duplikatpruefung und Herkunftsdokumentation. Automatisches
Kopieren oder Loeschen ohne Audit waere nicht reversibel genug.

## Zahlen

- Gefundene Agentenkandidaten: nicht live gescannt
- Migrierte Agenten: 0
- Zusammengefuehrte Duplikate: 0
- Trinity-interne Agenten bewusst nicht migriert: alle bestehenden Trinity-Repo-Agenten
- Neu erzeugte Agentenstruktur: `BrainVault/.agents`, `.ai`, `.catalog`,
  `AGENTS.md`, `CLAUDE.md`
- Nicht eindeutige Faelle: alle externen Bestandsagenten bis zur Ausfuehrung
  von `agentctl audit`

## Neu erzeugte technische Struktur

```text
BrainVault/
├── .agents/
├── .ai/
├── .catalog/
├── AGENTS.md
└── CLAUDE.md
```

Neue externe Agenten werden direkt angelegt unter:

```text
BrainVault/.agents/<bereich>/<agent-id>/
```

Erforderliche Kerndateien:

```text
agent.yaml
SKILL.md
README.md
```

## Validierung

Ausgefuehrt:

```bash
python3 -m pytest -q tests/test_brainvault_agents.py tests/test_agent_builder_skill.py tests/test_agent_ecosystem.py tests/test_agent_catalog.py tests/test_control_plane.py
git ls-files 'tests/test*.py' | xargs python3 -m pytest -q
python3 agentctl.py --vault-root "$TMP/MainHub" init
python3 agentctl.py --vault-root "$TMP/MainHub" create research smoke-agent --name "Smoke Agent"
python3 agentctl.py --vault-root "$TMP/MainHub" validate research.smoke_agent
python3 agentctl.py --vault-root "$TMP/MainHub" catalog build
```

Ergebnis:

- Zieltests: bestanden
- Getrackte Gesamttests: bestanden
- `agentctl` Smoke-Test: bestanden

Bekannte Testumgebung-Warnung:

- `urllib3` meldet auf dem aktuellen macOS-Python eine LibreSSL-Warnung. Das ist
  unveraendert und betrifft nicht die neue BrainVault-Agentenlogik.

## Bekannte Einschraenkungen

- Bestehende externe Agenten wurden noch nicht automatisch konsolidiert.
- `agentctl audit` erzeugt den Auditbericht, muss aber fuer die gewuenschten
  BrainVault-/CampusHub-/Ideaverse-Pfade separat ausgefuehrt und fachlich
  geprueft werden.
- Die UI trennt BrainVault-Agenten bereits technisch im Katalog (`tier=brainvault`);
  eine visuell getrennte Zwei-Listen-Ansicht kann darauf aufbauen.
- Das alte `shared/personal/staging`-System bleibt fuer Trinity-interne Skills
  und Altdaten kompatibel vorhanden.

## Empfohlene naechste Schritte

1. `agentctl audit <BrainVault/CampusHub/Ideaverse-Pfade>` ausfuehren.
2. `BRAINVAULT_AGENT_AUDIT.md` fachlich pruefen.
3. Eindeutige externe Agenten schrittweise nach `BrainVault/.agents` uebernehmen.
4. Nach jedem Agenten `agentctl validate <agent-id>` und `agentctl catalog build`
   ausfuehren.
5. Erst nach Tests in `agent.yaml` auf `status: active` und `enabled: true`
   setzen.
