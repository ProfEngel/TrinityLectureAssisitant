# TrinityLectureAssistant – große Übersicht nach Arbeitsmodi


siehe auch hier:https://chatgpt.com/share/6a072bd1-f1cc-83eb-8ecc-94bb4edc69e4

## A. Grundidee / Positionierung

**Highlights:**
Trinity ist kein klassischer Chatbot, sondern ein lokaler, agentenfähiger Lecture- und Office-Companion. Die primäre Zielarchitektur ist  **Local First** , modellagnostisch und DSGVO-orientiert. Die Architektur ist in spezialisierte Agent-Skills gegliedert, z.B. RAG, WebSearch, Image, Simulation, PowerPoint, Summary, Document Intelligence und Office Mode. ([GitHub](https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/README.md "raw.githubusercontent.com"))

a. KI-gestützte Vorlesungsassistentin für macOS / Apple Silicon
b. Lokaler Betrieb als primäre Zielarchitektur
c. Cloud-Dienste nur optional, nicht als Grundvoraussetzung
d. Modellagnostisch: lokale Modelle, OpenRouter oder andere Backends denkbar
e. Agentenfähig: Aufgaben werden an spezialisierte Agenten verteilt
f. Lecture Mode für Hörsaal / Lehre
g. Office Mode für Büro / produktive Arbeit
h. Lokale RAG-Wissensbasis für Skripte, PDFs, Sessions und später Office-Daten
i. Sprachschnittstelle über Mikrofon / AirPod
j. UI für Visualisierungen, Karten, Timer, Simulationen, Dokumentanalysen und Hinweise
k. DSGVO-orientierter Ansatz über gezieltes Dozenten-Audio statt Raumaufnahme
l. Erweiterbar durch neue Agent-Skills
m. Nicht nur reaktiv, sondern perspektivisch proaktiv durch Heartbeat, Bubbles und Telegram

---

# 1. Hörsaal / Lecture Mode

## 1.1 Lass Trinity nur zuhören — passiver Lecture Recorder

**Highlights:**
Trinity hört hier ausschließlich passiv mit. Es gibt noch keine Konversation, keine aktiven Zurufe, keine Wake-Word-Interaktion und keine sichtbare oder hörbare Intervention. Der Mehrwert liegt in Transkript, didaktisch angereicherter Summary, Fehlerhinweisen, Hervorhebungen und späterem semesterweitem RAG-Gedächtnis. Session-Summarizer, Summary per Zuruf, Review-Modus und RAG-Indexierung sind im Repo bzw. ToDo angelegt oder beschrieben. ([GitHub](https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/ToDo.md "raw.githubusercontent.com"))

a. Passive Spracherkennung über Dozenten-Mikrofon / AirPod
b. Aufzeichnung des gesprochenen Vorlesungsverlaufs
c. Erstellung eines Sitzungs-Transkripts im Hintergrund
d. DSGVO-orientierter Betrieb über Dozenten-Audio statt Raumaufnahme
e. Keine aktive Konversation mit Trinity
f. Keine Unterbrechung des Vortrags durch Trinity
g. Keine sichtbare oder hörbare Interaktion im Hörsaal
h. Automatische Strukturierung der Sitzung nach Themenblöcken
i. Automatische Zusammenfassung der Sitzung
j. Erfassung der behandelten Inhalte
k. Erfassung der Reihenfolge, in der Inhalte behandelt wurden
l. Erfassung besonders hervorgehobener Aspekte für Studierende
m. Erfassung von Begriffen, Beispielen oder Zusammenhängen, die explizit betont wurden
n. Erfassung spontaner Ergänzungen, die nicht im Skript standen
o. Erfassung erkannter Fehler oder Unklarheiten im eigenen Skript
p. Erfassung von Hinweisen auf notwendige Korrekturen im Lehrmaterial
q. Erfassung offener Punkte für die nächste Sitzung
r. Erfassung, welche Themen besonders ausführlich behandelt wurden
s. Erfassung, welche Themen nur kurz angerissen wurden
t. Erstellung einer didaktisch angereicherten Session-Summary
u. Speicherung der Summary für spätere Nutzung
v. Aufbau einer Vorlesungshistorie über das Semester
w. Zukünftig beziehungsweise bereits angelegt: automatische Übernahme der Session-Summaries ins RAG-Gedächtnis
x. Zukünftig: semesterweites Gedächtnis über Inhalte, Betonungen, Fehler, Ergänzungen und offene Punkte
y. Zukünftig: Prüfung, ob ein Thema im Semester bereits behandelt wurde
z. Zukünftig: Abfrage, wann ein Thema bereits gesagt wurde
aa. Zukünftig: Repetitions-Check gegen frühere Sessions
ab. Zukünftig: Hinweis, wenn wichtige Inhalte noch nicht behandelt wurden
ac. Lokale Speicherung von Transkripten, Summaries und Metadaten
ad. Lokale Auswertung als primäre Lösung
ae. Umsetzbar durch spezialisierte Agenten für Transkription, Strukturierung, Zusammenfassung, Fehlerhinweise und RAG-Indexierung

