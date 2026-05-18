# Trinity ToDo – Nächste Schritte 🧞‍♀️

Hier sind die geplanten Erweiterungen für Trinity:

## [v0.8.2] - 2026-05-18
- [X] **Secure Sandbox Environment (Isolierte Programmierung):** Aufbau einer 100% sicheren, isolierten Python-Programmierumgebung auf WebAssembly-Basis (Pyodide).
- [X] **Data Science & ML Support:** Volle Integration von Numpy, Pandas, Matplotlib, Seaborn, SymPy, SciPy und Scikit-Learn in der Sandbox.
- [X] **Bypass CORS in WebEngine:** Gezielte Aufhebung der CORS-Beschränkungen in PySide6 QWebEngineView zum Herunterladen beliebiger Online-Datensätze direkt im Sandbox-Kontext.
- [X] **Visual-Output (Plotly & Matplotlib):** Unterstützung für interaktives Rendering von Plotly-Diagrammen und statischen Matplotlib-Visualisierungen.

## [v0.8.1] - 2026-05-17
- [X] **Trinity Chat-Mode:** Implementierung eines ressourcenschonenden, rein text-/UI-basierten Chat-Modus.
- [X] **Dynamische Modus-Umschaltung:** Nahtloses Live-Wechseln zwischen Büro-, Vorlesungs- und Chat-Modus via Flüstern ("büromodus aktivieren") ohne App-Neustart.
- [X] **Session Protokollierung:** Umstellung auf `raw_session_ddmmmyyyy_hhmm.md` und sauberes Logging aller UI-Chats.

## [v0.8.0] - 2026-05-15
- [X] **Rebranding: Academic Personal Concierge**: Vollständige Neuausrichtung weg vom "Assistenten" hin zum "Concierge".
- [X] **UI Slogan Integration**: Dynamische Einblendung des Slogans im Avatar-UI.
- [X] **Roadmap Expansion**: Integration von Trinity Mobile in die strategische Planung.
- [X] **Positioning Document**: Erstellung und Integration von `warum_trinity.md` und neuen Infografiken.

## [v0.7.8] - 2026-05-14

- [X] **Feat: Verified Linux LTX 2.3 I2V Workflow**: API-Integration für I2V auf Linux-Systemen erfolgreich validiert.

## [v0.7.7] - 2026-05-13

- [X] **Fix: Cross-Platform LoRA Paths**: Alle Backslashes in LoRA-Pfaden wurden durch Vorwärtsslashs ersetzt (Kompatibilität für Linux-Server).

## [v0.7.6] - 2026-05-13

- [X] **Fix: LTX 2.3 Video Workflow**: Skript nutzt nun native Workflow-Defaults für Auflösung und Dauer.
- [X] **Optimization: ComfyUI Input Injection**: Nur noch Prompt und Bild werden überschrieben, um Stabilität zu erhöhen.

## [v0.7.5] - 2026-05-13

- [X] **Feat: Session Summarizer Activation**: Agent ist nun voll funktionsfähig.
- [X] **Feat: Deferred Summarization**: Unterstützung für "Zusammenfassung der letzten Session" (Büro-Workflow).
- [X] **Feat: Editable UI Summary**: Zusammenfassungen im UI sind nun für Notizen editierbar.
- [X] **Fix: RAG Indexing**: Sitzungsprotokolle in `memory/summaries/` werden nun zuverlässig indexiert.

## 0. Modularisierung & Skill-System (Architektur-Refactoring)

Ziel: Umstellung von monolithischen Funktionen auf ein modulares Skill-System im `agents/`-Verzeichnis.

- [X] **Struktur-Migration:** Auslagerung aller Funktionen in die neue Struktur.
  - **Trinity Live-Skills:** (Echtzeit-Interaktion während der Vorlesung)
  - **Post-Processing Skills:** (Lokale Nachbereitung nach der Session)
- [X] **Skill-Standard:** Jeder Skill erhält einen eigenen Ordner mit `script.py` und `skill.md`.
  - *Beispiel: `agents/session_summarizer_agent/` (Post-Processing)*
