# Implementierungsplan: Trinity kontrolliert fertigstellen

Stand: 23. Juli 2026
Status: **einzige aktuelle Resteliste**; T0 abgenommen, T1 lokal validiert,
Versionierung und Windows-/Companion-Abnahme ausstehend

Dieser Plan behandelt ausschließlich die bestehende Trinity-Anwendung. Trinity
Voice Studio besitzt einen eigenen Implementierungsplan und ein späteres eigenes
Repository. Beide Produkte dürfen unabhängig voneinander installiert, gestartet,
aktualisiert und entfernt werden.

## 1. Verbindlicher Ausgangspunkt

- Core-Repository: `ProfEngel/TrinityLectureAssisitant`
- Aktive Mac-Arbeitskopie: `/Users/matmax/Trinity_Assistant`
- Stand bei Erstellung dieses Plans: `0.16.58`
- Windows ist die Trinity-Autorität für **Arbeit/BIZ**.
- Mac ist die Trinity-Autorität für **Privat/PRIVAT**.
- **Development/TEST** bleibt isoliert.
- OneDrive-`BizVault` ist die berufliche Datenwahrheit.
- iCloud-`BrainVault` ist die private Datenwahrheit.
- Runtime, Datenbanken, RAG- und Graphify-Indizes sowie ausführbare Agenten
  liegen lokal und nicht in den Vaults.
- Canvas ist Bestandteil von Trinity und benötigt in der CompanionApp keine
  separate URL.
- Android bleibt vollständig entfernt. Die CompanionApp wird nur für iPhone
  und iPad gepflegt.
- Agenten und RAG-Quellen werden nur einzeln nach tatsächlichem Bedarf ergänzt.

Die bisherigen Architekturphasen 1 bis 5 sind im Kern umgesetzt. Dieser Plan
beginnt bei den noch offenen Resten und rollt fertige Arbeit nicht neu auf.

Ältere Roadmaps, Portierungspläne und Release Notes dokumentieren ihren
jeweiligen historischen Entwicklungsstand. Bei Widersprüchen gelten dieser
Plan, `PHASE_1_PROFILE_ARCHITECTURE.md` und
`TRINITY_ARCHITEKTUR_CHEATSHEET.md` in dieser Reihenfolge. Offene Arbeiten
werden ausschließlich hier geführt und nicht zusätzlich in einer zweiten
aktuellen Resteliste gepflegt.

## 2. Gemeinsame Abnahmeregeln

Jede Phase endet mit einer überprüfbaren Abnahme. Für Releases gelten:

- vorhandene Nutzerdaten und Konfigurationen bleiben erhalten;
- Profiltrennung wird automatisiert geprüft;
- Secrets erscheinen weder in Git noch in Logs;
- Installation, Update und Rückkehr zur Vorversion werden geprüft;
- Release Notes beschreiben sichtbare Änderungen und Benutzerschritte;
- unfertige Funktionen bleiben standardmäßig ausgeschaltet;
- keine automatische Inhaltsmigration und keine Legacy-Löschung;
- keine GitHub-Veröffentlichung ohne erfolgreiches lokales Prüfergebnis.

## T0 – Tatsächlichen Stand festschreiben

### Ziel

Repository, Installationen und Dokumentation beschreiben denselben Stand.

### Arbeiten

- Mac- und Windows-Version, Commit und Release erfassen.
- Widersprüche in Phase-1- und Phase-2-Dokumenten korrigieren.
- erledigte, vertagte und offene Punkte eindeutig kennzeichnen.
- historische Cloud-Arbeitskopien ausdrücklich als Legacy markieren.
- eine einzige aktuelle Resteliste in `docs/` anlegen.
- laufzeitbedingt veränderte Statusdateien von Quellcodeänderungen abgrenzen.

### Abnahme

- Ein neuer Chat erkennt allein aus der Dokumentation, was produktiv,
  experimentell, vertagt oder offen ist.
- `git status` enthält keine unerklärten Quellcodeänderungen.
- Es gibt keine widersprüchlichen Aussagen zu Vault, Profil, Telegram oder RAG.

### T0-Prüfstand vom 23. Juli 2026

- [x] Mac-Repository, Release und Installation geprüft:
  `v0.16.58`, Commit `48dfbae0b96164c923fc1eb0f55832afae787fae`,
  Branch `main`; `origin/main` und Tag `v0.16.58` zeigen auf denselben Commit.
- [x] Mac-Profil `PRIVAT`, lokale Runtime und iCloud-`BrainVault` geprüft.
- [x] `trinity doctor --online`, Vault-Status, Control-Plane-Status und
  SQLite-Integrität auf dem Mac geprüft.
- [x] 69 gezielte Profil-/Vault-/RAG-/Session-/Bridge-Tests sowie der
  vollständige Testbestand unter Python 3.13 erfolgreich ausgeführt.