---

## 1.2 Binde Trinity niedrigschwellig ein — Assistenz auf Zuruf

**Highlights:**
Ab hier wird Trinity aktiv ansprechbar. Sie kann per Sprache einfache Aufgaben übernehmen: Timer, Recherche, RAG-Abfragen, kurze Erklärungen, Schaubilder, Simulationen, Karten und PowerPoint-Steuerung. Im README werden Wake-Word-Interaktion, Webrecherche, Timer, Karten, Simulationen, Infografiken und PowerPoint-Agent genannt. ([GitHub](https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/README.md "raw.githubusercontent.com"))

a. Wake-Word-Erkennung „Trinity“
b. Ansprache am Satzanfang oder Satzende
c. Nutzung des gesprochenen Kontexts vor und nach dem Triggerwort
d. Kurze gesprochene Antworten per TTS
e. Rückfragen an Trinity während der Vorlesung
f. Kurze Erklärungen zu Begriffen
g. Definitionen aus dem eigenen Material abrufen
h. Beispiele und Analogien formulieren
i. Alternative Erklärungen zu schwierigen Konzepten geben
j. Timer starten und im UI anzeigen
k. Karten im UI anzeigen
l. Webrecherche über Tavily
m. Rechercheergebnisse knapp erklären lassen
n. In eigenen Vorlesungs-PDFs nachschlagen
o. RAG-Suche in Skripten, PDFs und Session-Summaries
p. Spontane Schaubilder / Skizzen / Infografiken erzeugen
q. Bereits erzeugte Schaubilder wiederfinden und erneut anzeigen
r. Asset-Memory für generierte Schaubilder
s. Aktienkurse und Charts anzeigen
t. Simulationen starten
u. Interaktive Beispiele anzeigen, z.B. Bienen, Sortierung, neuronale Netze
v. PowerPoint per Sprache steuern
w. Nächste Folie
x. Zurück
y. Präsentation starten
z. Content-Fenster frei verschieben
aa. Multi-Monitor-tauglich nutzbar
ab. Ergebnisse als UI-Widgets statt nur als Sprache anzeigen
ac. Fokus-Modus: „Hör weg“ / „Weiter geht’s“
ad. Chat-Modus ohne ständiges Triggerwort, wenn bewusst aktiviert
ae. Sofortiger Stopp laufender Sprachausgabe bei Unterbrechung

---

## 1.3 Binde Trinity vollständig ein — aktiver Lecturer Companion

**Highlights:**
In der Vollintegration wird Trinity zum proaktiven Co-Piloten im Hörsaal. Sie analysiert die Vorlesung live, gibt Hinweise, erkennt mögliche Fehler, schlägt Visualisierungen oder Aufgaben vor, fungiert als privater AirPod-Souffleur und kann Informationen per UI-Bubble oder Telegram senden. Proaktiver Heartbeat, Bubbles, Souffleur-Skill, Telegram-Bridge und RAG-Automatisierung sind in der ToDo beschrieben. ([GitHub](https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/ToDo.md "raw.githubusercontent.com"))

