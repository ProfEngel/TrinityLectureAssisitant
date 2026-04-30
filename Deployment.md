# Trinity Deployment Guide 🧞‍♀️

Diese Anleitung beschreibt die vollständige Installation von Trinity auf einem frischen macOS System (optimiert für Apple Silicon).

## 1. System-Voraussetzungen
- **Hardware:** Mac mit M1, M2, M3, M4 oder **M5 Chip** (Apple Silicon).
    - Getestetes System: **Mac M5 mit 32GB RAM**.
- **Betriebssystem:** macOS (getestet auf Sonoma/Sequoia).
- **Software:** Homebrew (für Audio-Treiber).

## 2. Grund-Installation

### Homebrew & PortAudio
Trinity benötigt `PortAudio` für die Mikrofon-Aufnahme:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install portaudio
```

### Python Setup
Trinity läuft am stabilsten mit **Python 3.9**.
```bash
# Prüfen ob Python installiert ist
python3 --version
```

### Repository & Abhängigkeiten
Klone das Projekt oder kopiere den Ordner und installiere die Python-Pakete:
```bash
pip install faster-whisper sounddevice numpy requests PySide6 \
            sentence-transformers pyobjc-framework-Speech \
            tavily-python
```

## 3. Die Komponenten-Konfiguration

### A. STT (Sprache-zu-Text)
Trinity nutzt `faster-whisper`.
- **Modell:** Das `small` Modell wird beim ersten Start automatisch nach `~/.cache/whisper` heruntergeladen (ca. 460 MB).
- **Treiber:** Nutzt die CPU (Apple Silicon Optimierung via CTranslate2).

### B. LLM (Das "Gehirn")
Trinity benötigt eine OpenAI-kompatible API.
1. **Lokal (Empfohlen):** Installiere **LM Studio**.
    - Lade ein Modell (z.B. **Qwen3.6 35B A3B in 4Bit Quantisierung**).
    - Starte den "Local Server" (Port 1234).
    - Stelle sicher, dass `use_local: true` in der `config.json` steht.
2. **Remote:** Trage einen API-Key für **OpenRouter** in die `config.json` ein.

### C. TTS (Stimme)
Es ist keine Installation nötig. Trinity nutzt den nativen macOS Befehl `say`.
- Die Stimme kann in den Systemeinstellungen -> Bedienungshilfen -> Gesprochene Inhalte angepasst werden (Standard: "Samantha").

### D. RAG (Wissensbasis)
Lege deine PDF-Skripte einfach in den Ordner `projects/Trinity_Assistant/RAG/`.
- Beim ersten Start baut Trinity automatisch den Vektor-Index.

## 4. Konfiguration & Personalisierung
Trinity benötigt einige Dateien für den Start, die in der GitHub-Version als `.example` vorliegen:

1.  **API-Keys:** Erstelle `core/config.json` aus der `core/config.json.example` und trage deine Keys ein.
2.  **Persona:** Erstelle `core/Soul.md` aus der `core/Soul.md.example` und passe Trinitys Persönlichkeit an.
3.  **Nutzerprofil:** Erstelle `core/User.md` aus der `core/User.md.example` und trage Informationen über dich und deine Zielgruppe ein.

### Beispiel config.json:
```json
{
  "llm": {
    "use_local": true,
    "local_url": "http://localhost:1234/v1",
    "local_model": "dein-modell-name"
  },
  "apis": {
    "tavily": "DEIN_TAVILY_KEY",
    "fal_ai": "DEIN_FAL_AI_KEY"
  }
}
```

## 5. Start
Wechsle in das Hauptverzeichnis deiner Ideaverse-Vault und starte den Launcher:
```bash
python3 projects/Trinity_Assistant/trinity_launcher.py
```

---
*Viel Erfolg bei der ersten Sitzung!* 🧞‍♀️
