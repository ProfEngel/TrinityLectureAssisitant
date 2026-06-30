# Trinity Onboarding

Dieses Dokument ist der zentrale Einstieg fuer Trinity auf macOS, Windows 11,
Linux-Servern sowie mit der optionalen iPhone/iPad-Companion-App. Es fuehrt von
der ersten lokalen Antwort bis zu proaktiven Vorlesungs-Workflows und lokalen
Codex-/Pi-/OpenCode-Projekten.

## 1. Vor dem Start

Trinity besteht aus drei bewusst getrennten Ebenen:

| Ebene | Aufgabe | Beispiele |
|---|---|---|
| Betriebsmodus | Legt die Interaktionslogik fest. | lecture, office, chat |
| Oberflaeche | Legt fest, wo Trinity sichtbar und bedienbar ist. | Augen-UI, ClassicUI, Terminal, WebUI |
| Geraeterolle | Legt fest, welches Geraet Eingabe, Ausgabe oder Server ist. | Desktop, Linux-Server, iPhone/iPad-Companion |

Der Betriebsmodus ist also keine UI-Auswahl: Ein Vortrag kann beispielsweise im
Lecture-Modus mit Augen-UI, ClassicUI, WebUI oder iPad-Companion stattfinden.

### Voraussetzungen

- macOS oder Windows 11 fuer den vollstaendigen Desktop-Betrieb; Ubuntu/Linux
  eignet sich als Headless-Server mit WebUI.
- Ein erreichbares LLM: lokal etwa LM Studio/Ollama oder ein konfigurierter
  Remote-Provider.
- Ein Mikrofon nur fuer Sprachbetrieb; fuer ClassicUI, WebUI und TUI reicht Text.
- Fuer die Companion-App: iPhone/iPad, Desktop- oder Server-Trinity und im
  empfohlenen Fall Tailscale auf beiden Geraeten.
- Optional: Tavily fuer Webrecherche, fal.ai oder ComfyUI fuer Medien, Codex CLI,
  Pi CLI und/oder OpenCode CLI fuer lokale Projekt-Automationen.

Nach jeder Installation pruefen:

~~~bash
trinity doctor
trinity start
~~~

trinity doctor --fix darf nur fuer die angezeigten, lokalen Reparaturen verwendet
werden. Zugangsdaten, Bearer-Token und API-Keys gehoeren nie in Screenshots,
Chats, Issues oder Git-Repositories.

## 2. Installation und erste Antwort

### macOS

~~~bash
curl -sSL https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/install_mac.sh | bash
trinity onboarding
trinity doctor
trinity start
~~~

### Windows 11

In PowerShell:

~~~powershell
Set-ExecutionPolicy -Scope Process Bypass
irm https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/install_windows.ps1 | iex
trinity onboarding
trinity doctor
trinity start
~~~

Die Ausfuehrungsrichtlinie gilt damit nur fuer das geoeffnete PowerShell-Fenster.
Weitere Hinweise stehen in [Deployment Windows 11](Deployment_Windows11.md).

### Linux / Ubuntu Server

~~~bash
curl -sSL https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/install_linux.sh | bash
~/.local/bin/trinity onboarding
~/.local/bin/trinity doctor
~/.local/bin/trinity server --host 127.0.0.1 --port 8765
~~~

Linux startet bewusst ohne lokale Augen-UI und ohne lokalen Audioeingang. Es
liefert die WebUI und kann von Desktop-Clients oder der Companion-App genutzt
werden. Details: [Deployment Linux](Deployment_Linux.md).

### LLM einrichten

Nutze die ClassicUI ueber das Zahnrad oder im Terminal:

~~~bash
trinity settings
~~~

Unter APIs/LLM wird ein Provider-Slot gewaehlt und mit URL, Modell und bei Bedarf
API-Key konfiguriert. Fuer einen lokalen LM-Studio-Server ist der
Standardanschluss typischerweise http://localhost:1234/v1/chat/completions.
Erst wenn trinity doctor den LLM-Zugang bestaetigt, sollte STT, Medien oder
Proaktivitaet aktiviert werden.