a. Trinity als rhetorischer Co-Pilot im Hörsaal
b. Privater AirPod-Souffleur für Hinweise nur an den Dozenten
c. Dynamisches Audio-Routing zwischen Kopfhörer und Plenum-Lautsprecher
d. Befehl „wiederhole das für das Plenum“
e. Kontextbezogenes Wiederholen einer Erklärung für Studierende
f. Ausgabe über Kopfhörer oder Lautsprecher je nach Kontext
g. Proaktiver Heartbeat im Hintergrund
h. Regelmäßige Analyse des Live-Transkripts
i. Analyse auf logische Fehler
j. Hinweis auf alternative Perspektiven
k. Hinweis auf inhaltliche Ergänzungen
l. Hinweis auf potenziell unklare Aussagen
m. Warn-Bubbles im UI
n. Gelbe Bubble: alternative Perspektive
o. Rote Bubble: möglicher Fehler
p. Grüne Bubble: proaktives Visual / Schaubild
q. Blaue Bubble: proaktive Übungsaufgabe mit Lösung
r. Klick auf Bubble öffnet Vorschau-Fenster
s. Hinweise per Telegram-DM aufs Smartphone
t. Nutzung bei Beamer- oder Vollbildbetrieb ohne UI-Unterbrechung
u. Proaktive Ideen / „Geistesblitze“ per Telegram
v. Zwei-Wege-Telegram-Bridge für Text- und Sprachnachrichten
w. Teilen von Inhalten via ScreenSharing
x. Ausgabe über AirPod-Souffleur
y. Automatische Indexierung von Session-Summaries ins RAG
z. Langzeitgedächtnis über mehrere Vorlesungen hinweg
aa. Repetitions-Check gegen frühere Sessions
ab. Hinweis, ob ein Thema in diesem Semester bereits behandelt wurde
ac. Hinweis, wann ein Thema bereits behandelt wurde
ad. Hinweis, wenn ein Thema wiederholt, vertieft oder noch nicht behandelt wurde
ae. Automatisches Wiederfinden früherer Erklärungen
af. Automatisches Zeigen proaktiver Visuals geplant
ag. System- und Screen-Control geplant
ah. Fenster zwischen Bildschirmen verschieben
ai. Mirror / Extended Mode schalten
aj. Fallback-LLM-Resilienz geplant
ak. Übergang vom reaktiven Assistenten zum proaktiven Agentic Companion

---

# 2. Büro / Office Mode

## 2.1 Lass Trinity mithören — Office Recorder / Arbeitskontext

**Highlights:**
Im Büro dient Trinity zunächst als lokaler Kontext- und Telemetrie-Begleiter. Sie kann erfassen, woran gearbeitet wurde, z.B. Lehre, Teams, Mail oder Unterlagen. User Telemetry und Office Mode sind im README und in der Roadmap beschrieben. ([GitHub](https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/README.md "raw.githubusercontent.com"))

a. Umschaltbarer Modus zwischen Vorlesung und Büro
b. Direktere Reaktion im Büro statt langer Vortragsantworten
c. Mitschnitt beziehungsweise Kontextbildung für Büroarbeit
d. Erfassung von Arbeitsbereichen
e. Telemetrie: Aufzeichnen, wie viel Zeit in welchen Tätigkeiten anfällt
f. Tracking von Vorlesungsvorbereitung
g. Tracking von Teams-Sitzungen
h. Tracking von Mail-Bearbeitung
i. Tracking von Arbeit an Dokumenten
j. Tracking von Recherchezeit
k. Wöchentliche Auswertung analog zu Bildschirmzeit
l. Überblick über Arbeitsmuster
m. Unterstützung bei Selbstorganisation
n. Büro-Kontext für spätere Analysen nutzbar machen
o. Lokaler, privatsphärenorientierter Betrieb
p. Persönlicher Produktivitätsbegleiter
q. Grundlage für spätere proaktive Hinweise
r. Grundlage für bessere Vorlesungs- und Büroplanung

---

## 2.2 Aktiviere Heartbeat — proaktive Büroassistenz

**Highlights:**
Der Office-Heartbeat macht Trinity im Büro proaktiv. Sie kann regelmäßig Mails, Kalender und Teams prüfen, relevante Ereignisse erkennen und per UI-Bubble oder Telegram hinweisen. Das ist in der ToDo als Office-Heartbeat mit Intervall-Abruf lokaler Quellen beschrieben. ([GitHub](https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/ToDo.md "raw.githubusercontent.com"))

