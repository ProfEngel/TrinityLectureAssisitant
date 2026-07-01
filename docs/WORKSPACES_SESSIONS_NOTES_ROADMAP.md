# Trinity Arbeitsraeume, Sessions und Notizen

Status: geplanter grosser Arbeitsschritt ab vNext

Dieses Dokument legt die naechste Ordnungsschicht fuer Trinity fest. Ziel ist
nicht, Trinity in einen weiteren Chatbot zu verwandeln. Trinity soll mehrere
dauerhafte Arbeitskontexte halten koennen, waehrend Vorlesungen, Schreibprojekte,
Forschung, Bueroarbeit, Agentenbau und Medienerzeugung parallel nebeneinander
laufen duerfen.

## Zielbild

Trinity bekommt eine fachliche Struktur oberhalb einzelner Chatverlaeufe:

- **Arbeitsraeume** sind dauerhafte Kontexte wie `Vorlesung WInf1`,
  `Erendria`, `Forschungsprojekt`, `Buero`, `Agentenbau` oder `Schnellnotizen`.
- **Sessions** sind konkrete Arbeitsphasen innerhalb eines Arbeitsraums. Sie
  koennen aktiv, pausiert, geschlossen, zusammengefasst oder archiviert sein.
- **Schnellsessions** entstehen, wenn der Nutzer ohne Auswahl eines
  Arbeitsraums schnell eine neue Session startet, etwa vor einer Vorlesung.
  Sie landen zunaechst in einer Inbox und koennen spaeter verschoben werden.
- **Notizen** sind unabhaengige Wissens- oder Aktionsschnipsel. Sie koennen
  frei bleiben oder einem Arbeitsraum, einer Session, einem Job, einem Medium
  oder einer Quelle zugeordnet werden.
- **Summaries** werden nicht automatisch bei jedem Kontextwechsel erzeugt.
  Eine Summary entsteht manuell per Button, per Sprachbefehl oder durch eine
  explizite Arbeitsraum-Regel, z.B. fuer abgeschlossene Vorlesungseinheiten.

Damit kann der Nutzer z.B. am iPad eine Vorlesung halten, waehrend im
Arbeitsraum `Erendria` ein pausierter Schreibkontext bestehen bleibt und im
Arbeitsraum `Agentenbau` spaeter ein Codex- oder Pi-Job weitergefuehrt wird.

## Leitentscheidungen

1. **Sessions statt Threads.** Der Begriff `Session` bleibt, weil er besser zu
   Vorlesungen, Arbeitsphasen und Trinitys bestehendem Log- und Summary-Modell
   passt.
2. **Arbeitsraeume statt Chatlisten.** Arbeitsraeume sind fachliche Container,
   keine reinen Chat-Threads.
3. **Kein Pflicht-Summary beim Wechsel.** Der Wechsel von Erendria zur Vorlesung
   darf nicht automatisch eine Erendria-Summary erzwingen.
4. **Summary bewusst ausloesen.** Eine Session bekommt einen Button
   `Zusammenfassen`. Optional darf ein Arbeitsraum Regeln haben wie
   `Beim Schliessen zusammenfassen`.
5. **Schnellsessions bleiben leicht.** `Neue Session` darf sofort starten und
   muss keinen Dialog erzwingen. Spaeter kann die Session benannt und in einen
   Arbeitsraum verschoben werden.
6. **Notizen sind eigenstaendig.** Notizen duerfen ohne Session existieren und
   erst spaeter zugeordnet werden.
7. **Runtime bleibt lokal.** Aktive Sessions, Jobs, Locks, Datenbanken und
   temporaere Dateien bleiben in der lokalen TrinityRuntime.
8. **BrainVault bleibt Agenten- und Wissenspool.** Externe Agenten und
   freigegebene Wissensstrukturen liegen im Cloud-Ordner; aktive Runtime-Daten
   nicht.
9. **HITL bleibt Standard bei riskanten Aktionen.** Externe Harnesses duerfen
   planen, pruefen und bauen, aber Versand, Loeschung, Publishing, Aktivierung
   und Rechteausweitung brauchen Freigabe.

