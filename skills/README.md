# Trinity Agentenkiste

Die Agentenkiste trennt neue Fähigkeiten in drei lokale Tiers:

- **shared/**: geprüfte, allgemein nutzbare Skills. Sie werden nur lokal
  installiert und nicht automatisch verteilt.
- **personal/**: dauerhaft für diese Trinity-Installation aktivierte Skills.
- **staging/**: neue oder geänderte Skills aus Agent Forge, Codex oder OpenCode.
  Sie werden niemals automatisch geladen oder aktiviert.

Ein verwalteter Skill enthält mindestens:

~~~text
manifest.json
script.py oder workflow.yaml
tests/
README.md
~~~

Bestehende Agenten unter ../../agents/ bleiben als Legacy-Skills aktiv und
rückwärtskompatibel. Neue Skills sollen über das Manifest und die Promotion
in den Personal-Tier gelangen:

~~~text
Staging -> Tests -> Freigabe -> trinity skills promote -> Personal
~~~

Die CLI zeigt den Status:

~~~bash
trinity skills list
trinity skills list --tier staging
trinity jobs list
trinity approvals list
~~~
