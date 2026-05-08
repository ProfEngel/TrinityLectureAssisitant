# Trinity ToDo – Nächste Schritte 🧞‍♀️

Hier sind die geplanten Erweiterungen für Trinity, die wir am Montag/Dienstag angehen:

## 0. Modularisierung & Skill-System (Architektur-Refactoring)
Ziel: Umstellung von monolithischen Funktionen auf ein modulares Skill-System im `agents/`-Verzeichnis.
- [ ] **Struktur-Migration:** Auslagerung aller Funktionen in die neue Struktur.
    - **Trinity Live-Skills:** (Echtzeit-Interaktion während der Vorlesung)
    - **Post-Processing Skills:** (Lokale Nachbereitung nach der Session)
- [x] **Skill-Standard:** Jeder Skill erhält einen eigenen Ordner mit `script.py` und `skill.md`.
    - *Beispiel: `agents/session_summarizer_agent/` (Post-Processing)*
- [ ] **Erweiterbarkeit:** Dynamische Registrierung neuer Skills.

## 1. Trinity Live-Skills (Echtzeit-Unterstützung)
Ziel: Erweiterung der Fähigkeiten während der aktiven Vorlesung.
- [x] **PowerPoint-Steuerung (Automation Agent):** 
    - AppleScript-Integration für Microsoft PowerPoint via `osascript`.
    - Sprachbefehle: "Nächste Folie", "Zurück", "Präsentation starten".
- [x] **Natural Conversation Mode (Chat-Modus):** 
    - "Lass uns quatschen" -> VAD-basierte Auto-Antwort ohne Triggerwort.
- [x] **Fokus-Modus ("Hör weg"):** 
    - "Bitte nicht zuhören" -> Trinity schaltet auf passiv, bis "Weiter geht's" gerufen wird.

## 2. Post-Processing & Nachbereitung (Lokal/Asynchron)
Ziel: Automatisierte Aufbereitung der Sitzungsdaten nach Ende der Vorlesung.
- [x] **Session Summarizer:** Automatisierte Erstellung von Zusammenfassungen inkl. Mitschreib-Blöcken und Transkriptionskorrektur.
- [x] **Summary "per Zuruf":**
    - Trigger-Befehl: "Trinity, Session beenden und zusammenfassen".
    - Workflow: Trinity schließt das Log-File, verschiebt es in `memory/` und startet automatisch den `session_summarizer_agent` Agent-Task.
- [x] **Review-Modus:** Trinity liest auf Wunsch die Zusammenfassung der letzten Session kurz vor Beginn der neuen vor.

## 3. Finetuning & UX
- [ ] **Interrupt-Handling:** Sofortiger Stopp der Sprachausgabe bei Unterbrechung.
- [ ] **Kontext-Gedächtnis:** Kurzzeitgedächtnis für die letzten 5-10 Interaktionen.

## 4. Zukünftige Features & Ideen (Phase 3)
- [ ] **Mail-Reader Agent (Experimentell):** 
    - Trinity soll (read-only) eingehende E-Mails überwachen (z.B. Krankmeldungen von Studenten kurz vor der Vorlesung).
    - Gibt dem Dozenten während der Vorlesung proaktiv Bescheid oder auf Zuruf ("Gibt es neue wichtige Mails?").

---
*Status: In Planung für KW 18/19*