## Datenmodell

### Lokale Runtime-Struktur

```text
TrinityRuntime/
├── workspaces/
│   ├── _inbox/
│   │   └── workspace.json
│   └── <workspace_id>/
│       ├── workspace.json
│       ├── sessions/
│       │   └── <session_id>/
│       │       ├── session.json
│       │       ├── transcript.md
│       │       ├── events.jsonl
│       │       ├── summary.md
│       │       ├── media/
│       │       ├── jobs.jsonl
│       │       └── memory_links.json
│       ├── notes.jsonl
│       ├── media_index.jsonl
│       └── workspace_memory.jsonl
├── notes/
│   ├── notes.sqlite3
│   └── attachments/
├── jobs/
├── memory/
├── logs/
└── databases/
```

`_inbox` ist der Standard-Arbeitsraum fuer Schnellsessions, unzugeordnete
Notizen und unklare Eingaben.

### Workspace

```json
{
  "id": "workspace_winf1",
  "title": "Wirtschaftsinformatik 1",
  "kind": "lecture",
  "status": "active",
  "created_at": "2026-07-01T10:00:00Z",
  "updated_at": "2026-07-01T10:00:00Z",
  "default_summary_policy": "manual",
  "default_harness": "pi",
  "tags": ["lecture", "bachelor"],
  "brainvault_scope": null
}
```

`kind` kann z.B. `lecture`, `office`, `writing`, `research`, `agent_building`,
`personal`, `inbox` oder `custom` sein.

### Session

```json
{
  "id": "session_20260701_1015_winf1",
  "workspace_id": "workspace_winf1",
  "title": "20260701_1015_WInf1",
  "status": "active",
  "summary_status": "none",
  "started_at": "2026-07-01T10:15:00Z",
  "ended_at": null,
  "last_opened_at": "2026-07-01T10:15:00Z",
  "mode": "lecture",
  "inputs": ["ipad_stt", "desktop_chat"],
  "media_count": 0,
  "job_count": 0,
  "tags": []
}
```

Session-Status:

- `active`: gerade offen
- `paused`: unterbrochen, spaeter fortsetzbar
- `closed`: fachlich beendet
- `summarized`: Summary vorhanden
- `archived`: nicht mehr in der Hauptliste

Summary-Status:

- `none`
- `queued`
- `running`
- `done`
- `failed`
- `skipped`

### Notiz

```json
{
  "id": "note_20260701_1020_abc",
  "title": "Idee zu Kapitel 3",
  "body": "Kurznotiz...",
  "type": "idea",
  "status": "open",
  "workspace_id": "workspace_erendria",
  "session_id": null,
  "source": "voice",
  "tags": ["erendria", "plot"],
  "created_at": "2026-07-01T10:20:00Z",
  "updated_at": "2026-07-01T10:20:00Z"
}
```

Notiztypen:

- `free`
- `todo`
- `idea`
- `decision`
- `question`
- `source`
- `lecture_note`
- `agent_hint`

## Bedienlogik

### Neue Session

`Neue Session` startet sofort eine Schnellsession, wenn kein Arbeitsraum
ausgewaehlt ist. Der vorgeschlagene Name folgt weiterhin:

```text
YYYYMMDD_HHMM_
```

Beispiele:

- `20260701_1015_WInf1`
- `20260701_1430_Erendria_Kapitel3`
- `20260701_1805_Agentenbau_Mail`

Der Nutzer kann spaeter:

- die Session umbenennen,
- sie in einen Arbeitsraum verschieben,
- sie schliessen,
- eine Summary starten,
- sie archivieren.

### Zusammenfassung

Eine Summary wird ausgeloest durch:

- Button `Zusammenfassen`
- Sprachbefehl: `Trinity, fasse diese Session zusammen`
- CLI: `trinity session summarize <session-id>`
- optionale Arbeitsraum-Regel, z.B. `lecture_auto_summary_on_close=true`