## 3. Lokale Runtime und BrainVault-Agentenpool

Beim ersten `trinity onboarding` fragt Trinity nach zwei Speicherorten:

| Ort | Aufgabe | Darf in die Cloud? |
|---|---|---|
| **Lokale Runtime** | laufende Jobs, Queues, aktive Workspaces, SQLite-Datenbanken, Cache, temporaere Dateien, Logs, Locks und Secrets | Nein |
| **BrainVault / Cloud-Agentenpool** | freigegebene externe Agenten, Kataloge, Harness-Regeln, Vorlagen, Wissensbestaende und Ergebnisse | Ja |

Der Grund ist schlicht: Synchronisierte Cloud-Ordner koennen Dateien sperren,
umbenennen, verzögert schreiben oder auf einem anderen Gerät gleichzeitig
anfassen. Fuer laufende Jobs und SQLite-Datenbanken ist das eine schlechte Idee.
Der BrainVault darf dagegen bewusst in iCloud, OneDrive, Google Drive, Dropbox
oder einem anderen Sync-Ordner liegen. Massgeblich ist heute der BrainVault-Root,
also der Ordner, der `.agents`, `AGENTS.md` und optional `CLAUDE.md` enthaelt.
Automatisch generierte Katalogdaten liegen unter `.agents/_meta`, nicht als
zusaetzliche Top-Level-Ordner. Alte `MainHub/TrinityVault`-Strukturen sind nicht
mehr der Normalpfad und koennen archiviert werden, sobald die Einstellungen auf
den BrainVault-Root zeigen.

Generisches Beispiel:

~~~bash
trinity control-plane init \
  --runtime-root "/lokaler/pfad/zu/TrinityRuntime" \
  --vault-root "/cloud/pfad/zu/BrainVault"
~~~

Status und Agentenpool pruefen:

~~~bash
trinity control-plane status
agentctl list
~~~

Eine gesunde Ausgabe zeigt `warnings: []`, den lokalen Runtime-Pfad und den
BrainVault-Pfad. `agentctl list` sollte die externen Agenten aus
`BrainVault/.agents` anzeigen. Wenn eine Warnung sagt, dass die Runtime in
iCloud/OneDrive/Google Drive liegt, sollte der Runtime-Pfad auf einen lokalen
Ordner umgestellt werden.

Rueckrollen ist einfach: Die bestehende Trinity-Version bleibt als GitHub-Release
erreichbar. Lokal kann die Control Plane deaktiviert werden, indem
`control_plane.enabled` in den Einstellungen ausgeschaltet oder die Installation
auf einen aelteren Release-Tag zurueckgesetzt wird. Der BrainVault enthaelt
keine aktiven Runtime-Datenbanken und kann daher liegen bleiben, bis man ihn
wirklich nicht mehr braucht.

## 4. Oberflaechen und Terminal

In Einstellungen -> System -> Bedienoberflaechen koennen Oberflaechen frei
kombiniert werden:

- **Augen-UI:** dezente, schwebende Vorlesungsoberflaeche und Datei-Drop.
- **ClassicUI:** Chat, Anlagen, Live-Mitschrift/Agentenlog, Memory Graph und
  Einstellungen im gleichen Fenster.
- **Terminal/TUI:** robust fuer Headless, SSH und Diagnose. trinity tui bietet
  Sessions, Memory und Slash-Commands.
- **WebUI:** Browser-Chat fuer Server, Client oder Desktop. Start mit
  trinity start --surface web. Die Schaltflaeche Einstellungen oeffnet dieselben
  zentralen Konfigurationsbereiche wie die ClassicUI: LLM, Persona, Sprache,
  Oberflaechen, Codex/OpenCode, Companion, Server sowie Soul/User. Ohne Token
  ist sie nur auf localhost erreichbar; mit Server-Accounts nur fuer Admins.

