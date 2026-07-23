# T1 – Canvas-Abnahme auf Mac, Windows und Companion

Stand: 23. Juli 2026

Dieses Protokoll gehört zu T1 des autoritativen
`IMPLEMENTIERUNGSPLAN_TRINITY.md`. Es verändert weder Vault- noch
Memory-Inhalte.

## Ursache

Der Canvas-Server bestimmte `dist/` bisher relativ zum aktuellen
Arbeitsverzeichnis. Beim Start des absoluten Server-Einstiegs aus einem anderen
Verzeichnis war deshalb zwar `/api/health` verfügbar, die Weboberfläche unter
`/` antwortete aber mit HTTP 404 und der technischen Express-Meldung
`Cannot GET /`.

Der korrigierte Server bestimmt seine Installationswurzel aus
`import.meta.url`. Der Produktions-Smoke-Test startet ihn absichtlich aus einem
fremden Arbeitsverzeichnis und prüft Health, Weboberfläche und eine unbekannte
API-Route.

## Bereits auf dem Mac geprüft

- TypeScript-Typecheck und Produktionsbuild in gebündelter und Standalone-
  Arbeitskopie
- identische geänderte Quelldateien in beiden Arbeitskopien
- Root-GET aus fremdem Arbeitsverzeichnis: HTTP 200
- Health: `ok=true`, Dienst `trinity-creative-canvas`, `uiReady=true`
- unbekannte API-Route: verständliche JSON-Antwort mit HTTP 404
- `trinity canvas start`, Status `ready`, anschließend `trinity canvas stop`
- gezielte Python-Tests für Manager, Doctor, Bridge, CLI und Installer
- vollständige Trinity-Suite: 238 Tests unter Python 3.13 bestanden
- Python-Compile-Checks, Canvas-Lint, Typecheck, Build und Produktions-Smoke
  bestanden

## Windows-Abnahme nach Bereitstellung des T1-Stands

In PowerShell:

```powershell
$Trinity = "$env:LOCALAPPDATA\Trinity"
$Cli = "$Trinity\venv\Scripts\trinity.exe"

& $Cli --version
& $Cli --home $Trinity canvas status
& $Cli --home $Trinity canvas stop
& $Cli --home $Trinity canvas start
& $Cli --home $Trinity doctor

$Canvas = (& $Cli --home $Trinity canvas status | ConvertFrom-Json)
$Canvas
Invoke-RestMethod "$($Canvas.url)/api/health"
$Root = Invoke-WebRequest "$($Canvas.url)/"
$Root.StatusCode

& $Cli --home $Trinity canvas stop
```

Erwartet:

- Trinity meldet Version `0.16.59`.
- Doctor meldet Canvas nach dem Start mit `[OK]`.
- `canvas status` meldet `state=ready`, `running=true`,
  `ui_ready=true` und `http_status=200`.
- Health meldet `ok=true`, `service=trinity-creative-canvas` und
  `uiReady=true`.
- Root-GET meldet HTTP 200 und enthält `Trinity Creative Canvas`.
- Nach `canvas stop` meldet der Status `state=stopped`.
- Trinity Desktop startet anschließend Canvas erneut automatisch; der Reiter
  **Canvas** lädt ohne manuelle Port- oder URL-Eingabe.

## Companion-Abnahme

1. BIZ-Trinity auf Windows starten.
2. Auf iPhone oder iPad das Profil **Arbeit** auswählen.
3. Canvas aus der CompanionApp öffnen.
4. Prüfen, dass keine zusätzliche Canvas-Adresse oder Portnummer eingegeben
   werden muss.
5. Canvas auf Windows stoppen und in der CompanionApp neu laden.
6. Prüfen, dass eine verständliche Nichterreichbarkeitsmeldung erscheint.
7. Trinity neu starten und prüfen, dass Canvas wieder erreichbar ist.

## Abnahmeprotokoll

| Prüfung | Ergebnis |
|---|---|
| Mac Produktions-Smoke | bestanden |
| Mac verwalteter Start/Stop | bestanden |
| Vollständige Trinity-Tests | bestanden: 238 |
| CI macOS | offen |
| CI Windows | offen |
| Windows Installation/Update | offen |
| Windows Desktop | offen |
| iPhone/iPad Companion | offen |