- [x] Phase-1-/Phase-2-Dokumente auf den aktuellen Mac- und Release-Stand
  korrigiert.
- [x] Historische Roadmaps und alte Architekturstände als historisch oder
  abgelöst gekennzeichnet.
- [x] Laufzeitdateien `core/state.txt` und `core/payload.html` als bekannte,
  nicht zu committende Runtime-Ausgaben abgegrenzt.
- [x] Unabhängige Voice-Studio-Dokumentation als außerhalb dieses Plans
  liegend gekennzeichnet und nicht verändert.
- [x] Windows-Installation geprüft: Trinity `0.16.58`, Python `3.11.9`,
  Profil `BIZ`, vollständiger OneDrive-`BizVault`, keine fehlenden oder
  unklassifizierten Hauptordner und laut Doctor aktuelle Installation.
- [x] Windows-Harnesszustand festgehalten: Goose ist verfügbar; Codex und
  OpenCode sind nicht installiert. Codex wird vor der ersten produktiven
  BIZ-Builder-/Heavy-Duty-Aufgabe kontrolliert ergänzt. OpenCode bleibt
  optional und wird nicht automatisch installiert.

**T0 ist am 23. Juli 2026 abgenommen.** T1 beginnt erst nach ausdrücklicher
Freigabe.

## T1 – Canvas unter Windows reparieren und abnehmen

### Ziel

Canvas startet zusammen mit Trinity auf Mac und Windows und ist ohne Kenntnis
einer Portnummer erreichbar.

### Arbeiten

- Windows-GET-Fehler reproduzieren und Ursache protokollieren.
- Launcher, Basisroute, Web-Dateien und Weiterleitung prüfen.
- verständliche Fehlerseite statt technischer GET-Meldung ergänzen.
- Canvas-Status in Doctor und Statusansicht prüfen.
- Standalone-Canvas und gebündelte Komponente auf demselben Quellstand halten.

### Abnahme

- Mac und Windows: Start, Neustart, Update und Beenden erfolgreich.
- Desktop und Companion öffnen die von Trinity gelieferte Canvas-Adresse.
- Keine manuelle Port- oder URL-Eingabe erforderlich.
- Nicht erreichbares Canvas wird verständlich gemeldet.

### T1-Prüfstand vom 23. Juli 2026

- [x] Technische GET-Meldung reproduziert: Wird der absolute Canvas-
  Servereinstieg aus einem anderen Arbeitsverzeichnis gestartet, bleibt
  `/api/health` erreichbar, während `/` wegen der an `process.cwd()` gebundenen
  Web-Dateien mit HTTP 404 und `Cannot GET /` antwortet.
- [x] Pfadauflösung repariert: Produktionsbuild und Standard-Datenordner werden
  relativ zur Canvas-Installation bestimmt und sind nicht mehr vom
  Startverzeichnis abhängig.
- [x] Verständliche HTTP-503-Wartungsseite für einen fehlenden Webbuild sowie
  verständliche JSON-404-Antwort für unbekannte API-Routen ergänzt.
- [x] Health um `uiReady` erweitert; CLI-Status und Doctor unterscheiden
  `ready`, `stopped`, `not_installed`, `not_built` und `ui_unavailable`.
- [x] Desktop-Canvas-Reiter zeigt bei Nichterreichbarkeit eine Trinity-
  Fehlerseite; Control-Ansicht und authentifiziertes Companion-Dashboard
  erhalten denselben Canvas-Status samt von Trinity gelieferter Adresse.
- [x] Gebündelte und lokale Standalone-Arbeitskopie besitzen denselben
  geänderten Quellstand.
- [x] Mac: Typecheck, Produktionsbuild, Start aus fremdem Arbeitsverzeichnis,
  Root-GET, Health, unbekannte API-Route sowie verwalteter Start und Stop
  erfolgreich geprüft.
- [x] Plattformübergreifenden Produktions-Smoke-Test für macOS und Windows in
  die CI-Konfiguration aufgenommen.
- [ ] Canvas-Änderung kontrolliert im eigenständigen Canvas-Repository
  versionieren und danach den geprüften Submodule-Stand in Trinity festhalten.
- [x] Vollständigen Trinity-Testbestand auf dem fertigen lokalen Stand
  ausgeführt: 238 Tests unter Python 3.13 bestanden; Python-Compile-Checks,
  Canvas-Lint, Typecheck, Build und Produktions-Smoke ebenfalls bestanden.
- [ ] Aktualisierten Stand unter Windows installieren/aktualisieren und Start,
  Neustart, Doctor, Root-GET, Desktop-Reiter und Beenden prüfen.
- [ ] Companion-Aufruf auf iPhone oder iPad gegen die BIZ-Trinity prüfen.