trinity start --surface all startet alle Oberflaechen. Sind Augen-UI, ClassicUI
und WebUI deaktiviert, bleibt die Terminal-CLI als bedienbarer Fallback aktiv.

Einstellungen fuer LLM, Persona, Sprache, TTS, Telegram und Betriebsmodus werden
bei neuen Anfragen neu eingelesen. Ein Neustart ist nur fuer eine geaenderte
Oberflaechenkombination oder die Companion Bridge erforderlich.

Seit v0.15.3 haben ClassicUI und Einstellungsfenster zusaetzlich schnelle
Desktop-Schalter fuer **Zuhoeren** und **Sprechen**. Damit kann der Mac oder
Windows-PC sofort stumm geschaltet werden, wenn parallel iPad/iPhone, Telegram
oder ein anderes Trinity-Frontend aktiv ist. Das verhindert, dass Trinity ihre
eigene Sprachausgabe wieder als neuen Auftrag hoert.

## 5. Betriebsmodi und Einsatzstufen

### Lecture-Modus: Vorlesung und Praesentation

Der Lecture-Modus nutzt das Wake-Word und ist fuer eine moeglichst unaufdringliche
Begleitung ausgelegt.

| Stufe | Aktivierung | Was Trinity tut |
|---|---|---|
| **Level 1 - Zuhoeren** | Lecture, STT aktiv, Heartbeat aus | Schreibt lokal mit, reagiert auf ausdrueckliche Wake-Word-Anfragen und kann kurz antworten. |
| **Level 2 - Auf Zuruf handeln** | Zusaetzlich Medien-, Recherche-, Timer-, Simulation- oder Sandbox-Agenten nutzen | Erstellt auf ausdruecklichen Befehl Schaubilder, Rechercheergebnisse, Python-Ausgaben, Timer, Simulationen oder lokale Medien. Ergebnisse erscheinen in der passenden UI und auf Companion/Presenter, sofern verbunden. |
| **Level 3 - Proaktiver Begleiter** | Einstellungen -> Proaktiv: Heartbeat aktivieren; optional Bubbles, Visuals und Auto-RAG | Analysiert das Transkript periodisch auf Fehler, Perspektiven oder Uebungen und meldet Befunde als Bubble/Payload. Der Heartbeat erzeugt zusaetzliche LLM-Anfragen und sollte erst nach einem stabilen Level-1-Test aktiviert werden. |

Fuer sensible Situationen kann mit Formulierungen wie "Trinity, bitte nicht
zuhoeren" in einen passiven Fokusmodus gewechselt werden. Wichtig: Das physische
Mikrofon oder die Aufnahmeberechtigung des Betriebssystems bleibt die technische
Quelle; vor einer Veranstaltung sind Datenschutz- und Einwilligungsregeln der
Institution zu pruefen.

### Office-Modus: Dateien, Recherche und lokale Arbeit

Der Office-Modus eignet sich fuer vorbereitende Arbeit, Dokumente und
Automationen. ClassicUI und WebUI unterstuetzen Text-, PDF-, Bild- und
Tabellenanlagen. In der Augen-UI kann eine Datei abgelegt werden; Trinity zeigt
eine Vorschau oder oeffnet sie mit dem Standardprogramm und behaelt sie als
Kontext fuer den naechsten Auftrag.

Typische Aufgaben sind Zusammenfassungen, RAG-Abfragen, Webrecherche,
Schaubilder, Python-Berechnungen sowie lokale Codex-/OpenCode-Workflows. Fuer
eingehende E-Mails, Dateien mit personenbezogenen Daten oder Noten gelten immer
die lokalen Projektregeln und institutionellen Datenschutzvorgaben.

### Chat-Modus: bewusst auf Anforderung