- [X] **Erweiterbarkeit:** Dynamische Registrierung neuer Skills.

## 1. Trinity Live-Skills (Echtzeit-Unterstützung)

Ziel: Erweiterung der Fähigkeiten während der aktiven Vorlesung.

- [X] **PowerPoint-Steuerung (Automation Agent):**
  - AppleScript-Integration für Microsoft PowerPoint via `osascript`.
  - Sprachbefehle: "Nächste Folie", "Zurück", "Präsentation starten".
- [X] **Natural Conversation Mode (Chat-Modus):**
  - "Lass uns quatschen" -> VAD-basierte Auto-Antwort ohne Triggerwort.
- [X] **Fokus-Modus ("Hör weg"):**
  - "Bitte nicht zuhören" -> Trinity schaltet auf passiv, bis "Weiter geht's" gerufen wird.

## 2. Post-Processing & Nachbereitung (Lokal/Asynchron)

Ziel: Automatisierte Aufbereitung der Sitzungsdaten nach Ende der Vorlesung.

- [X] **Session Summarizer:** Automatisierte Erstellung von Zusammenfassungen inkl. Mitschreib-Blöcken und Transkriptionskorrektur.
- [X] **Summary "per Zuruf":**
  - Trigger-Befehl: "Trinity, Session beenden und zusammenfassen".
  - Workflow: Trinity schließt das Log-File, verschiebt es in `memory/` und startet automatisch den `session_summarizer_agent` Agent-Task.
- [X] **Review-Modus:** Trinity liest auf Wunsch die Zusammenfassung der letzten Session kurz vor Beginn der neuen vor.

## 3. Finetuning, UX & Moods

- [X] **Emotional Spectrum (Mood Update v0.4.3):**
  - [X] **Refined Love Mode:** Heart eyes, blush effect, and dynamic floating heart particles.
  - [X] **Refined Angry Mode:** Sharp trapezoidal eyes, visor jitter/shake, and aggressive particles (sparks/fire).
  - [X] **State Persistence:** Automatic revert to idle after 5 seconds.
- [X] **Interrupt-Handling:** Sofortiger Stopp der Sprachausgabe bei Unterbrechung (Wake-Word Terminate).
- [ ] **Dynamic Progress Indicators (Ring-UI):**
  - [ ] Kreisförmige Fortschrittsanzeige um den Avatar.
  - [ ] **Farbcodes:** Orange für Einlesen/Parsing (0-100%), Rot für Analyse/Denken.
- [ ] **Kontext-Gedächtnis:** Kurzzeitgedächtnis für die letzten 5-10 Interaktionen (via Rolling-Chunk-Context implementiert).

## 4. Zukünftige Features & Ideen (Phase 3: Cognitive & System Evolution)

> [!IMPORTANT]
> Diese Erweiterungen markieren den Übergang von Trinity als reaktivem Assistenten hin zu einem proaktiven "Agentic Companion". Dies erfordert einen architektonischen Shift hin zu einem permanent laufenden Hintergrund-Dienst (Daemon).

- [X] **Proaktiver Heartbeat (2-Minuten-Takt):**

  - [X] Kontinuierliche Analyse des Transkripts auf Fehler in Aussagen.
  - [X] Einblendung alternativer Perspektiven oder Ergänzungen.
  - [ ] **Repetitions-Check:** Abgleich mit RAG (vorherige Sessions), um Redundanzen aufzuzeigen.
  - [ ] **Proaktive Visuals:** Automatisches Zeigen von Schaubildern/Erklärungen auf dem Second Screen.
  - [ ] **Variabler Heartbeat:** Taktzeiten dynamisch und variabel anpassen (z.B. im Chat-, Büro- oder Headless-Modus).
  - [X] **UI-Integration (Bubbles):**
    - [X] Anzeige kleiner Benachrichtigungs-Bubbles über dem Trinity-Icon:

      - **Gelb:** Alternative Perspektiven (Counter).
      - **Rot:** Fehler in Aussagen (Counter).
      - **Grün:** Proaktive Visuals/Schaubilder (Counter).

      - [X] **Blau:** Proaktive Übungsaufgaben (Generiert eine Aufgabe, gefolgt von Leerzeilen und dann der Lösung zum Scrollen).
    - [X] **Interaktion:** Klick auf Bubble öffnet Vorschau-Fenster.
    - [X] **Action-Trigger:** Option zum Teilen via ScreenSharing oder Ausgabe über den "AirpodSouffleur" (TTS).
