# Trinity Deployment Guide für Windows 11

## Status

Windows 11 wird ab Release `v0.10.0` unterstützt. Der frühere macOS-Basisstand ist
zusätzlich als GitHub-Release `v0.9.2` gesichert und bleibt verfügbar.

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
- optionaler Codex-Agent, wenn die Codex CLI auf dem Windows-Host installiert und
  angemeldet ist
- wählbare Augen-UI, Classic-Desktopoberfläche und Terminal-CLI

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
irm https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/install_windows.ps1 | iex
```

Der Installer:

1. installiert nach `%LOCALAPPDATA%\Trinity`
2. prüft Python-Version und SSL-Unterstützung
3. installiert oder repariert bei Bedarf Python 3.11 über Windows Package Manager
4. sichert bei Updates Konfiguration, RAG, Memory und generierte Bilder
5. erstellt eine virtuelle Python-Umgebung
6. installiert gemeinsame und Windows-spezifische Abhängigkeiten
7. erstellt Verknüpfungen auf dem Desktop und im Startmenü
8. erstellt einen normalen Start, der die gewählten Oberflächen berücksichtigt
9. installiert den globalen Befehl `trinity` im Benutzer-PATH

Wurde das Skript als Datei aus dem Browser heruntergeladen, kann Windows vor der
Ausführung warnen. Nach Prüfung der Quelle lässt sich die Markierung entfernen:

```powershell
Unblock-File .\install_windows.ps1
.\install_windows.ps1
```

## Manueller Start

Nach der Installation eine neue PowerShell öffnen:

```powershell
trinity start
```

Die bisherige direkte Startmöglichkeit bleibt verfügbar:

```powershell
cd $env:LOCALAPPDATA\Trinity
.\venv\Scripts\python.exe .\trinity_launcher.py
```

Der normale Desktop- und Startmenüeintrag verwendet die unter
`Einstellungen > System > Bedienoberflächen` gewählte Kombination. Die Desktop-
Verknüpfung `Trinity ohne Terminal` unterdrückt die Konsole, sofern Augen- oder
Classic-UI aktiv sind; Protokolle werden weiterhin in `logs` abgelegt.

## Bedienoberflächen

- `Augen-UI`: schwebende Trinity für den Vorlesungsbetrieb
- `Classic-UI`: normale App mit Live-Mitschrift, dauerhaftem Chatverlauf,
  Text-/PDF-/Bildanlagen und eingebetteten Medienergebnissen. Das Zahnrad öffnet die
  Einstellungen im selben Fenster; oben und unten führt ein Button zurück zum Chat.
- `Terminal-CLI`: Mitschrift, Logs und Texteingabe im Terminal

Mehrere Oberflächen können gleichzeitig laufen. Sind Augen- und Classic-UI beide
deaktiviert, erzwingt Trinity die Terminal-CLI. So kann Trinity auch ohne grafische
Desktopumgebung bedient werden.

## CLI, Onboarding und Doctor

```powershell
trinity settings
trinity onboarding
trinity doctor
trinity doctor --fix
```

`trinity settings` bearbeitet die wichtigsten Einstellungen interaktiv im Terminal.
`trinity onboarding` führt durch die Ersteinrichtung. `trinity doctor` prüft unter
anderem Python, SSL, Konfiguration, Oberflächen, LLM und Schreibrechte. `--fix` legt
fehlende Standarddateien und Laufzeitordner an und aktiviert nötigenfalls den
Terminal-Fallback.

## Schwebendes Trinity-Fenster

- Linksklick auf Trinity öffnet das Flüsterfeld.
- Eingabe mit `Enter` absenden.
- Rechtsklick auf Trinity öffnet die Einstellungen direkt.
- Ziehen mit gedrückter linker Maustaste verschiebt Trinity.

## Stabiler Ersttest

1. In den Einstellungen unter `System` zunächst den Modus `chat` wählen.
2. `Experimentelle Windows-Spracheingabe` deaktiviert lassen.
3. Unter `LLM` den gewünschten Provider aktivieren und `Aktives LLM testen` wählen.
4. Trinity neu starten und die erste Frage über das Flüsterfeld stellen.

Whisper und der Mikrofoneingang werden unter Windows erst geladen, wenn die
experimentelle Spracheingabe ausdrücklich aktiviert wurde. Ein Audiofehler beendet
dadurch nicht mehr den Text- und LLM-Betrieb.

## Mikrofon prüfen

Unter `Einstellungen > Datenschutz und Sicherheit > Mikrofon` müssen
Mikrofonzugriff und der Zugriff für Desktop-Apps aktiviert sein.

## PowerPoint

PowerPoint muss als Desktop-Anwendung installiert sein. Eine Präsentation muss geöffnet
sein, bevor Trinity die Diashow startet. Für `weiter`, `zurück` und `beenden` muss eine
Diashow laufen.

## Mail

Der Windows-Mail-Agent ist derzeit deaktiviert und erklärt dies im Dialog.
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

Trinity schreibt dauerhaft Diagnoseprotokolle nach:

```text
%LOCALAPPDATA%\Trinity\logs
```

Ob eine Konsole sichtbar ist, bestimmt die Option `Terminal-CLI` in den Einstellungen.

Für sichtbare Logs Trinity manuell aus PowerShell starten:

```powershell
cd $env:LOCALAPPDATA\Trinity
.\venv\Scripts\python.exe .\trinity_launcher.py
```

Wenn die experimentelle Windows-Spracheingabe aktiviert wird, lädt der erste Sprachstart
das konfigurierte Whisper-Modell herunter. Das kann mehrere Minuten dauern.

## Codex-Agent

Voraussetzung ist eine installierte und angemeldete Codex CLI. Danach unter
`Einstellungen > Harnesses > Codex`:

1. Codex-Aufträge aktivieren.
2. Freigegebene Projekte als `Name = vollständiger Ordnerpfad` eintragen.
3. Optional ein Standardprojekt festlegen.
4. Für den Einstieg `workspace-write`, Netzwerk aus und ephemere Läufe verwenden.

Unter `Einstellungen > Harnesses` legt die Agentenmatrix fest, welche
Trinity-Agenten Codex ausfuehren darf. Unter `Einstellungen > Agenten` werden
Reifegrad, Rechte, Freigaben, erlaubte Pfade und Laufgrenzen gepflegt.

Der Trigger muss ausdrücklich genannt werden, beispielsweise:

> Trinity, nutze Codex im Projekt Lehre und prüfe die aktuellen Änderungen.
