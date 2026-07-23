# Trinity auf Windows 11

> **Historischer Portierungsplan:** Die Windows-Basisportierung ist umgesetzt.
> Aktuelle offene Arbeiten stehen ausschließlich in
> `docs/IMPLEMENTIERUNGSPLAN_TRINITY.md`.

## Umsetzungsstand

Die erste Portierungsstufe ist mit Release `v0.10.0` umgesetzt:

- Plattformadapter und Capability-Erkennung
- Windows SAPI für TTS
- PowerPoint COM unter Windows
- portable Temp-Dateien, Python-Unterprozesse und lokale Datei-URLs
- `pyproject.toml` mit macOS-/Windows-Abhängigkeiten
- `install_windows.ps1`
- Smoke-Tests auf macOS und Windows

Release `v0.10.1` ergänzt eine vom Kern getrennte Oberflächenwahl:

- Augen-UI für Vorlesung und Präsentation
- Classic-UI für den normalen Desktopbetrieb
- Terminal-CLI als erzwungener Fallback und Grundlage für Ubuntu/Headless

Noch offen sind Microsoft Graph für das neue Outlook, breite Windows-Hardwaretests,
vollständiges Packaging und die Trennung von Programm- und Nutzerdaten.

## Kurzfazit

Eine Windows-11-Version ist realistisch, ohne den bestehenden macOS-Funktionsumfang
einzuschränken. Der gemeinsame Python-, Qt-, Web-, RAG- und Agenten-Kern ist bereits
weitgehend plattformneutral. Portiert werden müssen hauptsächlich die Betriebssystem-
Schnittstellen:

- Installation und Packaging
- Text-to-Speech und Audio-Routing
- native Spracherkennung
- PowerPoint-Automation
- Mail-Automation
- plattformspezifische UI-Details

Die Portierung sollte nicht durch Windows-Abfragen im gesamten Code erfolgen. Empfohlen
wird eine kleine Plattformschicht mit getrennten macOS- und Windows-Adaptern. Die
vorhandenen macOS-Implementierungen bleiben dabei funktional unverändert und werden nur
hinter stabile Schnittstellen gelegt.

## Agenten-Matrix

| Komponente | Windows 11 | Aufwand | Anmerkung |
|---|---:|---:|---|
| Chat Mode Agent | Ja | gering | Reine Python-/LLM-Logik |
| ComfyUI Agent | Ja | gering | HTTP und lokale Dateien; Windows-Workflow ist bereits vorhanden |
| Deep Research Agent | Ja | gering | HTTP, BeautifulSoup und LLM |
| Focus Agent | Ja | gering | Benötigt nur die gemeinsame Audio-/TTS-Schnittstelle |
| Heartbeat Agent | Ja | gering | Reine Python-/LLM-Logik |
| Image Agent | Ja | gering | HTTP zu fal.ai und lokale Bildablage |
| Maps Agent | Ja | gering | HTML/Google Maps in Qt WebEngine |
| Notes Agent | Ja | gering | Markdown und lokale Dateien |
| RAG Agent | Ja | mittel | Abhängigkeiten und Python-Aufruf vereinheitlichen |
| Review Agent | Ja | gering | Plattformneutral, aktuell aber nur teilweise implementiert |
| Sandbox Agent | Ja | gering | Pyodide läuft in Qt WebEngine |
| Session Summarizer | Ja | gering | Dateipfade und Dateinamensschema korrigieren |
| Settings Agent | Ja | gering | PySide6 ist plattformübergreifend |
| Simulation Agent | Ja | gering | HTML/JavaScript/Canvas |
| Stock Agent | Ja | gering | HTTP und SVG |
| Summary Agent | Ja | gering | `sys.executable` und absolute Datenpfade verwenden |
| Timer Agent | Ja | gering | HTML/JavaScript |
| WebSearch Agent | Ja | gering | HTTP zu Tavily |
| PowerPoint Agent | Ja | mittel | Windows-Adapter über PowerPoint COM statt AppleScript |
| Mail Agent | Ja | hoch | Microsoft Graph für neues Outlook; COM nur als Fallback für klassisches Outlook |
| Whisper STT | Ja | mittel | `faster-whisper` und `sounddevice` sind Windows-fähig |
| Apple Native STT | Nein | keiner | Bleibt bewusst exklusiv für macOS |
| Souffleur Audio-Routing | Ja, mit Testbedarf | mittel bis hoch | Windows-Ausgabegeräte und TTS müssen separat angebunden werden |