a. Office-Heartbeat als Hintergrundprozess
b. Regelmäßiges Prüfen von Mails
c. Regelmäßiges Prüfen von Kalender-Events
d. Regelmäßiges Prüfen von Teams-Nachrichten
e. Lokaler Abruf über AppleScript oder lokale Schnittstellen geplant
f. Benachrichtigung per UI-Bubble
g. Benachrichtigung per Telegram
h. Hinweise auf neue Kommunikation
i. Hinweise auf wichtige Kommunikation
j. Hinweise auf offene Aufgaben
k. Hinweise auf bevorstehende Termine
l. Hinweise auf Terminkonflikte
m. Hinweise auf liegengebliebene Mails
n. Hinweise auf relevante Dokumente oder Vorbereitungsaufgaben
o. Proaktive Unterstützung ohne explizite Nachfrage
p. Später: Hintergrundreflexion / Dreaming-Funktion
q. Später: Aufbereitung von Informationen in Ruhezeiten
r. Später: Vorbereitung künftiger Sessions
s. Später: Bereinigung von Transkriptions- oder TTS-Problemen
t. Später: Fallback-LLM-Resilienz bei lokalen Modellproblemen

---

## 2.3 Interagiere mit Trinity — produktiver Office Companion

**Highlights:**
Hier wird Trinity im Büro zum aktiven Arbeitsassistenten. Sie unterstützt bei Mails, Kalender, Recherche, Lehrvorbereitung, Zusammenfassungen und Schreibstil. Mail-Assistent, Writing Sample RAG, Drafting, Lecture Prep Support und Deep Office RAG sind in der ToDo beschrieben. ([GitHub](https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/ToDo.md "raw.githubusercontent.com"))

a. Lokale Mail-Integration
b. Mails lesen
c. Mail-Kontext verstehen
d. Relevante alte Mails finden
e. Alte Mail-Antworten als Schreibprobe analysieren
f. Writing-Sample-RAG für den eigenen Stil
g. Mail-Entwürfe im eigenen Stil erstellen
h. Antworten auf Basis früherer Kommunikation vorbereiten
i. Kalenderunterstützung
j. Termine erkennen und einordnen
k. Rechercheunterstützung
l. Webrecherche und lokale Recherche kombinieren
m. Vorbereitung von Vorlesungsunterlagen
n. Unterstützung beim Erarbeiten von Lehrmaterial
o. Fragen zu eigenen Unterlagen beantworten
p. Zusammenfassungen nachträglich abrufen
q. Zusammenfassung der letzten Session auf Zuruf erstellen
r. Editable UI Summary: Zusammenfassungen im UI bearbeiten
s. Eigene Notizen zu Summaries ergänzen
t. Office-RAG für Mails und Dokumente geplant
u. Automatischer Zugriff auf relevante Ordner geplant
v. Automatische Indexierung von Lehre- und Thesen-Ordnern geplant
w. Sachverhalte interaktiv klären
x. Weniger Vortragsmodus, mehr Arbeitsdialog
y. Unterstützung bei administrativer Arbeit
z. Unterstützung bei wissenschaftlicher und didaktischer Vorbereitung

---

## 2.4 Nutze Trinity als Analysewerkzeug — Dokumente auf die UI legen

**Highlights:**
Trinity soll lokale Dateien per Drag & Drop aufnehmen, Pfade erkennen, Dokumente lesen und mit spezialisierten Agenten analysieren. Document Intelligence, File-Drop, PDF/Word/Excel-Parsing, Begutachtungs-Agenten, Speicherung und Anzeige der Ergebnisse sind in README und ToDo beschrieben. ([GitHub](https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/README.md "raw.githubusercontent.com"))

a. Drag & Drop lokaler Dateien auf Trinity-Icon / UI
b. Erkennen lokaler Dateipfade
c. Einlesen lokaler Dokumente
d. Dokument-Pfade automatisch interpretieren
e. PDF-Analyse
f. Word-Dokument-Analyse
g. Excel-Auswertungen einlesen
h. Tabellen interpretieren
i. Thesen analysieren
j. Seminararbeiten analysieren
k. Begutachtung von Seminararbeiten
l. Korrektur- und Review-Agenten
m. Fachliche Rückmeldung erzeugen
n. Didaktische Rückmeldung erzeugen
o. Strukturelle Rückmeldung erzeugen
p. Hinweise auf Schwächen, Lücken oder Inkonsistenzen
q. Zusammenfassung langer Dokumente
r. Extraktion zentraler Argumente
s. Vergleich mit Bewertungskriterien
t. Ergebnisse als Reviews oder Notes speichern
u. Ergebnisse nach Abschluss im UI anzeigen
v. Dynamic Progress Ring beim Einlesen und Analysieren
w. Orange: Reading / Parsing
x. Rot: Analyzing / Denken
y. Document Intelligence als zentrale Büro-Funktion
z. Deep Office RAG für wiederverwendbares Dokumentenwissen
aa. Ordner-Integration für Lehre und Thesen
ab. Lokale Analyse sensibler Prüfungs-, Lehr- und Forschungsdokumente
ac. Agentische Auswertung statt einfachem Datei-Upload