Der Summary-Job laeuft im Hintergrund. Trinity bleibt bedienbar. Das Ergebnis
wird als Asset sichtbar und mit der Session verknuepft. Erst danach darf die
Summary in RAG/Memory aufgenommen werden.

### Notizen

Notizen koennen jederzeit entstehen:

- `Trinity, notiere: ...`
- `Trinity, lege eine Todo an: ...`
- per Button in Desktop/Web/iPad
- als Markierung aus einer Summary
- als Ergebnis eines Agentenjobs

Eine Notiz kann spaeter einem Arbeitsraum oder einer Session zugeordnet werden:

```text
Trinity, verschiebe diese Notiz in den Arbeitsraum Erendria.
Trinity, verknuepfe die Notiz mit der aktuellen Vorlesungssession.
```

## UI-Plan

### Desktop ClassicUI und WebUI

Neue Kopfleiste:

- Arbeitsraum-Auswahl
- Session-Auswahl
- `Neue Session`
- `Zusammenfassen`
- `Notiz`
- Status fuer laufende Jobs

Neue Hauptansichten:

- `Alltag`
- `Vortrag`
- `Web`
- `Chat`
- `Live`

Alle anderen Arbeitsobjekte wandern aus der oberen Tab-Leiste heraus. Die
Memory-/Graph-Ansicht gehoert perspektivisch in die Einstellungen, weil sie
Konfiguration, Diagnose und Langzeitgedaechtnis betrifft und nicht die taegliche
Arbeitsflaeche blockieren soll.

Der Chat bekommt stattdessen links eine Codex-aehnliche Arbeitsnavigation:

```text
Arbeitsraeume
├── Angeheftet
├── Notizen
├── Sessions
└── Summaries
```

Diese Navigation ist nicht als zweite Chatliste gedacht. Sie zeigt fachliche
Container und Unterobjekte:

- **Arbeitsraeume** statt Projekte
- **Angeheftet** fuer haeufig genutzte Arbeitsraeume/Sessions
- **Notizen** als arbeitsraumuebergreifende Inbox plus zugeordnete Notizen
- **Sessions** statt Chats, je Arbeitsraum gruppiert
- **Summaries** je Arbeitsraum und Session auffindbar

Die erste UI-Iteration darf diese Leiste zunaechst als stabiles Geruest zeigen.
Die Live-Datenbindung folgt nach dem `WorkspaceManager` und `SessionManager`.

Die aktuelle iPad-Logik bleibt Vorbild: gleiche Begriffe, gleiche Buttons,
moeglichst gleiche Positionen.

### iPad/iPhone Companion

Die Arbeitsorganisation ist kein Desktop-only-Element. ClassicUI, WebUI, iPad
und iPhone verwenden dieselbe Logik:

- ein Button in der oberen Leiste blendet die Arbeitsorganisation ein oder aus
- auf breiten Displays erscheint sie als linke Seitenleiste
- auf iPhone/kompakten Displays erscheint sie als seitliche Schublade ueber der
  aktuellen Ansicht
- die Leiste ist in allen Hauptansichten verfuegbar, nicht nur im Chat
- Inhalte sind identisch strukturiert: Arbeitsraeume, Angeheftet, Notizen,
  Sessions und Summaries
- die konkrete Datenbindung erfolgt nach `WorkspaceManager` und
  `SessionManager`

iPad:

- Arbeitsraum- und Session-Picker oben oder in einem kompakten Seitenpanel
- einklappbare linke Arbeitsorga-Leiste in Alltag, Vortrag, Web, Chat und Live
- aktuelle Vortragssession bleibt beim Wechsel zwischen Vortrag/Web/Chat offen
- Summary-Button pro Session
- Notizen-Button fuer freie Notizen waehrend der Vorlesung

iPhone:

- schlanke Ansicht: Arbeitsraum, aktuelle Session, Mikro, TTS, Chat
- einklappbare Arbeitsorga-Schublade statt dauerhaft sichtbarer Sidebar
- Schnellsession muss mit einem Tap starten koennen
- Medien und Summaries sessionuebergreifend abrufbar