- [X] **Souffleur-Skill (Dynamisches Audio-Routing):**

  - [X] Umschalten der Audio-Ausgabe zwischen Kopfhörer (Privat) und Lautsprecher (Plenum) via `[SPEAKER]` Tag.
  - [X] Kontextbezogenes Wiederholen von Erklärungen für die Zuhörerschaft.
- [X] **RAG-Automatisierung:** Automatischer Import von Session-Summaries in die Wissensbasis (RAG), um das Langzeitgedächtnis zu stärken.
- [X] **Telegram-Bridge:** Proaktive Ideen und "Geistesblitze" von Trinity direkt aufs Handy (inkl. Two-Way Listener für Text- und Sprachnachrichten).
- [X] **Schaubilder-Gedächtnis (Asset-Memory):** Trinity behält den Überblick über generierte Schaubilder im Projektordner, kennt deren Inhalt/Kontext und kann diese auf Zuruf jederzeit erneut anzeigen.
- [ ] **Dreaming-Funktion (Deep Reflection & Knowledge Synthesis):**

  - [ ] Hintergrund-Verarbeitung von Informationen in Ruhezeiten.
  - [ ] **Wissens-Synthese:** Verarbeiten der Sessions zu komplexem Verständniswissen.
    - [ ] Automatisches Tagging von Inhalten und Schlüsselkonzepten.
    - [ ] Graphen-basierte Verlinkung verwandter Themen (Semantische Netze).
    - [ ] Relevanz-Gewichtung (Wichtiges stärken, Unwichtiges mit der Zeit depriorisieren/vergessen).
  - [ ] **Akzent-Korrektur:** Intelligente Bereinigung von TTS-Fehlern (durch Akzent bedingt) im "Schlaf".
  - [ ] Aufbereitung von Inhalten für zukünftige Sessions.
- [ ] **System- & Screen-Control:**

  - [ ] "Trinity, zeig mir das auf beiden Bildschirmen" -> Toggle Mirror/Extended Mode.
  - [ ] Verschieben von Trinity-Fenstern zwischen Desktops via Sprachbefehl.
- [X] **Secure Sandbox Environment (Isolierte Programmierung):**
  - [X] Bereitstellung einer sicheren Sandbox-Programmierumgebung für mathematische Berechnungen, Datenanalysen und Diagrammerstellung.
  - [X] Striktes Rechtemanagement: Vollständige Isolation, kein Zugriff auf das eigentliche Dateisystem oder Trinity-Kernkomponenten.
- [ ] **Onboarding & UX:**

  - [ ] Tutorial für Erstbenutzer erstellen (geplant ab Q3 2026).
  - [ ] **Naming Refactoring:** Prüfung des Namens "Lecturer Companion" als Alternative/Zusatz zu Trinity.
  - [ ] **Global Session Control:** Sessions direkt aus der UI beenden und neu starten, ohne den Prozess killen zu müssen.
- [ ] **LLM Resilience:**

  - [ ] Implementierung von Fallback-LLMs (z.B. Wechsel zu OpenRouter, wenn lokales Modell hakt).
- [ ] **User Telemetry (Dashboard):**

  - [ ] Tracking der Nutzung analog zu Apples Bildschirmzeit.
  - [ ] Auswertung: Stunden/Minuten in Vorlesungen (Lecture Mode), Teams-Sitzungen, Email-Bearbeitung pro Woche.
- [ ] **Headless Mode & CLI (Terminal-Chat):**
  - [ ] Headless-Betrieb für Linux/Ubuntu-Server.
  - [ ] Interaktiver Chat im Terminal über den CLI-Aufruf `trinity` (analog zum Hermes Agent).
