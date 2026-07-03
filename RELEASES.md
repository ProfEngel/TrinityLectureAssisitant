# Trinity Releases

Diese Datei sammelt die laengere Release-Historie. In der README stehen nur die
letzten drei Highlights, damit der Einstieg kurz und lesbar bleibt. Detaillierte
Einzelnotizen liegen unter [docs/release_notes](docs/release_notes/).

## Aktuelle Highlights

- **v0.16.36:** Antwort-Sicherheitsnetz fuer Talk/Chat: Trinity bereinigt LLM- und Agentenantworten vor der Anzeige von internen Thinking-/Reasoning-Bloecken, bevorzugt klare Final-Antworten und gibt kurze Sprachfragen nicht mehr als ausufernde Scratchpads aus. ClassicUI laedt beim Session-Wechsel ausserdem gezielt die gewaehlte Bridge-Session.
- **v0.16.35:** Companion-STT bleibt jetzt sauber in der aktiven Session: `session_name`, `session_id` und Datenschutzkontext werden auch im Chat-/Wakeword-Pfad uebertragen. iPad/iPhone koennen den Runtime-Modus `Vorlesung`, `Buero` oder `Chat` setzen, zeigen `Wakeword erkannt` kurz sichtbar an und arbeiten mit kuerzeren STT-/Polling-Latenzen.
- **v0.16.34:** Telegram bekommt eine eigene persistente Session; Telegram-Text, Voice, Bilder und erzeugte Medien bleiben im Telegram-Kanal. Passend dazu werden iPhone-Statusflaechen kompakter, Talk-Kamera/Anhang liegen frei, STT nimmt nach TTS schneller wieder auf und neue Companion-Arbeitsraeume/Sessions erscheinen sofort lokal.
- **v0.16.32:** Companion Offline-Talk verhaelt sich naeher wie online: finale STT-Chunks werden lokal in den Chat geschrieben, Wakeword-Varianten aus Trinity werden offline erkannt, Apple Foundation Models koennen direkt antworten und die spaeter synchronisierten Offline-Events umfassen nun auch Transkripte.
- **v0.16.31:** Companion-App erhaelt einen sichtbaren Antwortmodus-Schalter: `Auto` priorisiert den Trinity Server und nutzt Apple Foundation Models als Fallback; `Foundation` bevorzugt lokale Textantworten und synchronisiert Offline-Events spaeter zurueck. README wurde aufgeraeumt und verweist auf Feature- und Offline-Dokumentation.
- **v0.16.30:** Companion-Clients koennen Arbeitsraeume, Sessions, Notizen und Chat-Events lokal cachen; bei Verbindungsverlust kann die iPhone-/iPad-App einfache Textantworten ueber Apples Foundation Models lokal erzeugen und diese beim Reconnect in die Trinity-Session zuruecksynchronisieren.
- **v0.16.29:** Chatprompts aus ClassicUI, iPad und iPhone laufen nun ueber eine Bridge-Queue statt ueber eine einzelne Befehlsdatei; mehrere Clients/Sessions koennen parallel senden, alte Fremd-Session-Events werden strikter gefiltert, und fehlerhafte Skill-Erkennung blockiert den normalen LLM-Antwortpfad nicht mehr.
- **v0.16.28:** Desktop, iPad und iPhone synchronisieren Arbeitsraeume und Sessions ueber die Bridge; Clients koennen dieselbe Session gezielt laden, umbenennen, archivieren oder loeschen, und mobile Antworten erscheinen auch bei langen/parallel genutzten Session-Verlaeufen wieder zuverlaessig.
- **v0.16.27:** Companion-Chat-Kompatibilitaet: Mobile Antworten werden auch dann wieder angezeigt, wenn ein Runtime-Pfad eine Antwort nur ueber `request_id` und ohne `session_id` zurueckliefert; die Companion-Eingabe startet wieder kompakt einzeilig.
- **v0.16.26:** Companion-Chat-Fix: Nachrichten koennen serverseitig geloescht werden, neue Sessions filtern alte Events strikt aus und Return sendet Chatnachrichten direkter.
- **v0.16.25:** Pi-Antworten werden nicht mehr doppelt angezeigt: Wenn Pi nur den normalen Antworttext liefert, erzeugt Trinity keine zusaetzliche Agenten-/Medienkarte mehr.
- **v0.16.24:** Agenten zeigen nun kompakt Herkunft, Beschreibung, Rechte und Jobzahlen; Agent-Anzeigenamen koennen ohne Ordner-Rename angepasst werden; Sessions lassen sich direkt loeschen; ClassicUI und Companion ruecken mit iPad-aehnlicher Symbolleiste und moderner Chat-Eingabe weiter zusammen.
- **v0.16.23:** Companion/Bridge-Feinschliff: Agents zeigt nun den vollen Dashboard-Agentenpool gruppiert als Trinity-Kernagenten und BrainVault-Erweiterungen; Prompts koennen direkt aus `Soul.md`/`User.md` geladen und gespeichert werden; Light/Dark/System greift in der Companion-App wirklich.
- **v0.16.22:** Companion-Feinschliff: iPhone-Talk-Buttons bleiben frei, Agents und Control werden anklickbar mit Favoriten, Agent-Start, RAG-/Session-/Prompt-Details; macOS-Desktop-App nutzt das Trinity-Icon nun explizit als Bundle-Icon.
- **v0.16.21:** `Agents` und `Control` nutzen nun echte Dashboard-Daten aus der Bridge; iPhone bleibt im Hochformat schlank ohne funktionslosen `...`-Button, iPad und ClassicUI behalten die erweiterte Symbolleiste.
- **v0.16.20:** ClassicUI und Companion bewegen sich Richtung gemeinsamer Arbeitsoberflaeche: `Talk`, neue `Agents`-/`Control`-Ansichten, iPhone-Bottom-Navigation und vorbereitete Audioquelle fuer eigenes Mikro vs. Meeting/System-Audio.
- **v0.16.19:** Arbeitsorga-Leiste weiter aufgeraeumt: Arbeitsraeume koennen angelegt werden, Platzhaltergruppen verschwinden und die Bedienung rueckt naeher an die Codex-Seitenleiste mit subtilen Icon-Aktionen.
- **v0.16.18:** Arbeitsorga-Leiste verfeinert: Arbeitsraeume starten Sessions im gewaehlten Kontext, erzeugen Notizen pro Arbeitsraum und Sessions haben direkte Aktionen fuer Anheften und Zusammenfassen.
- **v0.16.17:** Arbeitsraeume/Sessions beginnen als neue Ordnungsschicht: lokale Runtime-Metadaten, CLI-Kommandos, ClassicUI-Arbeitsleiste, Memory in den Einstellungen und Roadmap fuer iPad/iPhone/WebUI.
- **v0.16.16:** Agentenbau und Agenten-Ueberarbeitung nutzen standardmaessig Codex als Builder-Harness mit HITL-Regeln, Plan, Tests und Rueckfrage-/Freigabebericht; Pi bleibt Standard fuer bestehende BrainVault-Agentenarbeit.
- **v0.16.15:** BrainVault-Auto-Routing: Trinity kann bekannte externe BrainVault-Projekte und Agenten nun kontextbasiert an den Standard-Harness (aktuell Pi) delegieren, ohne dass der Nutzer Pi explizit nennen muss.
- **v0.16.14:** Pi-Desktop-Start stabilisiert: Trinity startet Homebrew-/Node-basierte Pi-CLIs nun auch aus macOS- und Windows-Launchern mit erweitertem Unterprozess-PATH, sodass `env: node: No such file or directory` nicht mehr den Pi-Harness blockiert.
- **v0.16.13:** Pi-Routing fuer BrainVault-Projektfragen verbessert: Imperativ `frag Pi`, allgemeine BrainVault-Fragen und Erendria-Treffer werden jetzt an Pi geleitet und mit passenden Agenten-/Projektkontexten angereichert.
- **v0.16.12:** GitHub-Markdown-Dokumentation neutralisiert sensible Dokumentanalyse-Beispiele. `Neue Session` schlaegt in ClassicUI, WebUI und Companion-App nun Namen im Format `JJJJMMDD_HHMM_` vor.
- **v0.16.11:** `Neue Session` zeigt die automatisch erzeugte Summary der vorherigen Session nun sichtbar in der neuen Session an. Das gilt fuer ClassicUI lokal, ClassicUI als Remote-Client und WebUI.
- **v0.16.10:** Update-Installer und `control-plane init` erzeugen im BrainVault keine historischen Zusatzordner wie `00_registry`, `01_agents` oder `03_results` mehr. Interne Kataloge, Policies und Artefakte liegen nun lokal in der Runtime; BrainVault bleibt schlank mit `.agents` und Instruktionsdateien.
- **v0.16.9:** Desktop-ClassicUI startet beim Button `Neue Session` nun ebenfalls den nicht-blockierenden Summary-Hintergrundjob fuer die vorherige Session. Auch Desktop-Sessions ohne bisherige Session-ID werden nur fuer das aktuelle App-Zeitfenster zusammengefasst.
- **v0.16.8:** Nicht-blockierende Session-Summaries: Beim Start einer neuen Session wird die alte Session im Hintergrund zusammengefasst, als Markdown-Asset gespeichert, in Memory/RAG uebernommen und ueber Desktop-WebUI sowie iPhone/iPad-Companion abrufbar gemacht.
- **v0.16.7:** Wakeword-Bugfix: Trinity erkennt iPhone-/iPad-STT-Varianten wie `Triniti`, `Trini ty`, `Tri-nity`, `Drinity` und `Trinitie` robuster, ohne nahe Alltagswoerter wie `Trend` oder `Training` als Trigger zu behandeln.