---

# 3. Querschnittsfunktionen in beiden Modi

## 3.1 Local First / Datenschutz / DSGVO

**Highlights:**
Trinity ist auf maximale lokale Kontrolle ausgelegt. Sprache, Transkripte, Summaries, RAG und Dokumente sollen primär lokal verarbeitet werden. Das README hebt Local First, DSGVO und lokale Verarbeitung explizit hervor. ([GitHub](https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/README.md "raw.githubusercontent.com"))

a. Komplett lokaler Betrieb als primäre Lösung
b. Cloud-Dienste optional
c. Lokale Spracherkennung möglich
d. Lokale LLM-Nutzung möglich
e. Lokale Text-to-Speech-Ausgabe möglich
f. Lokale RAG-Wissensbasis möglich
g. Lokale Speicherung von Transkripten
h. Lokale Speicherung von Summaries
i. Lokale Speicherung von Dokumentanalysen
j. Lokale Bildgenerierung perspektivisch und teilweise bereits vorgesehen
k. Lokale Musik- und Videogenerierung über ComfyUI
l. Keine zwingende Übertragung sensibler Daten an externe Anbieter
m. Geeignet für Lehr-, Forschungs- und Prüfungskontexte
n. DSGVO-orientierter Hörsaalbetrieb über Dozenten-Mikrofon
o. Keine gezielte Aufzeichnung von Studierendenstimmen
p. Kontrollierbare Datenhaltung
q. Universitär anschlussfähige Datenschutzlogik

---

## 3.2 Modellagnostik

**Highlights:**
Trinity ist nicht auf ein einzelnes Modell festgelegt. Im Tech-Stack werden lokale Modelle über LM Studio sowie OpenRouter als Fallback genannt. Dadurch kann je nach Datenschutz, Leistung und Aufgabe gewechselt werden. ([GitHub](https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/README.md "raw.githubusercontent.com"))

a. Nicht an ein bestimmtes LLM gebunden
b. Lokale Modelle über LM Studio möglich
c. Lokale Modelle über Ollama oder ähnliche Backends denkbar
d. Externe Modelle über OpenRouter möglich
e. Fallback-LLMs geplant
f. Wechsel zwischen kleinen, schnellen und großen, leistungsfähigen Modellen
g. Unterschiedliche Modelle für unterschiedliche Aufgaben
h. Kleines Modell für Routing
i. Größeres Modell für Analyse
j. Lokales Modell für sensible Daten
k. Cloud-Modell für unkritische Recherche optional
l. Modellwechsel ohne grundlegende Änderung der Nutzerlogik
m. Zukunftssicher gegenüber neuen Open-Source- und Cloud-Modellen
n. Agentenarchitektur erleichtert Modell-Spezialisierung

---

## 3.3 Agentenfähigkeit / Skill-System

**Highlights:**
Das Agenten-System ist der Kern der Erweiterbarkeit. Das Repo beschreibt unabhängige Agent-Skills wie Office Mode, Lecture Mode, RAG, WebSearch, Image, Simulation, PowerPoint, ComfyUI, Summary und Document Intelligence. ([GitHub](https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/README.md "raw.githubusercontent.com"))

a. Trinity als agentisches Assistenzsystem
b. Agentic Router entscheidet, welcher Skill zuständig ist
c. Jeder Skill kann als eigener Agent organisiert werden
d. Dynamische Registrierung neuer Skills
e. RAG-Agent für Vorlesungs-PDFs, Mails und Session-Summaries
f. WebSearch-Agent für Echtzeit-Websuche
g. Image-Agent für Infografiken und Skizzen
h. Simulation-Agent für interaktive Simulationen
i. PowerPoint-Agent für Präsentationssteuerung
j. ComfyUI-Agent für lokale Bild-, Musik- und Videogenerierung
k. Summary-Agent für Zusammenfassungen und RAG-Indexierung
l. Document-Intelligence-Agent für Seminararbeiten, Thesen und Excel-Dateien
m. Office-Agent für Mails, Kalender und produktiven Support
n. Telemetrie-Agent für Arbeitszeitanalyse
o. Heartbeat-Agent für proaktive Hinweise
p. Telegram-Agent für Smartphone-Kommunikation
q. Souffleur-Agent für Audio-Routing
r. Asset-Memory-Agent für Schaubilder
s. Erweiterbar durch neue Spezialagenten
t. Modular statt monolithisch
u. Macht lokalen Betrieb realistischer, weil Aufgaben verteilt und spezialisiert werden können
v. Macht Trinity langfristig anpassbar an neue Modelle, Hardware und Lehrszenarien