Der Chat-Modus ist fuer ClassicUI, WebUI, TUI und Headless-Betrieb gedacht.
Er verarbeitet Text und Anlagen gezielt; der Heartbeat wird nicht gestartet.
Agenten bleiben moeglich, werden aber nur durch klare Auftraege ausgeloest. Das
ist der beste Modus, um LLM-, Anlagen- und Code-Integrationen einzeln zu testen.

## 6. Companion: iPhone und iPad

Die Companion-App ist absichtlich nicht Teil der Desktop-Installer. Sie ist ein
separates iOS/iPadOS-Projekt und verbindet sich mit einer laufenden
Desktop-/Server-Trinity per lokaler HTTP-Bridge.

### Empfohlenes privates Setup mit Tailscale

1. Tailscale auf dem Trinity-Host und dem iPhone/iPad anmelden.
2. In Trinity Einstellungen -> System -> Companion Bridge oeffnen.
3. Bridge beim Trinity-Start oeffnen aktivieren.
4. Host 0.0.0.0, einen freien Port (typisch 8765) und einen langen Bearer Token
   setzen.
5. Trinity neu starten.
6. In der Companion-App http://TAILSCALE-IP:8765 und denselben Token eintragen.

Bei Tailscale muss normalerweise kein Router-Port ins Internet geoeffnet werden.
Die lokale Firewall darf Trinity/Python nur in privaten Netzen beziehungsweise im
Tailnet akzeptieren. Eine Bridge mit 0.0.0.0 ohne Token darf nicht ungeschuetzt
ins oeffentliche Internet gestellt werden.

### Geraeterollen

- **iPhone:** mobiles STT, Fluestern/Text, Kamera/Anlagen und lokales TTS.
- **iPad:** Alltags-, Chat-, Presenter-, Vortrags- und Webansicht; geeignet fuer
  Folien, Annotationen und Medienpraesentation.
- **Desktop oder Linux-Server:** LLM, Agenten, Dateien, Mediengenerierung,
  Memory und Bridge.

Die Companion-App kann Chat, Live-Mitschrift, Bilder, Audio, Video, Timer,
Simulationen und Python-/Sandbox-Ergebnisse darstellen. iOS/iPadOS kann
Hintergrund-Spracherkennung systembedingt begrenzen; ein sichtbarer Vordergrund-
oder Split-View-Betrieb ist fuer laengere Vortraege robuster.

Android Tablet/Phone ist als zukuenftige Companion-Variante vorgesehen. Es gibt
in diesem Repository noch keinen Android-Installer oder Android-Client.

## 7. Lokale Codex-, OpenCode- und Pi-Agenten

Diese Integrationen sind absichtlich keine allgemeinen Fernsteuerungen des
Rechners. Trinity uebergibt nur explizit genannte Auftraege an zuvor freigegebene
Projektordner. Jede Ausfuehrung bleibt zusaetzlich an die Regeln, Skills und
Rechte des jeweiligen Projekts gebunden.

Seit v0.16.3 ist das Standardmodell deutlich einfacher: Unter
Einstellungen -> MainHub / Control Plane stehen nur die lokale Runtime, der
Cloud-Agentenpool und der Standard-Extern-Harness. Der Cloud-Agentenpool zeigt auf den
uebergeordneten BrainVault-Ordner, in dem `.agents` und `AGENTS.md` liegen.
Trinity stellt diesen Ordner Codex, Pi und OpenCode automatisch als Projekt
`BrainVault` bereit.

Codex, Pi und OpenCode liegen unter Einstellungen -> Harnesses. Dort wird
aktiviert, welche Programme erreichbar sind und welche Rollen sie uebernehmen:
Agentenbuilder, harte komplexe Faelle oder Ausfuehrung der Agenten. Der
Standard-Extern-Harness aus der Control Plane entscheidet, wer laufende Cloud-Agentenarbeit
zuerst bekommt; initial ist das `pi`. Codex bleibt der Builder-Harness fuer neue
Agenten, Imports, Refactorings, Tests und Quality-Gates.

