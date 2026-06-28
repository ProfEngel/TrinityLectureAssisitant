# Trinity Agenten-Oekosystem

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
| Harness-Routing | implementiert | Einstellungen -> Harnesses buendelt Codex, Pi und OpenCode mit Rollen fuer Agentenbuilder, komplexe Faelle und Agenten-Ausfuehrung plus Agenten-Matrix. |
| Grafische Agentenkiste | implementiert | Einstellungen -> Agenten zeigt Tiers, Legacy-Skills, Staging und Konflikte. |
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

## Staging und Freigaben

Ein von OpenCode oder Codex entwickelter neuer Agent gehoert zuerst nach:

~~~text
skills/staging/<skill-id>/
~~~

Mindestens erforderlich:

~~~text
manifest.json
script.py oder workflow.yaml
tests/
README.md
~~~

Staging-Skills werden nicht in die Laufzeit geladen. Der vorgesehene
Erzeugungsauftrag soll sie ausschliesslich im Staging-Verzeichnis anlegen; die
vollstaendige technische Abschottung ueber den Tool Broker folgt in der naechsten
Phase. Nach erfolgreichem Testlauf erzeugt Trinity eine Freigabe. Nur eine
freigegebene, einmalig konsumierbare Promotion verschiebt ihn nach
skills/personal und aktiviert ihn.

Kind-Freigaben sind fuer mehrschrittige Aufgaben vorgesehen: Eine explizite
Eltern-Freigabe kann nur konkret benannte Folgeaktionen fuer denselben Job
erlauben. Eine Freigabe fuer einen Mail-Entwurf ist also keine Freigabe fuer
Loeschungen, Uploads oder andere Projekte.

## Terminal-Kontrolle

~~~bash
trinity skills list
trinity skills list --tier staging
trinity jobs list
trinity jobs show JOB_ID
trinity approvals list
trinity approvals approve APPROVAL_ID
trinity skills promote SKILL_ID --approval-id APPROVAL_ID
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
   ClassicUI, WebUI, iPhone, iPad und spaetere Android/Watch-Clients liefern.
6. Tool Broker in allen neuen Skills erzwingen und alte Skills schrittweise
   migrieren.

Die Reihenfolge ist absichtlich konservativ: Erst nachvollziehbare Jobs und
Freigaben, dann kontrollierte Tools und erst danach automatische Agent-Erzeugung
oder mobile Freigaben.
