# Trinity — Academic Personal Concierge 🧞‍♀️
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20286707.svg)](https://doi.org/10.5281/zenodo.20286707)


![GitHub stars](https://img.shields.io/github/stars/ProfEngel/TrinityLectureAssisitant?style=social)
![GitHub forks](https://img.shields.io/github/forks/ProfEngel/TrinityLectureAssisitant?style=social)
![GitHub watchers](https://img.shields.io/github/watchers/ProfEngel/TrinityLectureAssisitant?style=social)
![GitHub repo size](https://img.shields.io/github/repo-size/ProfEngel/TrinityLectureAssisitant)
![GitHub language count](https://img.shields.io/github/languages/count/ProfEngel/TrinityLectureAssisitant)
![GitHub top language](https://img.shields.io/github/languages/top/ProfEngel/TrinityLectureAssisitant)
![GitHub last commit](https://img.shields.io/github/last-commit/ProfEngel/TrinityLectureAssisitant?color=red)
[![Sponsor](https://img.shields.io/static/v1?label=Sponsor&message=%E2%9D%A4&logo=GitHub&color=ff69b4)](https://github.com/sponsors/ProfEngel)
[![YouTube](https://img.shields.io/badge/YouTube-MatMaxEngel-red?logo=youtube&logoColor=white)](https://www.youtube.com/user/MatMaxEngel)

![Trinity Assistant Banner](assets/banner.png)
> [!NOTE]
> **Aktuelles Release:** 
> - **v0.10.0:** Gemeinsames Release für macOS und Windows 11 mit lokalem Codex-Agenten.
> - **v0.9.2:** Weiterhin verfügbarer macOS-Basisstand vor der Windows-Portierung.

### Nicht Chatbot. Nicht Copilot. Ein Academic Personal Concierge.

Trinity ist ein persönliches KI-Privatbüro für Professorinnen und Professoren: Ein **Academic Personal Concierge** für Vorlesungen, Recherche, Dokumente, Kommunikation und komplexe Wissensarbeit. Sie läuft lokal auf macOS und Windows 11. Trinity ist DSGVO-konform konzipiert und modellagnostisch.

---

![Trinity Academic Personal Concierge](assets/infografik_quer.png)

## 💡 Warum dieses Projekt? (Die Vision)

Als Dozent steht man oft vor der Herausforderung, den Fluss der Vorlesung beizubehalten und gleichzeitig spontane Informationen bereitzustellen oder im Büro die Flut an Dokumenten und Mails zu bewältigen. Trinity wurde entwickelt, um genau diese Lücke zu schließen:

![Trinity Vision](assets/trinity_vision.jpg)

*   **Dein persönliches Privatbüro:** Trinity unterstützt dich aktiv bei der Vorlesungsvorbereitung, Recherche und dem Dokumentenmanagement.
*   **Wissen on the fly:** Du möchtest einen neuen Blickwinkel auf eine Definition hören oder eine komplexe Metapher visualisieren? Trinity generiert (dank fal.ai oder lokal via ComfyUI) in Sekunden ein passendes **Schaubild oder Skizze**.
*   **Heartbeat-Souffleur (Audio-Routing):** Trinity fungiert als dein privater Souffleur auf dem AirPods. Hörst du eine Erklärung, die das Plenum (die Klasse) hören sollte, reicht ein *"Trinity, wiederhole das für alle"*, und sie wechselt automatisch die Audioausgabe auf die externen Lautsprecher.
*   **Proaktiver Begleiter (Telegram-DM):** Trinity analysiert deine Vorlesung live im Hintergrund. Fällt ihr ein logischer Fehler auf, zeigt sie im UI eine rote "Bubble". Arbeitest du im Vollbildmodus am Beamer? Kein Problem, die Telegram-Bridge sendet dir Trinitys Anmerkungen lautlos als Direktnachricht aufs Smartphone.
*   **Deep Memory (RAG Automation):** Am Ende einer Vorlesung generiert Trinity ein Summary. Damit das Wissen nicht verloren geht, fügt sie diese Zusammenfassungen ab sofort automatisch in ihr Langzeitgedächtnis (RAG-Index) ein. So weiß sie nächste Woche noch genau, worüber gesprochen wurde.
*   **Natürliche Interaktion:** Trinity hört aktiv zu und erkennt ihr Wake-Word egal ob am Anfang (*"Trinity, was ist..."*) oder am Ende (*"... findest du nicht auch, Trinity?"*) des Satzes. Sie nutzt den vollen Kontext davor und danach.
*   **Duale Modi (Lecture, Office & Chat Mode):** Trinity passt ihr Verhalten dem Kontext an. Im **Lecture Mode** agiert sie als rhetorische Unterstützung, im **Office Mode** als produktiver Begleiter, und im ressourcenschonenden **Chat Mode** kommuniziert sie rein über Text/UI ohne aktive Mikrofone. Du kannst jederzeit nahtlos zwischen den Modi wechseln.
*   **Fenster-Management:** Alle Fenster sind frei verschiebbar – ideal für Multi-Monitor-Setups.

Trinity ist mehr als ein Chatbot; sie ist das Interface zwischen deinem Wissen (RAG), dem World Wide Web und der visuellen Vermittlung im Hörsaal.

---

## 🚀 Das Agenten-System (Lecturer Companion)
 
 Trinity (geplant als *Lecturer Companion*) ist vollständig in **unabhängige Agent-Skills** unterteilt:
 
 | Agent | Modus | Kernfunktion |
 |---|---|---|
 | **Office Mode** | *Office* | **NEU:** Fokus auf Mail-Drafts, Kalender & produktiven Support. |
 | **Lecture Mode** | *Lecture* | Fokus auf Plenum-Interaktion, Souffleur-Routing & Visuals. |
 | **RAG-Agent** | *Beide* | Suche in Vorlesungs-PDFs, Mails & Session-Summaries. |
 | **WebSearch-Agent** | *Beide* | Echtzeit-Websuche via Tavily. |
 | **Image-Agent** | *Lecture* | Bildgenerierung (Infografiken/Skizzen) via fal.ai. |
 | **Simulation-Agent** | *Lecture* | Interaktive Simulationen (Bienen, Sortierung, NNs). |
 | **PowerPoint-Agent** | *Lecture* | Native Steuerung via AppleScript (macOS) oder COM (Windows). |
 | **ComfyUI-Agent** | *Beide* | Lokale Generierung von Bildern, Musik & Videos. |
 | **Summary-Agent** | *Beide* | Automatische Zusammenfassung & RAG-Indexierung. |
 | **Sandbox-Agent** | *Beide* | **NEU:** Sichere Python/WASM-Sandbox für Berechnungen & Data Science (Plotly). |
 | **Deep-Research-Agent** | *Beide* | **NEU:** Agentische, mehrstufige Tiefenrecherche mit lokaler Websuche (DDG) & Scraping. |
 | **Codex-Agent** | *Office/Chat* | Übergibt ausdrücklich adressierte Aufgaben an lokale Codex-Projekte samt Skills und Subagenten. |
 | **Document Intelligence**| *Office* | **NEU:** Drag & Drop von Seminararbeiten/Thesen zur Begutachtung. |
 
 ---
 
 ## ✨ Highlights & Besonderheiten
 
 *   **AirPod Souffleur:** Private Informationen direkt ins Ohr, Umschalten auf Plenum-Speaker auf Befehl.
 *   **Proaktiver Heartbeat:** Analyse des Transkripts alle 2 Min. mit Warnungen vor logischen Fehlern.
 *   **Document Intelligence:** Lokale Dateien (Thesen, Excel) einfach auf das UI "plumpsen" lassen zur Sofort-Analyse.
 *   **Secure Sandbox Environment:** 100% einbruchsichere Python/WASM-Umgebung (Pyodide) für wissenschaftliche Berechnungen, sympy-Algebra und interaktive Plotly-Diagramme.
 *   **Dynamic Progress Ring:** Kreisförmige Fortschrittsanzeige (Orange: Reading, Rot: Analyzing) um den Avatar.
 *   **User Telemetry:** Tracking der Zeit in Vorlesungen, Teams-Sitzungen und Mail-Bearbeitung (analog Bildschirmzeit).
 *   **Local First & DSGVO:** Maximale Privatsphäre durch lokale Verarbeitung und gezieltes STT-Mikrofon.

---

## Tech-Stack (Stand Juni 2026)

| Komponente | Technologie |
|---|---|
| **STT (Sprache → Text)** | `faster-whisper` · Modell: `small` · int8, CPU |
| **LLM** | Gemma 4 26B A4B oder Qwen3.6 35B A3B via LM Studio (lokal) oder OpenRouter (Fallback) |
| **TTS (Text → Stimme)** | macOS `say` oder Windows SAPI |
| **UI** | PySide6 / QWebEngineView mit Glasmorphismus |
| **RAG** | sentence-transformers `paraphrase-multilingual-MiniLM-L12-v2` |
| **Bildgenerierung** | fal.ai `nano-banana-2` (Cloud) oder ComfyUI `Flux.1/2` (Lokal) |
| **Musikgenerierung** | ComfyUI `AceStep 1.5` (Lokal) |
| **Videogenerierung** | ComfyUI `LTX 2.3` (Lokal) |
| **Python Sandbox** | Pyodide WebAssembly (lokal in QWebEngineView) |
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

## 🚀 Onboarding & Installation

Du brauchst ein KI-Sprachmodell via OpenRouter oder lokal via LM Studio/Ollama sowie optionale API-Keys für Web-Suche (Tavily) und Bildgenerierung (fal.ai).

### macOS

Der stabile macOS-Funktionsumfang bleibt vollständig erhalten.

Öffne das Terminal und führe diesen Befehl aus:

```bash
curl -sSL https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/install_mac.sh | bash
```

### Windows 11

Die Windows-Version verwendet optional Whisper für STT, Windows SAPI für TTS und COM
für die PowerPoint-Steuerung. Apple Native STT bleibt macOS-exklusiv. Der Mail-Agent
folgt später über Microsoft Graph, weil das neue Outlook keine COM-Automation
unterstützt.

PowerShell öffnen und ausführen:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
irm https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/install_windows.ps1 | iex
```

Der normale Windows-Start öffnet wie auf macOS ein sichtbares Terminal. Dort erscheinen
Trinitys Mitschrift, Agentenaktivität und Fehlerdiagnose. Zusätzlich installiert Trinity
eine Verknüpfung **„Trinity ohne Terminal“** für einen stillen Start.

Die vollständige Anleitung und Funktionsmatrix stehen in
[Deployment Windows 11](docs/Deployment_Windows11.md) und im
[Windows-Portierungsplan](docs/WINDOWS11_PORTING_PLAN.md).

Detaillierte Anweisungen zu den API-Keys und der Konfiguration findest du im [Wiki](https://github.com/ProfEngel/TrinityLectureAssisitant/wiki).

### Codex als lokaler Ausführungsagent

Trinity kann Aufgaben per Sprache, Chat oder Telegram an eine lokal installierte und
angemeldete Codex CLI übergeben. Codex arbeitet dabei ausschließlich in Projektordnern,
die zuvor unter **Einstellungen → Codex** freigegeben wurden.

Beispiel:

> „Trinity, nutze Codex im Projekt Automatismen. Prüfe meine aktuellen Mails und
> erstelle passende Antwortentwürfe.“

Codex verwendet die Regeln und Skills des ausgewählten Projekts. Subagenten werden
verwendet, wenn der Auftrag oder die Projektanweisungen sie ausdrücklich vorsehen.
Fernausgelöste Läufe dürfen Entwürfe und lokale Dateien erstellen, aber nichts
versenden, veröffentlichen, pushen oder deployen.

Die technische Grundlage ist Codex'
[nicht-interaktiver Modus](https://developers.openai.com/codex/noninteractive)
mit einer auf das Projekt begrenzten Sandbox. Hinweise zur Ablage eigener Workflows
stehen in der offiziellen Dokumentation zu
[Codex Skills](https://developers.openai.com/codex/skills).

---

## 🔒 Datenschutz & DSGVO-Konformität

Trinity ist vollständig **DSGVO-konform** im Hörsaal-Einsatz konzipiert. Da die Spracheingabe **exklusiv über ein einzelnes Apple AirPod** erfolgt, ist der Aufnahmeradius des Mikrofons auf ca. 20 cm um den Dozenten beschränkt. **Es werden keine Stimmen der Studierenden aufgezeichnet.**

---

#### 🗺️ Roadmap: Der Weg zu v1.0
 
 *   **Trinity Mobile (v0.8.0):** Companion-App für Single-Monitor-Setups, Tablet-Support und mobile Session-Synchronisation.
 *   **Office Mode Integration (Q2 2026):** Lokale Mail-Drafts, AppleScript-Anbindung für Teams/Kalender & Writing Sample RAG.
 *   **Document Intelligence (Q2 2026):** Drag & Drop Support für Thesen und Excel-Auswertungen inkl. Korrektur-Agenten.
 *   **User Telemetry (Q3 2026):** Nutzungsstatistiken für Lehre und Büro (analog Bildschirmzeit).
 *   **Cognitive Evolution & Dreaming (Q3 2026):** "Dreaming-Funktion" zur Hintergrund-Reflektion (Sessions verarbeiten zu komplexem Verständniswissen, Tagging, Graphen-Verlinkung, Relevanz-Gewichtung und Priorisierung) sowie Fallback-LLM Resilienz.
 *   **Erstbenutzer Onboarding (Q3 2026):** Interaktives Einführungstutorial für neue User.
 *   **Multi-OS & Cross-Platform Packaging:** macOS und Windows 11 werden unterstützt; als Nächstes folgen signierte Pakete sowie später iOS, Android und Headless Ubuntu.
 *   **Multi-Domain Expansion (Q4 2026):** Erweiterung des Concierges für Jeden (z.B. Ernährungsverläufe, Fitness, SmartHome – Kerndienste bereits erstellt).

Details zu den aktuellen Entwicklungsaufgaben findest du in der [ToDo.md](ToDo.md).

---

## Lizenz 📜

Dieses Projekt steht unter der **Apache License 2.0**.

---

## Zitation & Forschung 📚

Für das Projekt stehen wissenschaftliche Begleitpapiere (Whitepapers) bereit, die die architektonische Einzigartigkeit und Notwendigkeit des Trinity-Ansatzes im Detail analysieren:

*   **[Whitepaper (Deutsch)](docs/trinity_20052026_de.pdf)** — *TRINITY: Ein lokaler, agentischer Academic Personal Concierge für die KI-gestützte Hochschullehre und das akademische Dokumentenmanagement*
*   **[Whitepaper (English)](docs/trinity_20052026_en.pdf)** — *TRINITY: A Local Agentic Academic Personal Concierge for AI-Assisted Higher Education and Academic Document Management*

Wenn du Trinity in deiner Forschung verwendest, zitiere bitte wie folgt:

```bibtex
@software{trinity2026,
  title={Trinity: Academic Personal Concierge for macOS with modular Agentic-Skill-System},
  author={Engel, Mathias and Engel, Zoe},
  year={2026},
  note={Ein privates Forschungsprojekt von Mathias Engel, Zoe Engel und Eve},
  url={https://github.com/ProfEngel/TrinityLectureAssisitant}
}
```

---

_Made with ❤️ in Stuttgart / Nürtingen, Germany by Mathias Engel & Zoe Engel (2024–2025)_
_Trinity ist bereit._ 🧞‍♀️

---

## Über das Projekt

KI-gestützte Vorlesungsassistentin mit passiver Spracherkennung, modularem Agentic-Skill-System und lokaler RAG-Wissensbasis. Ein privates Forschungsprojekt mit und für Eve. 🧞‍♀️

---

## 💖 Sponsorship & Support

Trinity ist ein kostenloses Open-Source-Forschungsprojekt. Dennoch hat der Aufbau dieses **Academic Personal Concierge** bereits unzählige Stunden und erhebliche private Mittel (Hardware, Token, APIs) verschlungen. Wenn Trinity dir im Hörsaal oder Büro einen echten Mehrwert bietet (und z. B. teure Consulting-Optionen im Wert von 5.000 € – 10.000 € ersetzt), freuen wir uns über deine Unterstützung!

Deine freiwilligen Beiträge helfen uns, die Entwicklung voranzutreiben und Trinity noch intelligenter zu machen.

🎯 **Community Support**  
Perfekt für alle, die unsere Mission unterstützen möchten:

*   **☕ Kaffee für ProfEngel ($5):** Treibstoff für lange Coding-Nächte!
*   **💻 Token-Sponsor ($30):** Hilf uns, die API-Kosten für Cloud-Modelle (OpenRouter, fal.ai) und Tests zu decken.
*   **🚀 GPU Hour Sponsor ($110+):** Unterstütze uns beim Testen komplexer lokaler Modelle (LTX, Flux) auf Hochleistungssystemen.

**[👉 Jetzt Sponsor werden](https://github.com/sponsors/ProfEngel)**

---

## 🤝 Support & Beiträge

Beiträge sind herzlich willkommen! Wenn du Ideen, Verbesserungen oder Fehlerberichte hast, öffne gerne ein **Issue** oder einen **Pull Request**.

- 🐛 **Issues**: [GitHub Issues](https://github.com/ProfEngel/TrinityLectureAssisitant/issues)
- 💬 **Diskussionen**: [GitHub Discussions](https://github.com/ProfEngel/TrinityLectureAssisitant/discussions)
- 🎓 **Forschung**: `mat.max.engel [at] gmail.com`

## Star History

<a href="https://star-history.com/#ProfEngel/TrinityLectureAssisitant&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=ProfEngel/TrinityLectureAssisitant&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=ProfEngel/TrinityLectureAssisitant&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=ProfEngel/TrinityLectureAssisitant&type=Date" />
  </picture>
</a>