T1 ist erst nach den drei offenen Punkten abgenommen. Die konkreten Prüfungen
und erwarteten Ergebnisse stehen in `T1_CANVAS_ABNAHME.md`.

## T2 – Einen einheitlichen Live-Informationsstrom schaffen

### Ziel

Trinity, Goose, Codex, Subagenten und Companion-Geräte zeigen denselben
aktuellen Arbeitsstand.

### Arbeiten

- Request-IDs, Event-IDs und Job-Ereignisse zu einem Ereignismodell verbinden.
- fortlaufenden Event-Cursor je Profil und Session definieren.
- Wiederverbindung ab dem letzten bestätigten Ereignis implementieren.
- Status vereinheitlichen: wartet, läuft, benötigt Freigabe, fertig,
  abgebrochen und fehlgeschlagen.
- Abbruch und Freigabe serverseitig verbindlich machen.
- Polling nur als Rückfalllösung behalten.
- doppelte und verspätete Ergebnisse erkennen und ignorieren.

### Abnahme

- Auftrag auf Gerät A beginnen und auf Gerät B verfolgen.
- Nach Offlinezeit fehlen keine Ereignisse und erscheinen keine Duplikate.
- Abbruch und Freigabe werden überall gleich angezeigt.

## T3 – Profilübergreifende Übergabe kontrollierbar machen

### Ziel

Arbeit und Privat bleiben standardmäßig getrennt. Einzelne Inhalte können nur
nach ausdrücklicher Bestätigung übergeben werden.

### Arbeiten

- Übergabeobjekt für Dokument, Summary oder Medienartefakt definieren.
- Quelle, Zielprofil, Zweck, Zeitpunkt und Prüfsumme protokollieren.
- verständliche Vorschau und Bestätigung anzeigen.
- automatische Hintergrundübertragungen verbieten.
- Ablehnen und Entfernen lokaler Zwischenkopien ermöglichen.

### Abnahme

- Falsches Profil bleibt HTTP-seitig gesperrt.
- Ohne Bestätigung findet keine Übertragung statt.
- Jede Übergabe ist nachvollziehbar und inhaltlich begrenzt.

## T4 – Memory und RAG kontrolliert konsolidieren

### Ziel

Memory und RAG bleiben pro Profil sauber, löschbar und nachvollziehbar.

### Arbeiten

- interne Memory-Schnittstelle dokumentieren.
- Löschen einzelner Memories, Summaries, Sessions und vollständiger Profile
  auf Mac, Windows, iPhone und iPad testen.
- Herkunft, Profil, Session, Projekt und Bestätigungsstatus speichern.
- Agentenfeedback als Vorschlag statt sofort als Wahrheit speichern.
- alte Momora-, Jar-El- und Agenten-Memories nur aus Recovery prüfen.
- Importvorschau mit Behalten, Verwerfen und Profilzuordnung entwickeln.
- Graphify als lokales Dokument- und Code-Wissensnetz behandeln, nicht als
  Trinitys persönliches Langzeitgedächtnis.

### Abnahme

- Kein Memory und kein RAG-Chunk ohne Quelle und Profil.
- Leere Profile bleiben tatsächlich leer.
- Legacy-Import verändert Recovery nicht.
- Cross-Profile-Suchen sind standardmäßig unmöglich.

## T5 – Inhalte nachvollziehbar im Vault veröffentlichen

### Ziel

Trinity übernimmt geprüfte Ergebnisse in einen gewählten Vault-Ordner, ohne den
Vault zu einem Runtime-Verzeichnis zu machen.

### Arbeiten

- Veröffentlichungsdienst für Summary, Transcript, Dokument und Medien bauen.
- Manifest mit Quelle, Profil, Agent, Session, Ziel und Prüfsummen erzeugen.
- Status unterscheiden: Entwurf, angenommen, bearbeitet, abgelehnt, archiviert.
- Änderungen an veröffentlichten Dateien erkennen.
- finale Fassungen kontrolliert zurückführen.
- Konflikte und parallele Bearbeitung sichtbar machen.
- dauerhafte Memory-Übernahme erst nach Bestätigung erlauben.

### Abnahme

- Dateien landen nur im ausdrücklich gewählten Zielordner.
- Wiederholung erzeugt keine unbemerkten Duplikate.
- Sessiondaten und Vault-Dateien bleiben unterscheidbar.
- Jede Lernübernahme kann erklärt und widerrufen werden.

## T6 – Agenten nur bei Bedarf produktiv nehmen

### Ziel

Der Werkzeugkasten bleibt vollständig, die Installationen bleiben schlank.

### Arbeiten je tatsächlich benötigtem Agent

