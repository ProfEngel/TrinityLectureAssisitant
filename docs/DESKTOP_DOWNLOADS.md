# Trinity Desktop 0.19.1: Download und Ersteinrichtung

## Einfacher Start

1. Öffne die [Downloadseite](https://profengel.github.io/TrinityLectureAssisitant/).
2. Mac: DMG öffnen, **Trinity.app** nach Programme ziehen und starten.
   Windows: **Setup.exe** starten; alternativ das portable ZIP vollständig
   entpacken und **Trinity.exe** öffnen. Python/Git brauchst Du nicht vorher.
3. **Standalone** wählen. OpenAI-kompatible API-URL, Modellname und optional
   API-Key eintragen. `/v1` und `/v1/chat/completions` werden akzeptiert.
4. Der Assistent lädt Python, Bibliotheken, Parakeet und Qwen3 automatisch.
   Plane beim ersten Start Internet und mindestens 15 GB freien Speicher ein.
   Eve ist als freigegebene synthetische Referenzstimme im Download enthalten.
5. Nach abgeschlossenem Modell-Warmup startet Trinity. Mikrofon erlauben,
   dann „Trinity, erkläre den Unterschied zwischen Korrelation und Kausalität“.

Das Downloadpaket enthält den grafischen Starter, uv, den sauberen Trinity-Code
und Eve. Die großen Sprachmodelle und Laufzeitbibliotheken werden beim ersten
Start heruntergeladen, nicht im Git-Repository versioniert. Es ist deshalb
kein vollständig offline installierbares Paket. HF/PyPI/Python-Downloads benötigen
keinen LLM-Token; nur das gewählte LLM und optionale Medien-/Suchanbieter können
zusätzliche Zugangsdaten und Kosten benötigen.

## Hardware

- macOS: Apple Silicon, macOS 14 oder neuer; 16 GB RAM empfohlen. Intel-Macs
  können als Server-Client arbeiten, nicht mit der MLX-Standalone-Sprache.
- Windows: Windows 11 x64, NVIDIA-GPU mit aktuellem CUDA-12.8-kompatiblem
  Treiber; 8 GB VRAM und 16 GB RAM empfohlen. CUDA wird vor Sprachstart geprüft.
  Kein ungeprüfter Wechsel auf langsame CPU- oder fremde Systemstimmen.
- Das LLM wird nicht mitgeliefert. Lokal z. B. LM Studio/llama.cpp/Ollama mit
  OpenAI-kompatiblem Endpunkt oder eigener/extern gehosteter Modellserver.
  Bildschirm- und Folienfragen benötigen ein bildfähiges Modell am Endpunkt.
- Laufzeit, Latenz und verfügbare VRAM hängen vom LLM und der Hardware ab.
  Neue Windows-Installationen benötigen einen echten NVIDIA-Hardwaretest;
  GitHub-Buildrunner testen keine GPU-/Mikrofon-/Lautsprecherfunktion.

## Ein gemeinsamer Server statt Standalone

Wähle **Server-Client**, gib Trinity-Server-URL und Server-Token ein. Die
Realtime-URL kann separat eingestellt werden; sonst Port 8766 auf demselben
Host. Der Client lädt keine lokalen Parakeet/Qwen3-Modelle. Für TLS-Reverseproxy
oder andere Ports die vollständige WebSocket-URL angeben.

Der Linux-Server bleibt separat über [LINUX_UNIFIED_SERVER.md](LINUX_UNIFIED_SERVER.md)
installierbar. Server, Client und Standalone nutzen denselben öffentlichen
Quellstand. Die Windows-VM ist für einen Linux-Server nicht erforderlich.
Nicht ungeschützt ins Internet stellen; Authentifizierung und private
Netzwerke/TLS verwenden. Standalone ist standardmäßig nur an Loopback gebunden.

## Sicherheit, Updates und Rückfall

Die Starter sind derzeit **nicht mit einem öffentlichen Publisher-Zertifikat
signiert/notarisiert**. macOS kann eine Sicherheitswarnung zeigen; verwende
nach Prüfung des Downloads Systemeinstellungen → Datenschutz & Sicherheit →
Dennoch öffnen. Windows kann SmartScreen warnen. Keine Schutzfunktion pauschal
deaktivieren. SHA256-Dateien und zugehöriger Quellstand liegen im Release.

Benutzerdaten liegen unabhängig von Programme/Setup unter:

- Mac: `~/Library/Application Support/TrinityDesktop/`
- Windows: `%LOCALAPPDATA%\TrinityDesktop\`

Eine vorhandene Entwicklerinstallation wird **nicht** automatisch überschrieben
oder importiert. Starter-Updates behalten `core/config.json`, Stimme, Memory,
Dateien und Medien. Vor dem Update Trinity beenden. Die frühere App inkl.
Nutzerdaten liegt bei Versionswechsel unter `recovery/before-VERSION/`; die
Deinstallation des Windows-Starters löscht Benutzerdaten nicht. Die laufende
private Produktionsinstallation und der Server werden durch den öffentlichen
Build nicht verändert. Erst nach eigener Abnahme migrieren.

Die separate Mac-Ersteinrichtung wurde ohne vorinstalliertes Python/Git im
Starter-Pfad geprüft: Bibliotheken, Parakeet und Qwen3 heruntergeladen und
beide Modelle aufgewärmt; `voice doctor` ohne erforderliche Fehler.
Das ersetzt keinen Hör-/Mikrofontest oder einen Windows-GPU-Test.

Bei Einrichtungsfehlern zeigt der Assistent das Paket-/Hardwareproblem. Nach
Netzwerkfehlern erneut starten; Downloads werden über die Caches wiederverwendet.
Diagnosen: `logs/desktop.log` im Datenverzeichnis, Laufzeitlogs unter `app/logs/`.
Keine geheimen Konfigurationen oder vollständigen privaten Logs veröffentlichen.

## Abnahmetests für neue Downloads

1. Frisches Benutzerkonto ohne Python/Git: nur Download → drei LLM-Felder →
   Ersteinrichtung. Parakeet und Qwen3 müssen ohne zweite Konfiguration starten.
2. Zwei kurze Fragen und eine 60-Sekunden-Erklärung: alle Sätze hörbar, kein
   Stopp nach Silben und keine erneute Transkription der eigenen Stimme.
3. 10 Minuten Gespräch: danach „Fasse unsere drei wichtigsten Punkte zusammen“.
4. App schließen/öffnen: Verbindung und Memory erhalten, kein Modelldownload
   von vorne. Ausgewählten Client wechseln, unabhängigen Audioausgang testen.
5. Fensteranalyse nur nach ausdrücklicher Freigabe; zuerst TextEdit, Testtext,
   Diktat stoppen und Überarbeitung prüfen. Kein automatischer Mailversand.
6. Offline während Erstinstallation: klarer Fehler, erneuter Versuch möglich;
   nicht unterstützte Hardware: klarer Hinweis statt falschem Erfolgsstatus.

Die funktionierende private Linux/iPad-Konfiguration ist feldgetestet. Neue
öffentliche Bootstrapper sind eine neue Installationsstrecke, nicht der Beweis
eines vollständigen Tests auf jeder Hardwarekombination.
