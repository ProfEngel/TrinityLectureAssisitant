# 🧞‍♀️ Trinity Assistant – CheatSheet

Dieses CheatSheet bietet dir eine schnelle Übersicht über alle Funktionen, Live-Skills und Konfigurationen von Trinity. 

---

## 🚀 Trinity Starten

Der empfohlene Weg, um Trinity zu starten, ist über den Standard-Launcher (nutzt OpenAI Whisper für die Spracherkennung):
```bash
python3 projects/Trinity_Assistant/trinity_launcher.py
```
*(Hinweis: Der `trinity_native_launcher.py` ist aktuell experimentell und funktioniert in dieser Umgebung nicht zuverlässig).*

---

## ⚙️ Einstellungen, Persönlichkeit & Daten

Trinity ist extrem anpassbar. Du hast die volle Kontrolle über ihre Persönlichkeit, ihr Wissen und ihre APIs.

### 1. API-Keys & Modelle (`core/config.json`)
Die technischen Einstellungen sind in der Datei `core/config.json` gespeichert.
**Tipp:** Du kannst diese Datei am besten über das mitgelieferte UI ändern:
```bash
python3 projects/Trinity_Assistant/core/settings_ui.py
```
*(Hier trägst du OpenRouter-Keys, Fal.ai-Keys und das LLM-Modell ein).*

### 2. Persönlichkeit & Verhalten (`core/Soul.md`)
In der Datei `core/Soul.md` ist der System-Prompt von Trinity hinterlegt. 
- **Standard-Verhalten:** Trinity ist instruiert, **extrem kurz (max. 1-2 Sätze)** zu antworten, um in der Vorlesung nicht den Faden zu stören.
- **Längere Antworten:** Wenn du möchtest, dass sie ausführlicher antwortet, fordere sie in deinem Sprachbefehl explizit dazu auf (z.B. *"Erkläre mir das ausführlich in mehreren Sätzen..."*). Sie wird sich dann über ihre Grundeinstellung hinwegsetzen.
- **Anpassung:** Du kannst die `Soul.md` jederzeit mit einem Texteditor öffnen und anpassen, wenn du ihren Tonfall (z.B. lockerer, formeller) ändern möchtest.

### 3. Eigenes Wissen / RAG (`RAG/`)
Trinity hat direkten Zugriff auf deine lokalen Dokumente (Vorlesungsdaten, Bücher).
- Wenn du Skripte, PDFs oder Notizen in das System eingespeist hast, kannst du sie danach fragen.
- **Trigger:** Verwende Schlagworte wie *"laut Skript"*, *"im Buch"*, *"schlag nach"*, *"Wissensbasis"*.
- **Beispiel:** *"Trinity, was steht im Skript zur Entscheidungsökonomik?"* Sie durchsucht dann automatisch den RAG-Index und antwortet fachlich korrekt auf Basis deiner eigenen Dokumente.

---

## 🧠 Die Agenten & Live-Skills

Trinity ist dank des neuen Skill-Systems kein Monolith mehr, sondern ein dynamischer Agent. Alle Skills liegen im Ordner `agents/` und werden beim Start automatisch geladen.

Hier sind die aktuellen Skills und wie du sie über **Sprachbefehle** auslöst:

### ⏱️ 1. Timer Agent (`timer_agent`)
Startet einen Countdown-Timer im Zusatzfenster.
- **Trigger:** *"Stell einen Timer auf 5 Minuten."* oder *"Timer 10 Minuten."*
- **Aktion:** Zeigt eine Live-Uhr an und gibt bei Ablauf ein optisches und (falls verbunden) akustisches Signal.

### 🗺️ 2. Maps Agent (`maps_agent`)
Zeigt dynamische, interaktive Google Maps Karten.
- **Trigger:** *"Zeig mir die Karte von Stuttgart"* oder *"Google Maps Berlin."*
- **Aktion:** Lädt eine Leaflet/Google Maps API-Ansicht im Overlay.

### 📊 3. Stock Agent (`stock_agent`)
Ruft Live-Aktienkurse ab und visualisiert den 5-Tage-Trend.
- **Trigger:** *"Wie steht der Aktienkurs von Apple?"* oder *"Preis von Nvidia."* oder *"Bitcoin Kurs."*
- **Aktion:** Zeigt den Live-Kurs inkl. SVG-Sparkline-Chart.

### 🔍 4. WebSearch Agent (`websearch_agent`)
Sucht in Echtzeit im Internet (via Tavily) nach aktuellen Fakten.
- **Trigger:** *"Recherchiere nach dem nächsten Spiel des VfB"* oder *"Suche online nach..."*
- **Aktion:** Liefert die Top 3 Ergebnisse ins Gedächtnis von Trinity und zeigt Links an.