## Historie

- **v0.16.6:** Natuerliche Agentenpool-Nutzung: Fragen wie `Trinity, welche Faehigkeiten hast Du?` listen Trinitys lokale Faehigkeiten und den BrainVault-Agentenpool, ohne dass Pi oder Pfade genannt werden muessen. Bestehende BrainVault-Agenten laufen weiter standardmaessig ueber Pi; Codex/Antigravity duerfen denselben Agentenpool direkt nutzen.
- **v0.16.5:** Pi ist nun der Standard-Extern-Harness fuer laufende BrainVault-Agentenarbeit; Codex bleibt der Builder-Harness fuer neue Agenten, Imports, Refactorings und Quality-Gates.
- **v0.16.4:** Pi-Harness robuster fuer BrainVault/iCloud-Pfade: Trinity startet Pi mit Projekt-CWD, relativen Pfadregeln und `TRINITY_PROJECT_*`-Umgebung.
- **v0.16.3:** Settings-Aufraeumen fuer den zentralen BrainVault-Agentenpool: MainHub zeigt nur noch lokale Runtime, Cloud-Agentenpool und Standard-Extern-Harness; Codex, Pi und OpenCode erhalten `BrainVault` automatisch als gemeinsames Standardprojekt.
- **v0.16.2:** Externe Harness-Agenten koennen ohne Duplikation per `agentctl register` in `BrainVault/.agents` katalogisiert werden.
- **v0.16.1:** BrainVault-Agentenimport: bestehende CampusHub-Skills koennen nach `BrainVault/.agents` uebernommen, validiert, katalogisiert und in den Einstellungen geladen werden.
- **v0.16.0:** BrainVault-Agentenbasis: externe Fachagenten werden direkt unter `BrainVault/.agents` als `draft` angelegt und harness-agnostisch vorbereitet.
- **v0.15.6:** Harness-Einstellungen besser lesbar: kontrastreiche Status-Badges, groessere Projektfelder und eine nach unten wachsende Agentenmatrix.
- **v0.15.5:** Pi-Harness auf Codex/OpenCode-Niveau fuer Projektarbeit erweitert.
- **v0.15.4:** Jobbasierter Agentenbuilder-Loop mit Builder-Plan, Validierungsbericht, optionalen Harness-Rueckmeldungen und Quality-Gates.
- **v0.15.3:** Desktop-Settings erhalten schnelle Mikrofon-/Lautsprecher-Toggles gegen Selbstmithoeren; der Agentenbuilder kann vorhandene Agentenordner importieren.
- **v0.15.2:** Vollstaendiger Agentenkatalog in den Einstellungen mit Reifegrad, Rechten, Freigaben, Lauf-/Parallelitaetslimits und sichtbarem Trinity-Harness.
- **v0.15.1:** Gemeinsame Harness-Einstellungen fuer Codex, Pi und OpenCode.
- **v0.15.0:** Control-Plane-Fundament mit getrenntem lokalem TrinityRuntime-Ordner und synchronisiertem Vault.
- **v0.14.1:** Vollwertige WebUI-Einstellungen fuer LLM, Persona, Sprache, Oberflaechen, Agentenprojekte, Companion, Server und Profile.
- **v0.14.0:** Dreigeteilte Agentenkiste mit Shared/Personal/Staging, persistenter Plan-/Job-Verwaltung, Quality Gates und lokalen Freigaben.
- **v0.13.3:** Zentrales Onboarding fuer Desktop, Linux-Server, iPhone/iPad-Companion und sichere Codex-/OpenCode-Projekte.
- **v0.13.2:** WebUI als vierte auswaehlbare Desktop-Oberflaeche fuer macOS und Windows 11.
- **v0.13.1:** Einstellungen-UI stabilisiert: Systemseite scrollt sauber, Formfelder bleiben lesbar.
- **v0.13.0:** Optionaler Mehrbenutzer-Server mit Passwort-Accounts, getrennten Nutzerbereichen und ClassicUI-Client.
- **v0.12.1:** Augen-UI-Datei-Arbeitsbereich korrigiert.
- **v0.12.0:** Desktop-Arbeitsbereich fuer Datei-Drop auf der Augen-UI und schlanke Linux-Servervariante.
- **v0.11.7:** Companion-Bridge liefert Agenten-Widgets fuer Sandbox, Diagramme, Timer und Simulationen aus.
- **v0.11.6:** macOS-Starter-App zeigt das Trinity-Symbol bereits im Finder/Desktop.
- **v0.11.5:** Companion-Medienabruf fuer Bilder, Audio und Video stabilisiert.
- **v0.11.4:** Companion-STT-Finalisierung korrigiert.
- **v0.11.3:** Hellmodus der Einstellungen ueberarbeitet.
- **v0.11.2:** Praeziser Trinity-Trigger fuer normale Fragen zu Liebe und aehnlichen Begriffen.
- **v0.11.1:** ClassicUI als Erststart-Standard mit Chat, Live-Mitschrift/Agentenlog und Memory Graph.
- **v0.11.0:** Trinity TUI mit Slash-Commands, Sessions, lokalem SQLite-Memory, Self-Bake/Dreaming und Memory-Graph.
- **v0.10.3:** Classic-Chat mit Verlauf, Text-/PDF-/Bildanlagen und eingebetteten Medienergebnissen.
- **v0.10.2:** Gemeinsame Classic-/Settings-App sowie globale CLI mit Onboarding und Doctor.
- **v0.10.1:** Waehlbare Augen-, Classic- und Terminal-Oberflaechen fuer Desktop und Headless.
- **v0.10.0:** Gemeinsames Release fuer macOS und Windows 11 mit lokalem Codex-Agenten.
- **v0.9.2:** Weiterhin verfuegbarer macOS-Basisstand vor der Windows-Portierung.
