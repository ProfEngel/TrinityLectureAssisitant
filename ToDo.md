# Trinity ToDo – Nächste Schritte 🧞‍♀️

Hier sind die geplanten Erweiterungen für Trinity, die wir am Montag/Dienstag angehen:

## 1. PowerPoint-Steuerung (Automation Agent)
Ziel: Trinity kann Präsentationen per Sprachbefehl steuern.
- [ ] **AppleScript-Integration:** Funktionen zur Steuerung von Microsoft PowerPoint via `osascript`.
    - `next_slide()`: "Nächste Folie"
    - `prev_slide()`: "Zurück" / "Vorherige Folie"
    - `start_presentation()`: "Präsentation starten"
- [ ] **Trigger-Logik:** Erkennung der Befehle in `core/transcriber.py` (analog zu den UI-Befehlen).
- [ ] **Feedback:** Trinity bestätigt den Folienwechsel kurz ("Mache ich.", "Nächste Folie.").

## 2. Natural Conversation Mode (Chat-Modus)
Ziel: Ein Modus für lockere Gespräche ohne das Trigger-Wort "Trinity".
- [ ] **Modus-Umschaltung:**
    - "Lass uns quatschen" -> Aktiviert den Chat-Modus.
    - "Vorlesung starten" -> Zurück in den passiven Modus (mit Trigger-Wort).
- [ ] **Auto-Antwort-Logik:** Wenn `chat_mode = True`, triggert jede Spracherkennung nach einer definierten Stille-Zeit (VAD) automatisch eine Antwort.
- [ ] **UI-Feedback:** Visueller Indikator im Avatar-Fenster, dass Trinity gerade aktiv "mitlauscht".

## 3. Finetuning & UX
- [ ] **Interrupt-Handling:** Sicherstellen, dass Trinity sofort verstummt, wenn man sie im Chat-Modus unterbricht.
- [ ] **Kontext-Gedächtnis:** Im Chat-Modus die letzten 5-10 Gesprächswendungen präsenter im Prompt halten.

---
*Status: In Planung für KW 18/19*