---

## 3.4 RAG-Gedächtnis / Deep Memory

**Highlights:**
RAG ist die Brücke zwischen einzelnen Vorlesungen, eigenen Dokumenten und langfristigem Gedächtnis. Session-Summaries werden laut README automatisch in das Langzeitgedächtnis übernommen; die ToDo nennt zusätzlich RAG-Indexierung von Sitzungsprotokollen und Repetitions-Check. ([GitHub](https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/README.md "raw.githubusercontent.com"))

a. Lokale Wissensbasis
b. Indexierung von Vorlesungs-PDFs
c. Indexierung von Skripten
d. Indexierung von Session-Summaries
e. Indexierung von Sitzungsprotokollen
f. RAG-Abfragen während der Vorlesung
g. RAG-Abfragen im Büro
h. Semesterweites Gedächtnis
i. Erinnerung an behandelte Themen
j. Erinnerung an betonte Punkte
k. Erinnerung an Fehler im Skript
l. Erinnerung an offene Punkte
m. Erinnerung an spontane Ergänzungen
n. Prüfung, ob ein Thema bereits behandelt wurde
o. Prüfung, wann ein Thema behandelt wurde
p. Repetitions-Check
q. Deep Office RAG für Mail-Postfach geplant
r. Ordner-Integration für Lehre und Thesen geplant
s. Verbindung von Vorlesung, Büro, Dokumenten und Kommunikation
t. Grundlage für langfristige persönliche Wissensassistenz

---

## 3.5 UI, Visualisierung und Medien

**Highlights:**
Trinity kann Inhalte nicht nur sprechen, sondern im UI anzeigen: Timer, Karten, Infografiken, Simulationen, Bubbles, Dokumentanalysen und Medien. Das README beschreibt UI-Payloads, Content-Fenster, Glasmorphismus, Karten, Timer, Simulationen und Mediengenerierung. ([GitHub](https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/README.md "raw.githubusercontent.com"))

a. Avatar-UI
b. Content-Fenster
c. Frei verschiebbare Fenster
d. Multi-Monitor-Setup
e. UI-Payloads für visuelle Ergebnisse
f. Timer-Anzeige
g. Karten-Anzeige
h. Schaubilder
i. Skizzen
j. Infografiken
k. Simulationen
l. Bienen-Simulation
m. Bubble-Sort-Simulation
n. Neuronales-Netz-Simulation
o. Aktiencharts
p. Dokumentanalyse-Ausgaben
q. Editable UI Summaries
r. Warn-Bubbles
s. Vorschau-Fenster bei Bubble-Klick
t. Dynamic Progress Ring geplant
u. Reading / Parsing-Anzeige
v. Thinking / Analyzing-Anzeige
w. Bildgenerierung über fal.ai oder lokal über ComfyUI
x. Lokale Bildgenerierung via Flux
y. Musikgenerierung via AceStep
z. Videogenerierung via LTX
aa. Asset-Memory für erzeugte Schaubilder

---

## 3.6 Sprache, Audio und Souffleur

**Highlights:**
Sprache ist das natürliche Interface. Trinity nutzt STT, TTS, Wake-Word, Unterbrechungserkennung und perspektivisch dynamisches Audio-Routing zwischen privatem Kopfhörer und Plenum. faster-whisper, macOS `say`, Wake-Word und Souffleur-Routing sind im Repo genannt. ([GitHub](https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/README.md "raw.githubusercontent.com"))

