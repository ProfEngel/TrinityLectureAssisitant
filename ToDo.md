# Trinity ToDo – Nächste Schritte 🧞‍♀️

Hier sind die geplanten Erweiterungen für Trinity:

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
- [X] **Kontext-Gedächtnis:** Kurzzeitgedächtnis für die letzten 5-10 Interaktionen (via Rolling-Chunk-Context implementiert).


## 4. Zukünftige Features & Ideen (Phase 3: Cognitive & System Evolution)

> [!IMPORTANT]
> Diese Erweiterungen markieren den Übergang von Trinity als reaktivem Assistenten hin zu einem proaktiven "Agentic Companion". Dies erfordert einen architektonischen Shift hin zu einem permanent laufenden Hintergrund-Dienst (Daemon).

- [x] **Proaktiver Heartbeat (2-Minuten-Takt):**
  - [x] Kontinuierliche Analyse des Transkripts auf Fehler in Aussagen.
  - [x] Einblendung alternativer Perspektiven oder Ergänzungen.
  - [ ] **Repetitions-Check:** Abgleich mit RAG (vorherige Sessions), um Redundanzen aufzuzeigen.
  - [ ] **Proaktive Visuals:** Automatisches Zeigen von Schaubildern/Erklärungen auf dem Second Screen.
  - [x] **UI-Integration (Bubbles):**
    - [x] Anzeige kleiner Benachrichtigungs-Bubbles über dem Trinity-Icon:
      - **Gelb:** Alternative Perspektiven (Counter).
      - **Rot:** Fehler in Aussagen (Counter).
      - **Grün:** Proaktive Visuals/Schaubilder (Counter).
      - [x] **Blau:** Proaktive Übungsaufgaben (Generiert eine Aufgabe, gefolgt von Leerzeilen und dann der Lösung zum Scrollen).
    - [x] **Interaktion:** Klick auf Bubble öffnet Vorschau-Fenster.
    - [x] **Action-Trigger:** Option zum Teilen via ScreenSharing oder Ausgabe über den "AirpodSouffleur" (TTS).
- [x] **Souffleur-Skill (Dynamisches Audio-Routing):**
  - [x] Umschalten der Audio-Ausgabe zwischen Kopfhörer (Privat) und Lautsprecher (Plenum) via `[SPEAKER]` Tag.
  - [x] Kontextbezogenes Wiederholen von Erklärungen für die Zuhörerschaft.
- [x] **RAG-Automatisierung:** Automatischer Import von Session-Summaries in die Wissensbasis (RAG), um das Langzeitgedächtnis zu stärken.
- [x] **Telegram-Bridge:** Proaktive Ideen und "Geistesblitze" von Trinity direkt aufs Handy (inkl. Two-Way Listener für Text- und Sprachnachrichten).
- [x] **Schaubilder-Gedächtnis (Asset-Memory):** Trinity behält den Überblick über generierte Schaubilder im Projektordner, kennt deren Inhalt/Kontext und kann diese auf Zuruf jederzeit erneut anzeigen.
- [ ] **Dreaming-Funktion (Deep Reflection):**
  - [ ] Hintergrund-Verarbeitung von Informationen in Ruhezeiten.
  - [ ] **Akzent-Korrektur:** Intelligente Bereinigung von TTS-Fehlern (durch Akzent bedingt) im "Schlaf".
  - [ ] Aufbereitung von Inhalten für zukünftige Sessions.
- [ ] **System- & Screen-Control:**
  - [ ] "Trinity, zeig mir das auf beiden Bildschirmen" -> Toggle Mirror/Extended Mode.
  - [ ] Verschieben von Trinity-Fenstern zwischen Desktops via Sprachbefehl.
- [ ] **Onboarding & UX:**
  - [ ] Tutorial für Erstbenutzer erstellen.
- [ ] **Simulation Engine Updates:**
  - [ ] Bienensimulation erweitern: Einstellbare Parameter für mehrere Bienenstöcke, Blumen und Fressfeinde.

---

*Status: In Planung für KW 19/20 (Architektur-Erweiterung erforderlich)*