## Aktuelle Blocker

### 1. TTS ist direkt an macOS gekoppelt

`core/transcriber.py` startet an vielen Stellen den macOS-Befehl `say`. Auch Stimmen-
und Geräteauswahl in `core/settings_ui.py` verwenden `say`.

Empfehlung:

- gemeinsame Schnittstelle `speak()`, `stop()`, `list_voices()` und
  `list_output_devices()` einführen
- macOS-Adapter behält `say` und das heutige Verhalten
- Windows-Adapter nutzt Windows SAPI
- Prozessabbruch beim Wake-Word muss auf beiden Plattformen unterstützt werden

### 2. PowerPoint und Mail verwenden AppleScript

Beide Agenten werden aktuell auf jeder Plattform geladen. Auf Windows würde der
PowerPoint-Agent den fehlenden `osascript`-Aufruf derzeit sogar als erfolgreiche Aktion
bestätigen.

Empfehlung:

- Agentenlogik von der Automation trennen
- macOS: vorhandene AppleScript-Implementierung
- Windows PowerPoint: Microsoft PowerPoint COM Object Model
- Windows Mail: Microsoft Graph als zukunftsfähiger Hauptweg
- klassisches Outlook COM nur als optionaler lokaler Fallback
- nicht verfügbare Fähigkeiten in UI und Router sichtbar deaktivieren

Das neue Outlook für Windows unterstützt keine COM-/VSTO-Automation. Ein reiner
COM-Agent würde daher nur mit dem klassischen Outlook funktionieren. Für eine
Windows-11-Version, die auch auf neuen Geräten Bestand hat, sollte der Mail-Agent
Microsoft Graph mit delegierten, möglichst kleinen Berechtigungen verwenden.

### 3. Installation ist ausschließlich macOS-spezifisch

`install_mac.sh` verwendet Bash, AppleScript, `sips`, `iconutil`, `.app` und `.icns`.
Diese Datei soll erhalten bleiben.

Für Windows wird separat benötigt:

- `install_windows.ps1`
- virtuelle Umgebung mit `venv\Scripts\python.exe`
- Startmenü-/Desktop-Verknüpfung
- `.ico`-Icon
- Mikrofon-Berechtigungsprüfung
- optional später signierter Installer

### 4. Abhängigkeiten sind nicht zentral definiert

Es gibt aktuell weder `pyproject.toml` noch vollständige Requirements-Dateien. Der
macOS-Installer enthält zudem nicht alle zur Laufzeit verwendeten Pakete.

Empfehlung:

- `pyproject.toml` als zentrale Quelle
- gemeinsame Abhängigkeiten für beide Plattformen
- macOS-Extra mit `pyobjc`
- Windows-Extra mit `pywin32`
- Versionen sperren und auf beiden Plattformen automatisiert testen

### 5. Programmdateien und Nutzerdaten sind vermischt

Konfiguration, RAG-Inhalte, Transkripte und generierte Medien liegen im
Installationsordner. Das ist bei Updates riskant und kollidiert auf Windows mit
geschützten Installationsverzeichnissen.

Empfehlung:

- Programmdateien getrennt von Nutzerdaten installieren
- macOS-Daten langfristig unter `~/Library/Application Support/Trinity`
- Windows-Daten unter `%LOCALAPPDATA%\Trinity`
- bestehende macOS-Daten beim ersten Start verlustfrei migrieren
- bis zur Migration den aktuellen macOS-Pfad als Legacy-Fallback erhalten

### 6. Kleinere portable Pfad- und Prozessprobleme

- `python3` muss in Unterprozessen durch `sys.executable` ersetzt werden
- `/tmp/tg_voice.oga` muss über `tempfile` erzeugt werden
- relative Pfade wie `memory/test.md` müssen von einem zentralen Projekt-/Datenpfad
  abgeleitet werden
- Session-Dateinamen `raw_session_*` und `Sitzung_*` sind derzeit nicht konsistent
- lokale Datei-URLs sollten mit `QUrl.fromLocalFile()` oder `Path.as_uri()` gebaut werden

## Empfohlene Zielstruktur

```text
Trinity_Assistant/
├── core/
│   ├── platform/
│   │   ├── protocols.py
│   │   ├── factory.py
│   │   ├── macos/
│   │   │   ├── tts.py
│   │   │   ├── speech.py
│   │   │   ├── powerpoint.py
│   │   │   └── mail.py
│   │   └── windows/
│   │       ├── tts.py
│   │       ├── speech.py
│   │       ├── powerpoint.py
│   │       └── mail.py
│   └── paths.py
├── installers/
│   ├── macos/
│   └── windows/
├── packaging/
│   ├── macos/
│   └── windows/
├── tests/
│   ├── common/
│   ├── macos/
│   └── windows/
├── pyproject.toml
├── install_mac.sh
└── install_windows.ps1
```

