# Trinity Agenten-Oekosystem

Status: technisches Bestandsdokument. Die aktuelle Restereihenfolge und die
verbindlichen Profil-/Vault-Regeln stehen in
`IMPLEMENTIERUNGSPLAN_TRINITY.md` und
`PHASE_1_PROFILE_ARCHITECTURE.md`.

Dieses Dokument beschreibt den technischen Entwicklungsstand der neuen
dreigeteilten Agentenkiste. Es ergaenzt [Onboarding](ONBOARDING.md): Dort steht
die Einrichtung, hier stehen Architektur, Sicherheitsgrenzen und die offenen
vNext-Phasen.

## Bereits implementiertes Fundament

| Baustein | Status | Verhalten |
|---|---|---|
| Shared / Personal / Staging | implementiert | Verzeichnisse unter skills/ und eine Registry mit Manifest-Validierung. |
| Legacy-Adapter | implementiert | Bestehende agents/*/script.py bleiben aktiv und unveraendert nutzbar. |
| Staging-Schutz | implementiert | Staging-Skills werden nie automatisch geladen oder aktiviert. |
| Promotion | implementiert | Erfordert Manifest, vorhandene Tests, Erzeugungsjob und eine einmalig nutzbare activate_skill-Freigabe. |
| Job Manager | implementiert | Nicht-triviale Auftraege erhalten persistente Schritte, Status, Quality Gates und Abschlussberichte in memory/jobs.sqlite3. |
| Approval Manager | implementiert | Lokale, zeitlich begrenzte Freigaben; Eltern-Freigaben koennen eng begrenzte Kind-Aktionen erlauben. |
| Policy Engine | implementiert | Paketinstallation und unbekannte Systemaktionen sind standardmaessig blockiert; Versand, Loeschung, Upload, Publikation und Skill-Aktivierung verlangen Freigabe. |
| Task Orchestrator | implementiert | Codex-, OpenCode-, Agent-Forge- und umfangreiche Auftraege bekommen vor dem Start einen Plan und Job. |
| Harness-Routing | implementiert | Einstellungen -> Harnesses buendelt Trinity, Codex, Pi und OpenCode mit Rollen fuer Agentenbuilder, komplexe Faelle und Agenten-Ausfuehrung plus Agenten-Matrix. |
| Grafischer Agentenkatalog | implementiert | Einstellungen -> Agenten zeigt Trinity, Agentenbuilder, Shared/Personal/Staging- und Legacy-Agenten samt Reifegrad, Runtime-Status, Rechten, Pfaden, Freigaben, Lauf-/Parallelitaetslimits und Jobzahlen. |
| CLI | implementiert | trinity skills, trinity jobs und trinity approvals machen Status und Freigaben kontrollierbar. |

## Mehrere voneinander getrennte Projektordner

Ja: Codex und OpenCode akzeptieren jeweils beliebig viele Projekt-Aliasse.
Jede Zeile in den Codex- und OpenCode-Bloecken unter
Einstellungen -> Harnesses hat dieses Format:

~~~text
Trinity = /Users/NAME/.../Trinity_Assistant
Hochschulprojekte = /Users/NAME/.../Hochschulprojekte
Erendria = /Users/NAME/.../Erendria
~~~

Ein Auftrag nennt immer beides, Tool und Alias:

~~~text
Trinity, nutze Codex im Projekt Trinity und pruefe die Agententests.
Trinity, nutze OpenCode im Projekt Hochschulprojekte und starte den dortigen Workflow.
Trinity, nutze Codex im Projekt Erendria und pruefe die Kapitelstruktur.
~~~

Trinity arbeitet dann nur im jeweils freigegebenen Ordner. Es gibt keine
automatische Verbindung, gemeinsame Projekt-Memory oder Dateifreigabe zwischen
den Alias-Projekten. Das Standardprojekt dient nur als klarer Fallback, wenn ein
Auftrag keinen Alias nennt.

## Planung und Quality Gates

Nicht jede Antwort braucht einen Plan. Bildgenerierung, eine kurze Erklaerung
oder ein Timer bleiben direkt. Folgende Auftraege werden als nicht-trivial
behandelt und bekommen einen lokalen Job:

- ausdrueckliche Codex- oder OpenCode-Auftraege
- Agent-Forge-Auftraege
- mehrschrittige Workflows mit Projekt-, Test-, Mail-, Dokument- oder
  Automationsbezug

Der Standardplan enthaelt:

1. Auftrag, Projekt und Grenzen pruefen.
2. Delegierten Agenten oder lokalen Workflow ausfuehren.
3. Ergebnis und Tests gegen den Auftrag pruefen.
4. Abschlussbericht, Artefakte und Auditdaten speichern.

Der Job speichert dabei nicht nur "fertig", sondern die einzelnen Schritte und
ihre Quality Gates. Ein fehlgeschlagener Lauf kann danach bewusst lokal
wiederholt oder in einer spaeteren Phase mit einem reproduzierbaren
Eskalationspaket an Codex uebergeben werden.

## BrainVault-Drafts und Freigaben

Ein von Trinity, Codex, Pi, OpenCode, Claude Code oder Antigravity entwickelter
externer Fachagent gehoert ab v0.16.0 direkt nach:

~~~text
Lokaler-Agenten-Werkzeugkasten/.agents/<bereich>/<agent-id>/
~~~

Mindestens erforderlich:

~~~text
agent.yaml
SKILL.md
README.md
~~~

Neue Agenten werden sofort als `status: draft` und `enabled: false` im
BrainVault-Katalog sichtbar. Sie werden nicht in `skills/staging`,
`skills/personal` oder `skills/shared` dupliziert. Nach erfolgreichem Testlauf
und Freigabe wird direkt in `agent.yaml` auf `status: active` und
`enabled: true` umgestellt. Das alte Staging-/Promotion-Modell bleibt nur noch
als Kompatibilitaetsmechanismus fuer Trinity-interne Skills und Altdaten
erhalten.

Kind-Freigaben sind fuer mehrschrittige Aufgaben vorgesehen: Eine explizite
Eltern-Freigabe kann nur konkret benannte Folgeaktionen fuer denselben Job
erlauben. Eine Freigabe fuer einen Mail-Entwurf ist also keine Freigabe fuer
Loeschungen, Uploads oder andere Projekte.

## Agentenkatalog und Harness-Matrix

Seit v0.15.2 gibt es zwei bewusst getrennte Einstellungsbereiche:

- **Einstellungen -> Agenten:** Der Katalog zeigt jeden bekannten Agenten. Dort
  werden Reifegrad, erlaubte Tools/Rechte, erlaubte Pfade, explizite Freigaben,
  maximale Wiederholungen und parallele Laeufe gepflegt. Ein noch nicht
  erprobter Agent kann nach echten Tests auf "erprobt" oder "stabil" gesetzt
  werden.
- **Einstellungen -> Harnesses:** Die Matrix legt fest, welcher Ausfuehrer
  welchen Agenten starten darf. Trinity ist sichtbar, weil die Standard-Agenten
  und die Control Plane bei Trinity selbst liegen. Codex, Pi und OpenCode werden
  nur dort angehakt, wo sie wirklich passende Worker sind.

Externe Werkzeugkasten-Agenten, Trinity-interne Skills und vorhandene Legacy-Agenten tauchen
automatisch in den Listen auf. Das verhindert Dupletten: Der Katalog verwaltet
Status und Rechte, die Matrix verwaltet die technische Ausfuehrung.

Der Agentenbuilder ist als Trinity-interner Skill vorhanden. Er ist absichtlich
freigabeorientiert: Er formuliert Anforderung, Plan, Quality Gates, Draft-Bau,
Validierung und Release-Schritt, aktiviert produktiven Code aber erst nach einer
expliziten Freigabe.

## Agenten importieren, erstellen und erweitern

Der Agentenbuilder versteht drei praktische Auftragsklassen:

~~~text
Trinity, baue einen neuen Agenten fuer ...
Trinity, hol Dir diesen Agenten "/vollstaendiger/Pfad/zum/Agentenordner"
Trinity, erweitere den Agenten ... um ...
~~~

Ein Import kopiert nicht blind Code in die produktive Laufzeit. Stattdessen wird
unter `.agents/<bereich>/<agent-id>/` im lokalen Werkzeugkasten ein Draft-Agent erzeugt:

- `agent.yaml` als Quelle der Wahrheit,
- `manifest.json` als Kompatibilitaetsdatei fuer bestehende Trinity-Jobs,
- `origin_snapshot/` mit relevanten Markdown-, JSON/YAML-, Python- und
  Konfigurationsdateien,
- `README.md` und `SKILL.md`,
- `README_IMPORT.md` als Importbericht,
- `BUILDER_PLAN.md` und `VALIDATION_REPORT.md` fuer den sichtbaren Builder-Loop,
- ein Platzhalter-`script.py`, das vor produktiver Aktivierung bremst,
- ein Smoke-Test als Minimal-Quality-Gate.

Subagenten werden als Unterordner erkannt, wenn dort typische Marker wie
`README.md`, `agent.md`, `workflow.yaml` oder `script.py` liegen. Im
Agentenkatalog erscheinen diese Subagenten in der Hinweis-Spalte des importierten
Hauptagenten. Erst nach echten Tests und Freigabe wird der Draft aktiv.

Der Builder-Loop arbeitet jobbasiert. Er markiert die Draft-Erstellung,
lokale Quality-Gates, optionales Harness-Feedback und die Freigabevorbereitung
als einzelne Schritte im Trinity-Jobmanager. Wenn Codex, Pi oder OpenCode in den
Harness-Einstellungen aktiviert sind und fuer die passende Rolle freigegeben
wurden, kann Trinity sie fuer Feedback oder Nacharbeit am lokalen Agentenordner
aufrufen. Der Loop darf dabei nicht automatisch aktivieren; dafuer bleibt
`activate_skill` als Freigabe notwendig.

## Terminal-Kontrolle

~~~bash
trinity skills list
agentctl list
agentctl inspect AGENT_ID
agentctl validate AGENT_ID
agentctl catalog build
trinity jobs list
trinity jobs show JOB_ID
trinity approvals list
trinity approvals approve APPROVAL_ID
~~~

## Noch offene vNext-Phasen

Die folgenden Punkte aus openpoints.md sind bewusst noch nicht als oberflaechlich
unvollstaendiges System aktiviert:

1. Tool Broker: Neue Skills sollen Dateisystem, Shell und Netz nur noch ueber
   kontrollierte ExecutionContext-Adapter verwenden.
2. Agent Forge: Spezifikationsdialog, Staging-Erzeugung und automatischer
   Testlauf fuer neue Skills.
3. Eskalationspakete: Nach zwei echten fehlgeschlagenen Build-/Test-Zyklen
   reproduzierbare Pakete fuer Codex erstellen.
4. Artefakt-, Knowledge- und Projekt-Memory-Manager: getrennte Projektkontexte
   mit Hashes, Herkunft und Zugriffskontrolle.
5. Notification Bus und Gateway API: Jobs, Freigaben und Skill-Status an
   ClassicUI, WebUI, iPhone und iPad liefern.
6. Tool Broker in allen neuen Skills erzwingen und alte Skills schrittweise
   migrieren.

Die Reihenfolge ist absichtlich konservativ: Erst nachvollziehbare Jobs und
Freigaben, dann kontrollierte Tools und erst danach automatische Agent-Erzeugung
oder mobile Freigaben.