a. Sprache zu Text über faster-whisper
b. VAD-basierte Spracherkennung
c. Text zu Sprache über macOS `say`
d. AirPod als privates Interface
e. Wake-Word-Interaktion in aktiven Modi
f. Triggerwort am Anfang oder Ende eines Satzes
g. Kontextnutzung vor und nach Wake-Word
h. Sofortiges Unterbrechen laufender Ausgabe
i. Fokus-Modus / Hör-weg-Modus
j. Chat-Modus bei bewusster Aktivierung
k. AirPod-Souffleur
l. Private Hinweise nur für den Dozenten
m. Umschalten auf Plenum-Speaker
n. Wiederholen von Erklärungen für alle
o. Sprachsteuerung von PowerPoint
p. Sprachsteuerung von Sessions
q. Sprachsteuerung von Visualisierungen
r. Sprachsteuerung von Recherche und RAG

---

# 4. Entwicklungsstand / Roadmap-Charakter

**Highlights:**
Ein Teil ist bereits implementiert, ein Teil ist geplant. Besonders relevant: Session Summarizer, RAG-Indexing, PowerPoint-Steuerung, Chat-Modus, Fokus-Modus, Heartbeat, UI-Bubbles, Souffleur, Telegram, Asset-Memory und ComfyUI-Integration sind in der ToDo teilweise als erledigt markiert; Office Mode, Document Intelligence, Deep Office RAG, Telemetrie und System-Control sind Roadmap-Themen. ([GitHub](https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/ToDo.md "raw.githubusercontent.com"))

a. Bereits vorhanden: modulares Skill-System
b. Bereits vorhanden: Session Summarizer
c. Bereits vorhanden: Summary der letzten Session
d. Bereits vorhanden: Editable UI Summary
e. Bereits vorhanden: RAG-Indexing von Summaries
f. Bereits vorhanden: PowerPoint-Steuerung
g. Bereits vorhanden: Natural Conversation Mode
h. Bereits vorhanden: Fokus-Modus
i. Bereits vorhanden: Interrupt-Handling
j. Bereits vorhanden: proaktiver Heartbeat
k. Bereits vorhanden: Bubbles für Hinweise
l. Bereits vorhanden: Souffleur-Skill
m. Bereits vorhanden: Telegram-Bridge
n. Bereits vorhanden: Asset-Memory für Schaubilder
o. Bereits vorhanden: Simulationen
p. Bereits vorhanden: lokale ComfyUI-Medienintegration
q. Geplant: Office Mode als eigene Modus-Weiche
r. Geplant: lokaler Mail-Assistent
s. Geplant: Writing Sample RAG
t. Geplant: Office-Heartbeat
u. Geplant: File-Drop und Document Intelligence
v. Geplant: Begutachtungs-Agenten
w. Geplant: Deep Office RAG
x. Geplant: User Telemetry Dashboard
y. Geplant: Dreaming-Funktion
z. Geplant: System- und Screen-Control
aa. Geplant: Fallback-LLM-Resilienz
ab. Geplant: Native Standalone-App

---

# 5. Kurzform als Erklärlogik für Professorinnen und Professoren

## Im Hörsaal

**1. Trinity hört nur zu.**
Sie zeichnet die Vorlesung passiv auf, erstellt Transkript und Summary, merkt sich Hervorhebungen, erkannte Skriptfehler, spontane Ergänzungen und offene Punkte.

**2. Trinity hilft niedrigschwellig auf Zuruf.**
Sie beantwortet kurze Fragen, sucht im Skript, startet Timer, zeigt Karten, erzeugt Schaubilder, startet Simulationen und steuert PowerPoint.

**3. Trinity wird vollständig eingebunden.**
Sie wird zum proaktiven Lecturer Companion mit Souffleur, Heartbeat, Fehlerhinweisen, Perspektivwechseln, Visual-Vorschlägen, Übungsaufgaben, Telegram-Hinweisen und semesterweitem Gedächtnis.

## Im Büro

**1. Trinity hört mit und baut Arbeitskontext auf.**
Sie erkennt, woran gearbeitet wird, und kann Telemetrie über Lehre, Teams, Mails, Recherche und Dokumentarbeit aufbauen.

**2. Trinity aktiviert Heartbeat.**
Sie prüft proaktiv Mails, Kalender und Teams und meldet relevante Ereignisse per UI oder Telegram.

**3. Trinity wird zum Office Companion.**
Sie hilft bei Mails, Kalender, Recherche, Vorlesungsvorbereitung, Zusammenfassungen und Schreibstil.

**4. Trinity wird zum Analysewerkzeug.**
Man legt Dokumente auf die UI; Trinity erkennt Pfade, liest PDFs, Word-Dateien und Excel-Tabellen, analysiert Seminararbeiten oder Thesen und erstellt Reviews.