`install_mac.sh` kann aus Kompatibilitätsgründen am bisherigen Ort bleiben und intern
den macOS-Installer aufrufen. Windows-Dateien sollten nicht in die Agentenordner gelegt
werden, sondern gebündelt in `core/platform/windows`, `installers/windows` und
`packaging/windows`.

## Capability-System

Jeder systemnahe Agent sollte deklarieren, welche Fähigkeit er benötigt, zum Beispiel:

```python
REQUIRED_CAPABILITIES = {"powerpoint_automation"}
```

Beim Start ermittelt Trinity verfügbare Fähigkeiten:

```text
speech_input
speech_output
audio_device_routing
powerpoint_automation
mail_read
mail_draft
```

Der Router lädt oder aktiviert einen Agenten nur, wenn sein Adapter verfügbar ist. So
bleibt Trinity auf Windows funktionsfähig, auch wenn Outlook oder PowerPoint nicht
installiert sind, und macOS verliert keine vorhandene Funktion.

## Packaging-Empfehlung

Für die erste Windows-Version:

1. PowerShell-Installer für Entwickler und Tester
2. anschließend PyInstaller im `onedir`-Modus
3. danach ein signierter Inno-Setup- oder MSIX-Installer

`onedir` ist für Trinity zunächst geeigneter als `onefile`, weil PySide6 WebEngine,
HTML-Assets, Agenten, Workflows und ML-Bibliotheken viele zusätzliche Dateien benötigen.
Windows-Builds müssen auf Windows erzeugt und getestet werden; macOS-Builds weiterhin
auf macOS.

## Empfohlene Reihenfolge

### Phase 1: Portabler Kern

- zentrale Pfadverwaltung
- zentrale Abhängigkeiten
- `sys.executable` und `tempfile`
- Plattform- und Capability-Erkennung
- macOS-Smoke-Tests als Regressionsschutz

### Phase 2: Windows-Basisversion

- Windows-PowerShell-Installer
- PySide6-UI unter Windows testen
- Whisper-Mikrofonpfad
- Windows-SAPI-TTS
- Chat, RAG, Web, Bilder, Simulation, Sandbox und Notizen

### Phase 3: Native Windows-Agenten

- PowerPoint über COM
- Mail über Microsoft Graph, ohne automatisches Senden
- optionaler COM-Fallback für klassisches Outlook
- Audio-Geräteauswahl und Souffleur-Routing

### Phase 4: Distribution

- PyInstaller-`onedir`
- Installer, Signierung und Update-Strategie
- CI-Matrix für macOS und Windows
- reale Tests mit Mikrofon, mehreren Ausgabegeräten, PowerPoint und Outlook

## Abnahmekriterien

- aktueller macOS-Launcher und `install_mac.sh` funktionieren unverändert weiter
- macOS Native STT bleibt verfügbar
- Windows startet ohne installierte Apple-Bibliotheken
- nicht verfügbare Agenten melden klar den Grund und behaupten keinen Erfolg
- Windows Whisper STT, TTS-Unterbrechung und UI funktionieren gemeinsam
- PowerPoint-Steuerung funktioniert in laufender Windows-Diashow
- Mail-Agent erstellt nur sichtbare Entwürfe und sendet nie automatisch
- Nutzerdaten bleiben bei Updates auf beiden Plattformen erhalten
- automatisierte Smoke-Tests laufen auf macOS und Windows

## Technische Referenzen

- Qt for Python: https://doc.qt.io/qtforpython-6/
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- sounddevice Installation: https://python-sounddevice.readthedocs.io/en/0.5.0/installation.html
- PowerPoint SlideShowView: https://learn.microsoft.com/en-us/office/vba/api/powerpoint.slideshowview
- Windows SAPI SpVoice: https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms720149(v=vs.85)
- Neues Outlook und COM: https://learn.microsoft.com/en-us/office/dev/add-ins/outlook/outlook-add-ins-overview
- Microsoft Graph Berechtigungen: https://learn.microsoft.com/en-us/graph/permissions-overview
- PyInstaller: https://pyinstaller.org/en/stable/operating-mode.html