Unter Einstellungen -> Agenten steht der Agentenkatalog in zwei Tabellen:
lokale Trinity-Agenten und externe Cloud-Agenten aus BrainVault. Sichtbar
bleiben Name, Status, Reifegrad, Harness und ein kurzer Hinweis. Rechte,
Skripte, Ursprungspfade und Detailregeln stehen in der jeweiligen `agent.yaml`,
damit die UI nicht ueberlaedt.

### Gemeinsame Sicherheitsgrundsaetze

1. Zuerst ein separates Testprojekt freigeben, nicht das Produktivprojekt.
2. Nur vollstaendige Pfade und sprechende Projektnamen verwenden:

   ~~~text
   Testprojekt = /vollstaendiger/Pfad/zum/Testprojekt
   ~~~

3. Fuer normale BrainVault-Arbeit reicht der Harness-Name: `Trinity, nutze
   Codex ...` oder `Trinity, nutze Pi ...`. Trinity verwendet dann automatisch
   das Projekt `BrainVault`. Andere Projekte nur nennen, wenn bewusst nicht im
   zentralen Agentenpool gearbeitet werden soll.
4. Externe Aktionen nur vorbereiten: keine E-Mails senden, keine Kaeufe, keine
   Deployments, keine Pushes und keine Loeschungen ohne eigene, spaetere
   Bestaetigung.
5. Projektregeln sind entscheidend: Trinity kann ein Projekt mit absichtlich
   weitreichenden Shell-/Netzwerkrechten nicht automatisch unschaedlich machen.
6. Neue Agenten zuerst im Katalog pruefen: Reifegrad und Harness sollten zum
   Einsatzzweck passen; Rechte und Spezialregeln liegen in `agent.yaml`.

### Agentenbuilder nutzen

Der Agentenbuilder ist ein Trinity-interner Skill und steht im Agentenkatalog.
Ein sicherer Startauftrag ist:

> Trinity, aktiviere den Agentenbuilder. Ich moechte einen Agenten planen, der
> PDF-Folien auf fehlende Quellen prueft und nur einen Bericht schreibt.

Trinity legt dabei keinen produktiven Agenten heimlich frei. Externe
Fachagenten werden direkt als BrainVault-Draft unter
`BrainVault/.agents/<bereich>/<agent-id>/` angelegt und sofort im
BrainVault-Katalog sichtbar. Erst wenn Tests und Freigabe stimmen, wird
`agent.yaml` auf `status: active` und `enabled: true` gesetzt.

Typische Auftraege sind:

~~~text
Trinity, baue einen neuen Agenten fuer die DCM-Auswertung.
Trinity, hol Dir diesen Agenten "/vollstaendiger/Pfad/zum/DCM-Agenten".
Trinity, erweitere den Gutachten-Agenten um einen Plausibilitaetscheck.
~~~

Ein Import ist absichtlich nur ein sicherer Draft-Schritt. Trinity kopiert die
relevanten Dateien in `origin_snapshot/`, erkennt moegliche Subagenten aus
Unterordnern, schreibt einen Importbericht und traegt den Agenten im
BrainVault-Katalog als Draft ein. Produktiv wird er erst, wenn Tests, Rechte,
Freigaben und Harness-
Zuordnung sauber geprueft sind.

Der Builder-Loop legt dazu einen sichtbaren Job an. Mit `trinity jobs list` und
`trinity jobs show JOB_ID` siehst Du Plan, Quality-Gates, Validierungsstatus und
gegebenenfalls Harness-Rueckmeldungen. Im BrainVault-Draft entstehen
`BUILDER_PLAN.md`, `VALIDATION_REPORT.md` und bei externem Feedback
`HARNESS_REPORT.md`.

Fuer direkte Verwaltung ohne Trinity-UI gibt es `agentctl`:

