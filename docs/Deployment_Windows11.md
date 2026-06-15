# Trinity Deployment Guide für Windows 11

## Status

Die Windows-Version ist eine Entwicklungsvorschau. Der stabile macOS-Stand ist als
GitHub-Release `v0.9.2` gesichert und bleibt unverändert verfügbar.

## Unterstützt

- PySide6-Oberfläche und Chat-Modus
- Whisper-Spracherkennung über `faster-whisper`
- Windows-SAPI-Sprachausgabe
- auswählbare SAPI-Stimmen und Audioausgänge
- PowerPoint-Steuerung über das Microsoft COM Object Model
- RAG, WebSearch, Deep Research und Stock Agent
- Bildgenerierung über fal.ai und ComfyUI
- Pyodide Sandbox und JavaScript-Simulationen
- Notizen, Timer, Summary und Heartbeat
- Telegram-Bridge

## Noch nicht unterstützt

- Apple Native STT; diese Funktion bleibt macOS-exklusiv
- Mail-Automation im neuen Outlook
- abschließend getestetes Souffleur-Routing auf jeder Windows-Audiohardware
- signierter MSIX-/Inno-Setup-Installer

Für das neue Outlook ist Microsoft Graph vorgesehen. COM ist dort offiziell nicht
verfügbar und wird deshalb nicht als allgemeine Windows-Maillösung eingesetzt.

## Voraussetzungen

- Windows 11, 64 Bit
- Python 3.9 bis 3.12 mit funktionierendem SSL; empfohlen wird Python 3.11
- mindestens 8 GB RAM, empfohlen 16 GB oder mehr
- Mikrofonzugriff für Desktop-Apps
- optional Microsoft PowerPoint Desktop
- lokales LLM über LM Studio oder ein OpenRouter-Zugang

## Installation

PowerShell öffnen:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
irm https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/codex/windows11-platform/install_windows.ps1 | iex
```

Der Installer:

1. installiert nach `%LOCALAPPDATA%\Trinity`
2. prüft Python-Version und SSL-Unterstützung
3. installiert oder repariert bei Bedarf Python 3.11 über Windows Package Manager
4. sichert bei Updates Konfiguration, RAG, Memory und generierte Bilder
5. erstellt eine virtuelle Python-Umgebung
6. installiert gemeinsame und Windows-spezifische Abhängigkeiten
7. erstellt Verknüpfungen auf dem Desktop und im Startmenü

Wurde das Skript als Datei aus dem Browser heruntergeladen, kann Windows vor der
Ausführung warnen. Nach Prüfung der Quelle lässt sich die Markierung entfernen:

```powershell
Unblock-File .\install_windows.ps1
.\install_windows.ps1
```

## Manueller Start

```powershell
cd $env:LOCALAPPDATA\Trinity
.\venv\Scripts\python.exe .\trinity_launcher.py
```

## Mikrofon prüfen

Unter `Einstellungen > Datenschutz und Sicherheit > Mikrofon` müssen
Mikrofonzugriff und der Zugriff für Desktop-Apps aktiviert sein.

## PowerPoint

PowerPoint muss als Desktop-Anwendung installiert sein. Eine Präsentation muss geöffnet
sein, bevor Trinity die Diashow startet. Für `weiter`, `zurück` und `beenden` muss eine
Diashow laufen.

## Mail

Der Windows-Mail-Agent wird in dieser Vorschau deaktiviert und erklärt dies im Dialog.
Eine spätere Version verwendet Microsoft Graph mit delegierten Minimalberechtigungen.
Trinity wird weiterhin niemals automatisch eine Mail versenden.

## Fehlerdiagnose

Nur Python und SSL prüfen, ohne Trinity zu installieren:

```powershell
.\install_windows.ps1 -ValidateEnvironmentOnly -SkipPythonInstall
```

Falls keine geeignete Python-Installation gefunden wird, installiert der normale
Installer automatisch die offizielle Python-3.11-Version über `winget`. Auf zentral
verwalteten Rechnern kann dafür eine Freigabe der Administration erforderlich sein.

Für sichtbare Logs Trinity manuell aus PowerShell starten:

```powershell
cd $env:LOCALAPPDATA\Trinity
.\venv\Scripts\python.exe .\trinity_launcher.py
```

Der erste Start lädt das konfigurierte Whisper-Modell herunter. Das kann mehrere Minuten
dauern.
