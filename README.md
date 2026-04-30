# Trinity Assistant 🧞‍♀️

![Trinity Big Picture](assets/trinity_big_picture.jpg)

Trinity ist eine KI-gestützte Vorlesungsassistentin für macOS (Apple Silicon). Sie hört passiv zu, erkennt ihr Trigger-Wort, antwortet per Stimme und kann Infografiken, Webrecherchen, Timer, Karten und Simulationen direkt im UI anzeigen.

---

## 💡 Warum dieses Projekt? (Die Vision)

Als Dozent steht man oft vor der Herausforderung, den Fluss der Vorlesung beizubehalten und gleichzeitig spontane Informationen bereitzustellen. Trinity wurde entwickelt, um genau diese Lücke zu schließen:

![Trinity Vision](assets/trinity_vision.jpg)

*   **Der Assistent an deiner Seite:** Stell dir vor, du könntest mitten in einer Übung einfach sagen: *"Trinity, setze einen Timer für 10 Minuten"*, ohne dein Tablet oder Laptop zu berühren.
*   **Wissen on the fly:** Du möchtest einen neuen Blickwinkel auf eine Definition hören oder eine komplexe Metapher visualisieren? Trinity generiert (dank fal.ai) in Sekunden ein passendes **Schaubild oder Skizze**.
*   **Echtzeit-Daten:** *"Wie haben sich die Aktienkurse von Nvidia in den letzten 3 Wochen entwickelt?"* – Trinity recherchiert live (via Tavily) und blendet die Antwort sowie interaktive Charts direkt ein.
*   **Interaktive Lehre:** Ob YouTube-Videos, Google Maps Navigationsrouten oder interaktive Simulationen (wie das Game of Life) – Trinity bringt Dynamik in den Hörsaal.
*   **Korrektur & Synthese:** Du bemerkst einen Fehler im Skript oder möchtest am Ende der Stunde ein **Big Picture** der heutigen Inhalte? Trinity greift auf deine eigenen Dokumente (via lokalem RAG) zurück und fasst alles präzise zusammen.

Trinity ist mehr als ein Chatbot; sie ist das Interface zwischen deinem Wissen (RAG), dem World Wide Web und der visuellen Vermittlung im Hörsaal.

---

## Tech-Stack (Stand April 2026)

| Komponente | Technologie |
|---|---|
| **STT (Sprache → Text)** | `faster-whisper` · Modell: `small` · int8, CPU |
| **LLM** | Qwen3.6 35B A3B via LM Studio (lokal) oder OpenRouter (Fallback) |
| **TTS (Text → Stimme)** | macOS `say` (Stimme: Samantha) |
| **UI** | PySide6 / QWebEngineView mit Glasmorphismus |
| **RAG** | sentence-transformers `paraphrase-multilingual-MiniLM-L12-v2` |
| **Bildgenerierung** | fal.ai `nano-banana-2` |
| **Web-Recherche** | Tavily API |

---

## Projektstruktur

```
Trinity_Assistant/
├── trinity_launcher.py        ← System starten
├── trinity_app.py             ← UI (Avatar + Content-Fenster)
├── trinity-blueprint.md       ← Architektur-Konzept
├── README.md
├── core/
│   ├── brain.py               ← KI-Logik, Agentic Router, RAG, Tools
│   ├── transcriber.py         ← STT-Loop (faster-whisper, VAD, Trigger)
│   ├── Soul.md                ← Persona & Systemrolle von Trinity
│   ├── User.md                ← Kontext über den Nutzer (Mathias)
│   ├── config.json            ← Alle Einstellungen (LLM, STT, TTS, APIs)
│   ├── state.txt              ← IPC-Status (idle/listening/thinking/speaking)
│   └── payload.html           ← Aktives UI-Widget (wird zur Laufzeit befüllt)
├── RAG/                       ← PDF-Skripte hier ablegen → auto-indexiert
│   ├── index/                 ← Vorberechneter Embedding-Index
│   └── build_index.py         ← Index manuell neu bauen
├── gen_images/                ← Generierte Schaubilder (PNG)
└── memory/                    ← Sitzungs-Transkripte (Markdown)
```

---

## Installation & Start

### Voraussetzungen
- macOS mit Apple Silicon (M1–M4)
- Python 3.9
- Pakete installieren:

```bash
pip install faster-whisper sounddevice numpy requests PySide6 \
            sentence-transformers pyobjc-framework-Speech
```

### Starten
```bash
cd "/Users/matmax/Library/Mobile Documents/iCloud~md~obsidian/Documents/Ideaverse"
python3 projects/Trinity_Assistant/trinity_launcher.py
```

---

## Bedienung (Sprachbefehle)

| Befehl | Aktion |
|---|---|
| *„Trinity, [Frage]"* | Freie Konversation |
| *„Trinity, schlag im Skript nach …"* | RAG-Suche in den PDFs |
| *„Trinity, recherchiere …"* | Live Web-Suche via Tavily |
| *„Trinity, erstelle eine Infografik zu …"* | Bildgenerierung via fal.ai |
| *„Trinity, zeig mir eine Karte von …"* | Google Maps im UI |
| *„Trinity, starte einen Timer für X Minuten"* | Countdown im UI |
| *„Trinity, Big Picture"* | Sitzungs-Zusammenfassung |
| *„Trinity, hör kurz weg"* | Stummschalten |
| *„Trinity, hör wieder zu"* | Reaktivieren |

---

## Konfiguration (`core/config.json`)

```json
{
  "llm": {
    "use_local": true,
    "local_url": "http://192.168.10.33:1234/v1/chat/completions",
    "local_model": "qwen/qwen3.6-35b-a3b"
  },
  "stt": {
    "model": "small",
    "silence_threshold": 0.015,
    "chunk_duration": 6
  },
  "tts": { "voice": "Samantha" }
}
```

**STT-Modell wechseln** (Qualität vs. Speed):
- `tiny` → ~0.3s, schwächstes Deutsch
- `small` → ~0.8s, gut ✅ **(Standard)**
- `medium` → ~2s, besser für Akzente
- `large-v3-turbo` → ~8s, beste Qualität (zu langsam für Echtzeit)

---

## Latenz-Tuning

| Hebel | Einstellung | Effekt |
|---|---|---|
| `max_tokens` in brain.py | 250 (Standard) | Kürzer → schneller |
| `chunk_duration` in config.json | 6s | Kleiner = reaktiver, aber mehr False-Triggers |
| `silence_threshold` | 0.015 | Mikrofon-abhängig, ggf. anpassen |
| LLM `thinking` | aus | Kein /think-Modus bei Qwen3 |

---

## RAG – neue Wissensquellen hinzufügen

Einfach PDF in `RAG/` legen → beim nächsten Start wird der Index automatisch neu gebaut.

Manuell neu bauen:
```bash
python3 projects/Trinity_Assistant/RAG/build_index.py
```

---

*Entwickelt für Mathias · Trinity ist bereit.* 🧞‍♀️