~~~bash
agentctl init
agentctl create research thesis-reviewer --name "Thesis Reviewer"
agentctl list
agentctl validate research.thesis_reviewer
agentctl catalog build
~~~

Wenn Du Codex, Pi oder OpenCode im Auftrag nennst und die jeweilige Anbindung in
Einstellungen -> Harnesses aktiv ist, kann Trinity diese Harnesses in den
Builder-Loop einbeziehen. Beispiel:

~~~text
Trinity, hol Dir diesen Agenten "/pfad/zum/Agentenordner" und mache ihn mit Pi
fuer Trinity lauffaehig.
~~~

Ohne aktivierte Harness-Anbindung macht Trinity trotzdem den lokalen
Staging-/Quality-Gate-Teil und schreibt einen nachvollziehbaren Blocker in den
Job.

### Codex einrichten

Voraussetzung ist eine installierte und angemeldete Codex CLI. Den erkannten Pfad
anzeigen:

~~~bash
command -v codex
~~~

Unter Windows PowerShell:

~~~powershell
(Get-Command codex).Source
~~~

In Einstellungen -> Harnesses -> Codex:

| Feld | Sicherer erster Wert |
|---|---|
| Codex-Auftraege erlauben | aktivieren |
| Programm | codex oder der mit dem Befehl ermittelte volle Pfad |
| Freigegebene Projekte | eine Zeile Alias = /vollstaendiger/Pfad |
| Standardprojekt | derselbe Alias |
| Codex-Rechte | zuerst read-only, fuer einen kontrollierten Bericht workspace-write |
| Zeitlimit | 180 bis 900 Sekunden |
| Antwortlaenge | 3200 bis 4000 Zeichen |
| Laeufe nicht als dauerhafte Sitzungen speichern | aktivieren |
| Netzwerkzugriff gestarteter Programme | deaktiviert lassen, solange kein klarer Bedarf besteht |

Beispiel:

> Trinity, nutze Codex im Projekt Testprojekt. Lies die Projektregeln, fuehre nur
> die vorhandenen Tests aus und schreibe den Bericht unter artifacts/.