- [ ] **Cross-Platform Packaging (Multi-OS Fertig-Apps):**
  - [ ] Fertige, installierbare App-Pakete für macOS, Windows 11, iOS, Android sowie Headless Ubuntu.
- [ ] **Multi-Domain & Lifestyle Concierge (Erweiterung für Jeden):**
  - [ ] Öffnung des Systems für Nicht-Lehrende. Trinity als persönlicher Concierge für jeden Lebensbereich (z.B. Ernährungsverläufe, Fitness, SmartHome-Steuerung etc. – wesentliche Basis-Agenten bereits vorhanden).
- [X] **Simulation Engine Updates:**

  - [X] Bienensimulation erweitern: Einstellbare Parameter für mehrere Bienenstöcke, Blumen und Fressfeinde.
  - [X] Fehlende Simulationen (Bubble Sort, Neuronales Netz) implementiert und `skill.md` aktualisiert.
- [X] **ComfyUI Media Integration (Local Generation):**

  - [X] **T2I/I2I:** Lokale Bildgenerierung via Flux2 (9b klein) für Schaubilder und Bearbeitungen.
  - [X] **T2A (Music):** Komplette Song-Generierung via AceStep 1.5 inkl. Stil/Lyrics-Extraktion.
  - [ ] **I2V (Video):** Erstellung von Kurzvideos aus Bildern via LTX 2.3 mit automatischer Skalierung. (Note: Aktuell Probleme bei der Einbindung, Prio niedrig).
  - [X] **Telegram/UI Dispatch:** Nahtlose Integration in die Telegram-Bridge und UI-Payloads.

## 5. Büro Modus (Office Companion)

Ziel: Trinity als Support-System im Büro-Alltag (Umschaltbar via Sprachbefehl/Whisper).

- [ ] **Modus-Weiche:** Manueller Wechsel zwischen "Vorlesung" (Lehre) und "Büro" (Support).
  - **Vorlesung:** Fokus auf Plenum-Interaktion, Souffleur-Routing, Schaubilder.
  - **Büro:** Fokus auf direkte Reaktion, keine langen "Vorträge", interaktive Klärung von Sachverhalten.
- [ ] **Email-Assistent (Local Integration):**
  - [ ] **Lese-Zugriff:** Auslesen lokaler Mails (macOS Mail App via AppleScript/Lokaler Scan).
  - [ ] **Writing Sample RAG:** Analyse alter Mail-Antworten als Stil-Vorlage (Schreibprobe).
  - [ ] **Drafting:** Erstellen von Mail-Entwürfen im eigenen Stil basierend auf RAG-Kontext.
- [ ] **Lecture Prep Support:** Unterstützung beim Erarbeiten von Unterlagen für die Vorlesung.
- [ ] **Office-Heartbeat (Proaktiv):**
  - [ ] Intervall-Abruf von Mails, Kalender-Events und Teams-Nachrichten (Lokal/AppleScript).
  - [ ] Benachrichtigung via UI-Bubbles oder Telegram.
- [ ] **File-Drop & Document Intelligence:**
  - [ ] **Drag & Drop UI:** Lokale Dateien (PDF, Word, Excel) einfach auf das Trinity-Icon "plumpsen" lassen.
  - [ ] **Document Parsing:** Einlesen und Interpretieren von Thesen, Seminararbeiten und Excel-Auswertungen.
  - [ ] **Specialized Agents (Begutachtung):** Dedizierte Agenten für die Korrektur/Begutachtung von Seminararbeiten.
  - [ ] **Storage & Display:** Ergebnisse (Reviews/Notes) speichern und nach Abschluss im UI anzeigen.
- [ ] **Deep Office RAG:**
  - [ ] Eigenes RAG-System für das Mail-Postfach.
  - [ ] Ordner-Integration: Automatischer Zugriff und Indexierung von "Lehre"- und "Thesen"-Ordnern.

---

*Status: In Planung für KW 19/20 (Architektur-Erweiterung erforderlich)*