### 🖼️ 5. Image Agent (`image_agent`)
Generiert minimalistische, auf Vorlesungen zugeschnittene Infografiken und Metapherbilder.
- **Trigger:** *"Generiere eine Infografik zur Raumzeit."* oder *"Erstelle ein Schaubild von..."*
- **Aktion:** Nutzt Fal.ai (Flux) und zeigt das generierte Bild formatfüllend an.

### 🎮 6. Simulation Agent (`simulation_agent`)
Lädt interaktive HTML5/JavaScript-Simulationen zur Visualisierung komplexer Themen.
- **Trigger:** *"Zeig Conway's Game of Life"*, *"Ameisen Simulation"*, *"Raumzeitkrümmung"*, *"Lass uns Pong spielen"*
- **Aktion:** Startet die Live-Simulation direkt im UI.

### 📋 7. Summary Agent (`summary_agent`)
Erstellt eine strukturierte Zusammenfassung der aktuellen Vorlesung.
- **Trigger:** *"Gib mir das Big Picture der Sitzung"* oder *"Zusammenfassung der Vorlesung."*
- **Aktion:** Analysiert das Transkript und zeigt strukturierte Bullet-Points an.

### 📊 8. PowerPoint Agent (`powerpoint_agent`)
Steuert Microsoft PowerPoint Präsentationen nativ über macOS AppleScript.
- **Trigger:** *"Präsentation starten"*, *"Nächste Folie"*, *"Zurück"*, *"Folie weiter"*, *"Präsentation beenden"*
- **Aktion:** Führt die Aktion im Hintergrund in PowerPoint aus.

### 🤫 9. Focus Agent (`focus_agent`)
Weist Trinity an, aktiv zuzuhören oder stumm im Hintergrund zu warten.
- **Trigger:** *"Bitte nicht zuhören"*, *"Hör weg"*, *"Fokus-Modus"* / Zurück: *"Weiter geht's"*, *"Hör wieder zu"*
- **Aktion:** Setzt das Kontextfenster um, sodass Trinity passiv agiert.

### 💬 10. Chat Mode Agent (`chat_mode_agent`)
Wechselt in den Natural Conversation Modus.
- **Trigger:** *"Lass uns quatschen"* oder *"Chat-Modus"*
- **Aktion:** Trinity verzichtet auf den "Lehrer-Ton" und antwortet kurz, knackig und gesprächig auf Zuruf.

### 🔁 11. Review Agent (`review_agent`)
Lädt das Summary der vergangenen Woche.
- **Trigger:** *"Zusammenfassung der letzten Vorlesung"* oder *"Letzte Sitzung"*
- **Aktion:** Liest das aggregierte Transkript/Summary der letzten Woche vor, um die Klasse wieder abzuholen.

### ⚙️ 12. Settings Agent (`settings_agent`)
Öffnet das Konfigurationsmenü auf Zuruf.
- **Trigger:** *"Öffne Einstellungen"* oder *"Konfiguration öffnen"*
- **Aktion:** Startet das UI für API-Keys und Modelle, ohne dass man das Terminal bemühen muss.

### ⌨️ 13. Codex Agent (`codex_agent`)
Übergibt komplexe Aufgaben an die lokal installierte Codex CLI.
- **Trigger:** Das Wort *„Codex“* muss ausdrücklich genannt werden.
- **Beispiel:** *„Trinity, nutze Codex im Projekt Automatismen und erstelle Entwürfe für meine aktuellen Mails.“*
- **Aktion:** Startet Codex im freigegebenen Projekt, nutzt dessen Regeln und Skills und gibt den Abschlussbericht direkt an Trinity beziehungsweise Telegram zurück.
- **Sicherheit:** Nur konfigurierte Projektordner; kein automatischer Versand, Push oder Deployment.

---

## 🛠️ Eigene Skills erstellen

Du möchtest Trinity etwas Neues beibringen? Ganz einfach:
1. Erstelle einen neuen Ordner: `agents/mein_neuer_skill/`
2. Erstelle eine `script.py` Datei mit folgendem Aufbau:
```python
def can_handle(query: str) -> bool:
    return "mein triggerwort" in query.lower()

def execute(query: str, context: dict = None) -> dict:
    # context["brain"] gibt dir vollen Zugriff auf das Kernsystem
    return {
        "has_payload": True, 
        "html_payload": "<h1>Hallo Welt</h1>",
        "search_context": "Ich habe die Aktion ausgeführt."
    }
```
3. Neustart von Trinity – der Skill wird **automatisch** geladen!