- `agent.yaml` mit Zweck, Profil, Harness und Rechten vervollständigen.
- benötigte Pfade, Subagenten und Teststatus eintragen.
- Zuständigkeit von Trinity, Goose oder Codex festlegen.
- Pi und OpenCode erst nach Prüfung deaktivieren oder behalten.
- Test und Freigabestatus ergänzen.
- keine pauschale Migration aus BrainVault_LEGACY.
- Codex auf Windows vor der ersten produktiven BIZ-Builder- oder
  Heavy-Duty-Aufgabe installieren und im Doctor prüfen.
- OpenCode nur installieren, wenn ein konkret benötigter Agent davon abhängt.

### Abnahme je Agent

- genau ein Ursprung im privaten Agenten-Repository;
- Freigabe für Arbeit, Privat, Gemeinsam oder Development;
- minimal notwendige Rechte und Pfade;
- erfolgreicher Harness-Test;
- dokumentierter Rückbau.

Diese Phase läuft nach Bedarf und blockiert Trinity nicht.

## T7 – Geräte und echten Vorlesungsablauf abnehmen

### Ziel

Der reale Tagesablauf funktioniert, nicht nur einzelne Funktionen.

### Prüfszenarien

- Mac-Desktop und private Companion-Geräte.
- Windows-Desktop und Arbeitsprofil.
- iPhone und iPad mit Arbeit, Privat und Development.
- getrennte Telegram-Bots und G2 im Hörsaal.
- Profilwechsel während unterschiedlicher Sessions.
- Sessionabschluss auf einem Gerät und neue Session auf allen Geräten.
- Medien, Canvas, Memory-Graph und nachträgliche Summary-Zuordnung.
- Verbindungsabbruch, App-Neustart, Serverneustart und Wiederverbindung.
- aktive Profilkennzeichnung in jeder relevanten Ansicht.

### Abnahme

- Ein vollständiger Vorlesungsablauf endet protokolliert erfolgreich.
- Nach Wiederverbindungen stimmen Profil, Session, Arbeitsraum und Artefakte.
- Es erscheinen keine Daten des zuvor aktiven Profils.

## T8 – Wartungsarmen Betrieb herstellen

### Ziel

Trinity funktioniert im Alltag ohne regelmäßige Reparatureingriffe.

### Arbeiten

- automatische Starts und Healthchecks vereinheitlichen.
- Logs begrenzen und rotieren.
- verschlüsselte Sicherungen relevanter lokaler Zustände planen.
- Windows-BIZ-Installation, Runtime und Recovery als eigenen verschlüsselten
  Container auf `BACKUP_M5` sichern; das Mac-Sparsebundle nicht verändern.
- Restore-Test ohne Überschreiben der Produktion automatisieren.
- Updatekanal mit geprüfter Rückkehr zur Vorversion vervollständigen.
- Warnungen für nicht erreichbare oder nicht synchronisierte Vaults ergänzen.
- Statusseite für Server, Modell, Memory, Vault, Canvas und Agenten abrunden.
- Abhängigkeiten kontrolliert aktualisieren.

### Abschlussabnahme

- vier Wochen normaler Betrieb ohne manuellen Reparatureingriff;
- mindestens ein erfolgreicher Restore-Test;
- Update und Rollback auf Mac und Windows geprüft;
- keine kritischen Profil-, Datenverlust- oder Sicherheitsfehler;
- aktuelles Release mit verständlichen Release Notes veröffentlicht.

## 3. Was nicht automatisch geschehen darf

- keine Migration des gesamten BrainVault_LEGACY;
- keine pauschale Agenteninstallation;
- kein automatischer Import alter Memories oder RAG-Quellen;
- keine beruflich-private Hintergrundübertragung;
- keine Wiederaufnahme der Android-App;
- keine Kopplung, die Trinity von Trinity Voice Studio abhängig macht.

## 4. Startauftrag für einen neuen Codex-Chat

> Wir setzen Trinity anhand von
> `/Users/matmax/Trinity_Assistant/docs/IMPLEMENTIERUNGSPLAN_TRINITY.md`
> fort. Lies zuerst den Plan sowie die Phase-1- und Phase-2-Dokumente. Prüfe
> danach den tatsächlichen lokalen Git-, Installations- und Release-Stand, ohne
> Nutzerdaten zu ändern. Beginne ausschließlich mit **T0**. Berichte
> Widersprüche, korrigiere die Statusdokumentation, führe passende Tests aus und
> stoppe nach der Abnahme von T0. Starte keine spätere Phase ohne meine
> ausdrückliche Bestätigung. Verbindlich gelten: Windows = Arbeit/BIZ, Mac =
> Privat/PRIVAT, Development = TEST, Android bleibt entfernt, Agenten und RAG
> werden nur einzeln nach Bedarf ergänzt. Trinity Voice Studio ist ein anderes
> Projekt und bleibt in diesem Chat unangetastet.