Codex wird im nicht-interaktiven Modus mit einer auf das Projekt begrenzten
Sandbox gestartet. Informationen zu Codex selbst: [Codex non-interactive
mode](https://developers.openai.com/codex/noninteractive) und [Codex
Skills](https://developers.openai.com/codex/skills).

### OpenCode einrichten

Voraussetzung ist eine installierte OpenCode CLI. Den Pfad pruefen:

~~~bash
command -v opencode
opencode --version
~~~

Unter Windows PowerShell:

~~~powershell
(Get-Command opencode).Source
opencode --version
~~~

In Einstellungen -> Harnesses -> OpenCode:

| Feld | Sicherer erster Wert |
|---|---|
| OpenCode-Auftraege erlauben | aktivieren |
| Programm | opencode oder der volle CLI-Pfad |
| Freigegebene Projekte | eine Zeile Alias = /vollstaendiger/Pfad |
| Standardprojekt | derselbe Alias |
| OpenCode-Agent | ein projektlokaler, eingeschraenkter Agent, nicht blind build |
| Modell | leer lassen fuer das in OpenCode konfigurierte Standardmodell; sonst provider/modell |
| Zeitlimit | 180 bis 900 Sekunden |
| Antwortlaenge | 3200 bis 4000 Zeichen |

OpenCode wird mit opencode run im erlaubten Projektordner gestartet. Auf
macOS/Linux verwendet Trinity fuer die OpenCode-CLI eine korrekt gequotete Shell,
damit projektlokale OpenCode-Konfigurationen sicher gefunden werden. Unter
Windows bleibt der .cmd-Startweg erhalten.

Ein sicherer OpenCode-Testagent sollte in der Projektkonfiguration opencode.json
einen Default-Deny-Ansatz nutzen: zuerst "*": "deny", danach nur Lesen, genau
definierte Testbefehle und einen einzelnen Berichtspfad freigeben. Beispielauftrag:

> Trinity, nutze OpenCode im Projekt Testprojekt. Lies die Projektregeln, fuehre
> nur die vorhandene Fixture-Pruefung aus und erstelle einen Bericht unter
> artifacts/. Aendere keine andere Datei.

Pruefe die wirksamen Agenten vorher mit opencode agent list. OpenCode-Agenten und
ihre Rechte werden vom Projekt selbst definiert; die Trinity-Einstellung waehlt
nur aus, welcher Agent in welchem erlaubten Projekt gestartet wird.

### Mehrere Projekte und ein sicherer Mac-Test

Codex und OpenCode koennen dieselben oder unterschiedliche, vollstaendig
getrennte Projekt-Aliasse erhalten. Beispielsweise in den Codex- und
OpenCode-Bloecken unter Einstellungen -> Harnesses:

~~~text
Trinity = /Users/NAME/.../Trinity_Assistant
Arbeitsprojekt = /Users/NAME/.../Arbeitsprojekt
Schreibprojekt = /Users/NAME/.../Schreibprojekt
Testprojekt = /Users/NAME/.../Testprojekt
~~~

Ein Alias ist keine Freigabe fuer andere Ordner und erzeugt kein gemeinsames
Projekt-Memory. Fuer den ersten Mac-Test zuerst die installierten Programme im
gleichen Terminal pruefen:

~~~bash
command -v codex && codex --version
command -v opencode && opencode --version
cd "/Users/NAME/.../Trinity_Assistant"
python3 -m pytest -q tests/test_codex_agent.py tests/test_opencode_agent.py
~~~

Danach in Trinity ausschliesslich gegen den Alias `Testprojekt` testen:

> Trinity, nutze Codex im Projekt Testprojekt. Lies nur die Projektregeln und
> fuehre den vorhandenen Smoke-Test aus. Aendere keine Dateien.

> Trinity, nutze OpenCode im Projekt Testprojekt. Fuehre nur den erlaubten
> Fixture-Test aus und berichte das Ergebnis. Aendere keine andere Datei.

Mit `trinity jobs list` und `trinity jobs show JOB_ID` erscheint jeweils der
angelegte Plan samt Quality Gates. Erst nach zwei erfolgreichen, nachvollziehbaren
Testlaeufen sollte ein produktiver Alias aktiviert werden.

Die neue dreigeteilte Agentenkiste, geplante Jobs und Freigaben sind im
[Agenten-Oekosystem](AGENT_ECOSYSTEM.md) beschrieben.

### Pi einrichten

Pi ist als CLI-/Wrapper-Harness eingebunden. Trinity kann ihm genau wie Codex
oder OpenCode freigegebene Projekt-Aliasse uebergeben, z.B. `BrainVault` und
separate Sandbox-/Projektordner. Voraussetzung ist ein ausfuehrbares Programm oder Skript, das
Trinity starten darf. Fuer die Pi-CLI ist nicht-interaktiv meist `-p {prompt}`
richtig. Ohne `{prompt}`-Platzhalter wird der Auftrag per stdin uebergeben; das
kann bei interaktiven CLIs haengen.

Beispiele fuer Einstellungen:

In Einstellungen -> Harnesses -> Pi:

~~~text
Programm: pi
Freigegebene Projekte:
SandboxVault = /vollstaendiger/Pfad/zur/Sandbox
BrainVault = /vollstaendiger/Pfad/zum/BrainVault
Standardprojekt: SandboxVault
Argumente: -p {prompt}
~~~

Ein eigener Wrapper ist weiterhin moeglich:

~~~text
Programm: /pfad/zu/pi-wrapper
Argumente: ask {prompt}
~~~

Sicherer Test:

> Trinity, nutze Pi im Projekt SandboxVault und erklaere in drei Saetzen, wie Du angebunden bist.

Wichtig: Eine normale Frage wie "Was ist die Kreiszahl Pi?" startet den
Pi-Agenten nicht. Trinity reagiert nur auf ausdrueckliche Formulierungen wie
"nutze Pi", "frage Pi" oder "Pi-Agent".

## 8. Server-Client, Telegram und Memory

### Desktop als Client eines Trinity-Servers

Ein macOS- oder Windows-Desktop kann statt lokal gegen einen Trinity-Server
arbeiten:

~~~bash
trinity client login --url http://TAILSCALE-IP:8765
trinity start --surface classic
~~~

Die grafischen Felder liegen unter Einstellungen -> System -> Trinity-Server
Client. Der Client trennt Verlauf, Uploads und Memory nach Serverkonto. Mit
trinity client logout wird der lokale Betrieb wieder aktiviert.

### Telegram

Telegram ist optional. Es eignet sich fuer Statusmeldungen und ausdrueckliche
Textauftraege, nicht als Ersatz fuer die lokale Sicherheitspruefung. Bot-Token
und Chat-ID werden in Einstellungen -> Proaktiv -> Telegram Bridge gesetzt.

### TUI und lokales Memory

trinity tui bietet Sessions, Kontextverdichtung und lokales Memory. Wichtige
Kommandos sind /session new, /context, /remember, /memory bake, /memory dream
und /graph. Die Daten liegen lokal in memory/trinity_memory.sqlite3.

## 9. Diagnose und Fehlerbilder

| Symptom | Pruefung |
|---|---|
| Trinity antwortet nicht | trinity doctor; LLM-URL/Modell testen; ClassicUI-Live-Log lesen. |
| Codex/OpenCode wird nicht gefunden | CLI im gleichen Benutzerkonto installieren; command -v beziehungsweise Get-Command nutzen; vollen Pfad in Einstellungen -> Harnesses eintragen. |
| Pi wird nicht gefunden | Eigenen Pi-Wrapper anlegen, ausfuehrbar machen und den vollstaendigen Pfad in Einstellungen -> Harnesses -> Pi eintragen. |
| Agent waehlt falsches Projekt | Alias im Auftrag nennen und exakt wie im Feld Standardprojekt schreiben. |
| Code-Agent kann nicht schreiben | Codex-Sandbox pruefen; bei OpenCode die projektlokale opencode.json und den konkreten edit-Pfad pruefen. |
| Companion verbindet nicht | Tailscale-IP, Bridge-Port, Bearer-Token und lokale Firewall pruefen; Bridge nach Einstellungswechsel neu starten. |
| Heartbeat erzeugt Last | Intervall vergroessern oder Heartbeat/Bubbles deaktivieren. |
| Trinity hoert sich selbst | Im Desktop-Fenster Mikrofon/Zuhören oder Lautsprecher/Sprechen pausieren, wenn iPad/iPhone daneben testweise aktiv ist. |

Fuer den ersten Fehlerbericht immer diese Angaben sammeln: Betriebssystem,
Trinity-Version, gewaehlte Oberflaeche, Betriebsmodus, die sichtbare Fehlermeldung
und die Ausgabe von trinity doctor. Zugangsdaten gehoeren nicht in den Bericht.

## 10. Empfohlene Reihenfolge

1. LLM und ClassicUI im Chat-Modus testen.
2. Eine Datei oder PDF anhaengen und die Antwort pruefen.
3. STT und Wake-Word im Lecture-Modus mit Heartbeat aus testen.
4. Companion per Tailscale und Bearer-Token verbinden.
5. Erst dann Medien, Heartbeat, Telegram und Auto-RAG aktivieren.
6. Codex oder OpenCode ausschliesslich in einem separaten Testprojekt erproben.
7. Produktive Automationen erst nach einer eigenen Projekt- und Rechtepruefung
   freigeben.

Damit bleibt Trinity schrittweise nachvollziehbar: Jede neue Faehigkeit baut auf
einem bereits getesteten, lokalen Fundament auf.
