# Trinity auf Linux / Ubuntu Server

Die Linux-Variante ist ein Headless-Server: Trinity-Kern, HTTP-Bridge und Browser-WebUI laufen ohne PySide, Augen-UI oder lokales Mikrofon. Sprach- und Dateiinteraktion erfolgen im Browser, per iPhone/iPad-Companion oder Telegram.

## Installation

```bash
curl -sSL https://raw.githubusercontent.com/ProfEngel/TrinityLectureAssisitant/main/install_linux.sh | bash
~/.local/bin/trinity onboarding
```

Der Installer legt Trinity in `~/Trinity_Assistant`, eine virtuelle Umgebung und den Befehl `~/.local/bin/trinity` an. Fuer eine dauerhaft gesetzte PATH-Variable kann `~/.local/bin` in die Shell-Konfiguration aufgenommen werden.

## Server starten

```bash
trinity server --host 127.0.0.1 --port 8765
```

Die WebUI ist dann unter `http://127.0.0.1:8765/` erreichbar. Der Kern verarbeitet Browserauftraege ueber die gleiche lokale Queue wie Classic-UI, TUI und Companion Bridge. Lokales STT wird im Servermodus absichtlich nicht geladen.

## Tailscale und Accounts

Fuer private Fernnutzung:

```bash
trinity server --host 0.0.0.0 --port 8765 --auth
```

Dann im Tailnet `http://TAILSCALE-IP:8765/` oeffnen und beim ersten Zugriff den
Admin-Account anlegen. Der Admin kann weitere Accounts anlegen; Anmeldung ist
über die WebUI oder den Desktop-Client möglich. Ohne Tailscale sollte der Server
nicht offen ins Internet gestellt werden.

## Funktionen

- Chat und Dateiupload fuer Text, PDF, Bild, `.xlsx` und `.xlsm`
- eingebettete Bilder, Audio, Video, Sandbox- und HTML-Ergebnisse
- pro Account getrennte Chatverläufe, Uploads und Memory-Datenbanken unter `memory/users/`
- dieselben Agenten und die Companion-Bridge wie auf Desktop-Systemen
- Logs unter `logs/server-runtime.log` und `logs/server-web.log`

Die Linux-Variante ersetzt keine macOS- oder Windows-Oberflaeche. Sie ist ein zusaetzlicher, stabiler Serverpfad fuer Browser, SSH und mobile Clients.

## Desktop als Client verbinden

Auf macOS oder Windows in der gewünschten Trinity-Installation:

```bash
trinity client login --url http://TAILSCALE-IP:8765
trinity start --surface classic
```

`trinity client status` prüft die Verbindung. `trinity client logout` entfernt
den lokalen Sitzungstoken und aktiviert wieder den vollständigen lokalen Betrieb.
Ein angemeldeter Admin kann weitere Konten mit
`trinity client add-user --url http://TAILSCALE-IP:8765 --username NAME` anlegen.