### Terminal/CLI

```bash
trinity workspace list
trinity workspace create "Erendria" --kind writing
trinity workspace switch erendria

trinity session new --workspace erendria --title 20260701_1430_Kapitel3
trinity session list --workspace erendria
trinity session move SESSION_ID --to erendria
trinity session summarize SESSION_ID
trinity session close SESSION_ID

trinity notes add "Idee fuer Kapitel 3" --workspace erendria
trinity notes list --workspace erendria
trinity notes move NOTE_ID --workspace winf1
```

## Agenten- und Harness-Integration

Arbeitsraeume bekommen optionale Default-Werte:

- Standard-Harness fuer BrainVault-Arbeit, z.B. Pi
- Builder-Harness fuer Agentenbau, z.B. Codex
- erlaubte BrainVault-Bereiche
- erlaubte Tools/Rechte
- Summary- und Memory-Regeln

Beispiele:

```text
Trinity, im Arbeitsraum Erendria: pruefe die Kapitelstruktur.
Trinity, im Arbeitsraum Agentenbau: baue einen Steuerdaten-Agenten als Draft.
Trinity, im Arbeitsraum WInf1: erstelle aus der heutigen Session eine Zusammenfassung.
```

Routing-Regel:

- Bestehende BrainVault-Agentenarbeit geht an den Standard-Harness des
  Arbeitsraums, aktuell meist Pi.
- Neue Agenten, Agentenimport und Agentenueberarbeitung gehen an den
  Builder-Harness, aktuell Codex.
- Trinity bleibt Control Plane, UI, Memory, Freigabe- und Ergebnismanager.

## Umsetzung in Phasen

### Phase 1: Foundation

Ziel: stabile Daten- und CLI-Schicht ohne UI-Risiko.

Umfang:

- `core/workspace_manager.py`
- `core/session_manager.py`
- `core/notes_store.py`
- Runtime-Pfade unter `TrinityRuntime/workspaces/`
- Migration vorhandener Session-IDs in `_inbox`
- CLI-Kommandos fuer Workspaces, Sessions und Notes
- Tests fuer CRUD, Verschieben, Summary-Status und Pfadtrennung

Quality Gates:

- bestehende ClassicUI/WebUI/iPad-Bridge laufen unveraendert weiter
- keine automatische Summary beim Sessionwechsel
- Schnellsession landet in `_inbox`
- Runtime-Daten werden nicht in BrainVault geschrieben

### Phase 2: Session-Lifecycle

Ziel: die bestehende `Neue Session`-Logik wird an den Session-Manager
angebunden.

Umfang:

- Session-Namen weiterhin mit `YYYYMMDD_HHMM_`
- `Neue Session` erstellt Metadaten
- `Session verschieben`
- `Session schliessen`
- `Zusammenfassen` als manueller Button
- Summary-Asset an Session koppeln
- alter Auto-Summary-Flow wird auf explizite Regeln umgestellt

Quality Gates:

- Erendria-Session bleibt pausiert, wenn eine Vorlesungssession startet
- Summary laeuft im Hintergrund
- Zusammenfassung erscheint als Asset und bleibt spaeter abrufbar

### Phase 3: Notizen

Ziel: Notizen werden unabhaengig von Chats und Sessions nutzbar.

Umfang:

- globale Notiz-Inbox
- Notizen Arbeitsraeumen/Sessions zuordnen
- Todo/Idee/Entscheidung/Frage als Typen
- Notizen in ClassicUI/WebUI/iPad sichtbar
- optionaler Import bestehender `memory/notes/`

Quality Gates:

- Notiz ohne Session moeglich
- spaeteres Verschieben moeglich
- keine Vermischung mit normalem Chatverlauf

### Phase 4: UI-Vereinheitlichung

Ziel: ClassicUI, WebUI und Companion fuehlen sich gleich an.

Umfang:

- Arbeitsraum-/Session-Kopfbereich
- einheitliche Buttons fuer `Neue Session`, `Zusammenfassen`, `Notiz`
- obere Haupttabs nur noch `Alltag`, `Vortrag`, `Web`, `Chat`, `Live`
- `Presenter` wird als eigene Hauptansicht entfernt; grosse Medien bleiben als
  Overlay/Asset in Alltag, Vortrag oder Chat sichtbar
- Memory-/Graph-Ansicht wandert aus `Live` in die Einstellungen
- einklappbare linke Arbeitsnavigation nach Codex-Vorbild in allen Ansichten
- Arbeitsraumliste
- Sessionliste mit Status je Arbeitsraum
- Summary-Badge
- Notizen- und Summary-Gruppen in der linken Arbeitsnavigation

Quality Gates:

- iPad-Vortragsansicht behaelt geoeffnete PDF/HTML beim Moduswechsel
- iPhone bleibt schlank
- Desktop/WebUI uebernehmen dieselbe Kernlogik

### Phase 5: Cross-Workspace-Jobs

Ziel: Trinity kann Hintergrundaufgaben in anderen Arbeitsraeumen starten, ohne
den aktuellen Arbeitsraum zu unterbrechen.

Umfang:

- Job-Queue pro Arbeitsraum
- Status-Badges
- Ergebniszuordnung zu Arbeitsraum/Session
- Freigaben pro Arbeitsraum
- Harness-Routing pro Arbeitsraum

Quality Gates:

- Vorlesung bleibt bedienbar, waehrend Erendria-Job laeuft
- keine unbemerkten Schreibaktionen ausserhalb erlaubter Pfade
- Ergebnisse landen im richtigen Arbeitsraum

### Phase 6: Memory und RAG pro Arbeitsraum

Ziel: Trinity erinnert kontextsensitiv, ohne alles in einen globalen Brei zu
mischen.

Umfang:

- Workspace-spezifische Memory-Sicht
- Session-Summaries als Memory-Kandidaten
- Notizen als Memory-Kandidaten
- manuelle Aufnahme ins Langzeitgedaechtnis
- Graph-Ansicht nach Arbeitsraum filterbar

Quality Gates:

- Frage in Erendria zieht Erendria-Kontext vor
- Vorlesungsfrage zieht Vorlesungskontext vor
- globale Suche bleibt moeglich, aber sichtbar als globale Suche markiert

## Erste konkrete Implementierungsaufgabe

Der erste echte Code-Schritt sollte bewusst klein bleiben:

1. `WorkspaceManager` und `SessionManager` bauen.
2. `_inbox` automatisch anlegen.
3. `trinity workspace list/create` und `trinity session new/list/move` ergaenzen.
4. Tests fuer Pfade, Metadaten und Verschieben schreiben.
5. Noch keine UI umbauen.

Danach kann der bestehende `Neue Session`-Button sicher auf die neue Schicht
umgestellt werden.

## Nicht-Ziele fuer den ersten Schritt

- keine grosse UI-Umstellung im ersten Commit
- keine automatische Migration aller alten Memory-Dateien
- keine parallele Job-Orchestrierung im ersten Schritt
- keine Aenderung am Pi-/Codex-Routing ausser der spaeteren Zuordnung pro
  Arbeitsraum
- kein Schreiben aktiver Runtime-Daten in BrainVault

## Offene Entscheidungen

- Soll ein Arbeitsraum mehrere aktive Sessions erlauben oder genau eine aktive
  und mehrere pausierte?
- Soll eine Vorlesungssession beim App-Neustart automatisch fortgesetzt werden
  oder nur vorgeschlagen werden?
- Wie lange bleiben Schnellsessions in `_inbox`, bevor Trinity ans Aufraeumen
  erinnert?
- Welche Notiztypen sollen im ersten UI sichtbar sein und welche nur intern?
- Soll die Arbeitsraum-Summary spaeter mehrere Session-Summaries verdichten?

Die konservative Empfehlung lautet: erst einfache, robuste lokale Datenhaltung,
dann manuelle Bedienung, dann intelligente Automatik.
