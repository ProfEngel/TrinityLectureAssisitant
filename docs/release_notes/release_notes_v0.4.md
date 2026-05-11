# Trinity Assistant v0.4 🚀

Das ist das größte Architektur- und Feature-Update seit Beginn des Projekts! Trinity ist jetzt kein monolithisches Skript mehr, sondern ein hochskalierbares, multi-agentisches System, das perfekt auf die Live-Lehre zugeschnitten ist.

## 🌟 Highlights & Neue Features

### 🧩 1. Multi-Agentische Architektur (Skill-System)
Der ehemals große "Core-Monolith" (`brain.py`) wurde restlos bereinigt. Trinity lädt nun beim Start dynamisch alle "Skills" als autonome Agenten aus dem `agents/`-Ordner.
*   **Plug & Play:** Neue Features (Skills) können extrem einfach hinzugefügt werden, indem ein neuer Ordner mit einer `script.py` in `agents/` abgelegt wird. Trinity lernt diese Features vollautomatisch beim nächsten Systemstart.

### 🎭 2. Neue & optimierte Live-Skills (Die 11 Agenten)
Aus den vormals rudimentären Funktionen sind 11 vollwertige Agenten entstanden:
*   **PowerPoint-Agent:** Steuert Microsoft PowerPoint Präsentationen nativ unter macOS rein durch Sprachbefehle (*"Nächste Folie"*, *"Präsentation starten"*).
*   **Image-Agent:** Erstellt via fal.ai blitzschnell minimalistische, deutsche Metapherbilder und Schaubilder, die durch neues Prompt-Tuning perfekt für kurze Einblendungen in Vorlesungen sind.
*   **Chat Mode-Agent:** Ein neuer Befehl (*"Lass uns quatschen"*) versetzt Trinity in einen gesprächigen, natürlichen Konversationsmodus, der von der sonst extrem kurzen 1-2-Sätze-Regel abweicht.
*   **Focus-Agent:** (*"Hör weg"*) Trinity kann vorübergehend in einen passiven Fokus-Modus versetzt werden.
*   **Review-Agent:** Kann das aggregierte Summary der vergangenen Vorlesung abrufen, um die Klasse zum Start der Sitzung wieder abzuholen.
*   *Zudem überarbeitet:* Maps-Agent, Stock-Agent, WebSearch-Agent (Tavily), Simulation-Agent, Timer-Agent und Summary-Agent.

### 🔒 3. Vollständige DSGVO-Konformität im Hörsaal
Das System wurde konzeptionell für den europäischen Datenschutz optimiert:
Die Spracheingabe erfolgt exklusiv über einen einzelnen AirPod des Dozenten (ca. 20cm Aufnahmeradius). Das bedeutet: Stimmen, Zwischenrufe oder Fragen von Studierenden aus dem Saal werden *nicht* erfasst, transkribiert oder in den lokalen Logfiles gespeichert.

### ⚡ 4. One-Click-Installation für Mac-Nutzer
Die Installation ist ab sofort ein Kinderspiel – auch ohne Entwickler-Kenntnisse.
Das neue `install_mac.sh`-Skript lädt das Projekt herunter, erstellt eine isolierte virtuelle Umgebung (`venv`) und platziert einen komfortablen **"Starte_Trinity"**-Button direkt auf dem Desktop. 

### 📑 5. Umfangreiches CheatSheet
Für den schnellen Überblick während der Vorlesung wurde ein umfangreiches `CheatSheet.md` hinzugefügt, das alle Sprachbefehle, Trigger und Konfigurationen auf einen Blick bündelt.

---

Trinity ist nun modularer und robuster denn je und bereit für den produktiven Einsatz im Hörsaal! 🧞‍♀️
