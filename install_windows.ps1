[CmdletBinding()]
param(
    [string]$InstallDir = "$env:LOCALAPPDATA\Trinity",
    [string]$Repository = "https://github.com/ProfEngel/TrinityLectureAssisitant.git",
    [string]$Branch = "main",
    [switch]$SkipPythonInstall,
    [switch]$ValidateEnvironmentOnly
)

$CanvasInstallDir = Join-Path $InstallDir "components\TrinityCanvas"
$CanvasRepository = "https://github.com/ProfEngel/TrinityCreativeCanvas.git"
$CanvasRevision = "21099e2d17181be2d3e0ad62210abfe1fda87cf8"

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Write-Host "Trinity Assistant Installer for Windows 11"
Write-Host "=========================================="
Write-Host ""

function Get-PythonCandidates {
    $candidates = [System.Collections.Generic.List[hashtable]]::new()
    $seen = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::OrdinalIgnoreCase
    )

    $pyLauncher = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        foreach ($version in @("-3.13", "-3.14", "-3.12", "-3.11", "-3.10")) {
            $key = "$($pyLauncher.Source)|$version"
            if ($seen.Add($key)) {
                $candidates.Add(@{
                    Executable = $pyLauncher.Source
                    Prefix = @($version)
                    Description = "Python Launcher $version"
                })
            }
        }
    }

    foreach ($commandName in @("python.exe", "python3.exe")) {
        $python = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($python -and $seen.Add($python.Source)) {
            $candidates.Add(@{
                Executable = $python.Source
                Prefix = @()
                Description = $python.Source
            })
        }
    }

    $knownRoots = @(
        "$env:LOCALAPPDATA\Programs\Python",
        "$env:ProgramFiles\Python",
        "${env:ProgramFiles(x86)}\Python"
    )
    foreach ($root in $knownRoots) {
        if (-not $root -or -not (Test-Path $root)) {
            continue
        }

        Get-ChildItem $root -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch "\\venv\\" } |
            Sort-Object FullName -Descending |
            ForEach-Object {
                if ($seen.Add($_.FullName)) {
                    $candidates.Add(@{
                        Executable = $_.FullName
                        Prefix = @()
                        Description = $_.FullName
                    })
                }
            }
    }

    return $candidates
}

function Test-PythonCommand {
    param(
        [hashtable]$PythonCommand
    )

    $probe = @"
import ssl
import struct
import sys
import venv

if sys.version_info[:2] < (3, 10) or sys.version_info[:2] >= (3, 15):
    raise RuntimeError(f'Python {sys.version.split()[0]} wird nicht unterstuetzt')
if struct.calcsize('P') * 8 != 64:
    raise RuntimeError('Trinity benoetigt 64-Bit-Python')

print(f'{sys.executable}|{sys.version.split()[0]}|{ssl.OPENSSL_VERSION}')
"@

    $previousErrorAction = $ErrorActionPreference
    try {
        # Windows PowerShell 5 wraps native stderr as ErrorRecord objects. Invalid
        # candidates are expected here, so inspect their exit code without aborting.
        $ErrorActionPreference = "Continue"
        $probeOutput = & $PythonCommand.Executable @($PythonCommand.Prefix) -c $probe 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }

    return @{
        IsValid = ($exitCode -eq 0)
        Details = (($probeOutput | ForEach-Object { "$_" }) -join "`n").Trim()
    }
}

function Find-CompatiblePython {
    $diagnostics = [System.Collections.Generic.List[string]]::new()

    foreach ($candidate in @(Get-PythonCandidates)) {
        $result = Test-PythonCommand $candidate
        if ($result.IsValid) {
            Write-Host "Verwende $($candidate.Description): $($result.Details)"
            return $candidate
        }

        if ($result.Details) {
            $diagnostics.Add("$($candidate.Description): $($result.Details)")
        }
    }

    if ($diagnostics.Count -gt 0) {
        Write-Warning "Gefundene Python-Installationen sind nicht kompatibel oder besitzen kein funktionierendes SSL:"
        $diagnostics | ForEach-Object { Write-Warning "  $_" }
    }

    return $null
}

function Install-CompatiblePython {
    $winget = Get-Command "winget.exe" -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "Kein kompatibles Python mit SSL gefunden. Bitte Python 3.13 (64 Bit) von https://www.python.org/downloads/windows/ installieren und den Installer erneut starten."
    }

    Write-Host "Installiere beziehungsweise repariere Python 3.13 mit Windows Package Manager ..."
    & $winget.Source install `
        --id Python.Python.3.13 `
        --exact `
        --source winget `
        --scope user `
        --silent `
        --force `
        --disable-interactivity `
        --accept-package-agreements `
        --accept-source-agreements

    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.13 konnte nicht automatisch installiert werden. Bitte Python 3.13 (64 Bit) von https://www.python.org/downloads/windows/ installieren."
    }
}

function Get-PythonCommand {
    $pythonCommand = Find-CompatiblePython
    if ($pythonCommand) {
        return $pythonCommand
    }

    if ($SkipPythonInstall) {
        throw "Kein kompatibles Python mit SSL gefunden. Die automatische Python-Installation wurde deaktiviert."
    }

    Install-CompatiblePython
    $pythonCommand = Find-CompatiblePython
    if (-not $pythonCommand) {
        throw "Python 3.13 wurde installiert, konnte aber noch nicht verwendet werden. Bitte PowerShell neu öffnen und den Installer erneut starten."
    }

    return $pythonCommand
}

function Invoke-Python {
    param(
        [hashtable]$PythonCommand,
        [string[]]$Arguments
    )

    & $PythonCommand.Executable @($PythonCommand.Prefix) @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python-Befehl fehlgeschlagen: $($Arguments -join ' ')"
    }
}

function Copy-IfPresent {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (Test-Path $Source) {
        Copy-Item $Source $Destination -Recurse -Force
    }
}

function Copy-DirectoryContents {
    param(
        [string]$Source,
        [string]$Destination,
        [string[]]$ExcludeNames = @()
    )

    if (-not (Test-Path $Source)) {
        return
    }

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Get-ChildItem $Source -Force |
        Where-Object { $_.Name -notin $ExcludeNames } |
        Copy-Item -Destination $Destination -Recurse -Force
}

function Stop-TrinityProcesses {
    param([string]$Root)

    # The launcher, settings UI, and console are Python processes. Stop only
    # processes whose command line belongs to this exact installation.
    $normalizedRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd("\\")
    $escapedRoot = [regex]::Escape($normalizedRoot)
    $processes = @(
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object {
                $_.ProcessId -ne $PID -and
                $_.CommandLine -and
                $_.CommandLine -match $escapedRoot
            }
    )

    if ($processes.Count -eq 0) {
        return
    }

    Write-Host "Beende laufende Trinity-Prozesse fuer das Update ..."
    foreach ($process in $processes) {
        try {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
        }
        catch {
            Write-Warning "Trinity-Prozess $($process.ProcessId) konnte nicht beendet werden: $($_.Exception.Message)"
        }
    }

    Start-Sleep -Seconds 2
}

function Remove-InstallationDirectory {
    param([string]$Path)

    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            Remove-Item $Path -Recurse -Force -ErrorAction Stop
            return
        }
        catch {
            if ($attempt -eq 5) {
                throw "Die bestehende Trinity-Installation konnte nicht entfernt werden. Bitte Trinity und alle offenen Einstellungen schliessen und das Update erneut starten. Details: $($_.Exception.Message)"
            }
            Start-Sleep -Seconds 1
        }
    }
}

$pythonCommand = Get-PythonCommand
if ($ValidateEnvironmentOnly) {
    Write-Host ""
    Write-Host "Python- und SSL-Pruefung erfolgreich."
    exit 0
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "$InstallDir`_backup_$timestamp"
$isUpdate = Test-Path $InstallDir

if ($isUpdate) {
    Stop-TrinityProcesses $InstallDir
    Write-Host "Bestehende Installation erkannt. Sichere Nutzerdaten ..."
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

    Copy-IfPresent "$InstallDir\core\config.json" "$backupDir\config.json"
    Copy-IfPresent "$InstallDir\core\Soul.md" "$backupDir\Soul.md"
    Copy-IfPresent "$InstallDir\core\User.md" "$backupDir\User.md"
    Copy-DirectoryContents "$InstallDir\memory" "$backupDir\memory"
    Copy-DirectoryContents "$InstallDir\RAG" "$backupDir\RAG"
    Copy-DirectoryContents "$InstallDir\gen_images" "$backupDir\gen_images"
    Copy-DirectoryContents "$InstallDir\logs" "$backupDir\logs"
    Copy-DirectoryContents "$InstallDir\TrinityRuntime" "$backupDir\TrinityRuntime"

    Remove-InstallationDirectory $InstallDir
}

Write-Host "Lade Trinity herunter ..."
$git = Get-Command "git.exe" -ErrorAction SilentlyContinue
if ($git) {
    & $git.Source clone --branch $Branch --single-branch --recurse-submodules --shallow-submodules $Repository $InstallDir
    if ($LASTEXITCODE -ne 0) {
        throw "Git konnte Trinity nicht herunterladen."
    }
}
else {
    $zipPath = Join-Path $env:TEMP "trinity-$timestamp.zip"
    $extractPath = Join-Path $env:TEMP "trinity-$timestamp"
    $zipUrl = "https://github.com/ProfEngel/TrinityLectureAssisitant/archive/refs/heads/$Branch.zip"

    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force
    $sourceDir = Get-ChildItem $extractPath -Directory | Select-Object -First 1
    Move-Item $sourceDir.FullName $InstallDir
    Remove-Item $zipPath, $extractPath -Recurse -Force

    $canvasZipPath = Join-Path $env:TEMP "trinity-canvas-$timestamp.zip"
    $canvasExtractPath = Join-Path $env:TEMP "trinity-canvas-$timestamp"
    $canvasZipUrl = "https://github.com/ProfEngel/TrinityCreativeCanvas/archive/$CanvasRevision.zip"
    Invoke-WebRequest -Uri $canvasZipUrl -OutFile $canvasZipPath
    Expand-Archive -Path $canvasZipPath -DestinationPath $canvasExtractPath -Force
    $canvasSourceDir = Get-ChildItem $canvasExtractPath -Directory | Select-Object -First 1
    New-Item -ItemType Directory -Path (Split-Path $CanvasInstallDir) -Force | Out-Null
    Move-Item $canvasSourceDir.FullName $CanvasInstallDir
    Remove-Item $canvasZipPath, $canvasExtractPath -Recurse -Force
}

if ($isUpdate) {
    Write-Host "Stelle Nutzerdaten wieder her ..."
    Copy-IfPresent "$backupDir\config.json" "$InstallDir\core\config.json"
    Copy-IfPresent "$backupDir\Soul.md" "$InstallDir\core\Soul.md"
    Copy-IfPresent "$backupDir\User.md" "$InstallDir\core\User.md"
    Copy-DirectoryContents "$backupDir\memory" "$InstallDir\memory"
    Copy-DirectoryContents "$backupDir\RAG" "$InstallDir\RAG" @("build_index.py")
    Copy-DirectoryContents "$backupDir\gen_images" "$InstallDir\gen_images"
    Copy-DirectoryContents "$backupDir\logs" "$InstallDir\logs"
    Copy-DirectoryContents "$backupDir\TrinityRuntime" "$InstallDir\TrinityRuntime"
    Remove-Item $backupDir -Recurse -Force
}

if (-not (Test-Path "$InstallDir\core\Soul.md")) {
    Copy-Item "$InstallDir\core\Soul.md.example" "$InstallDir\core\Soul.md"
}
if (-not (Test-Path "$InstallDir\core\User.md")) {
    Copy-Item "$InstallDir\core\User.md.example" "$InstallDir\core\User.md"
}

Write-Host "Erstelle virtuelle Python-Umgebung ..."
Invoke-Python $pythonCommand @("-m", "venv", "$InstallDir\venv")

$venvPython = "$InstallDir\venv\Scripts\python.exe"
$venvResult = Test-PythonCommand @{
    Executable = $venvPython
    Prefix = @()
    Description = $venvPython
}
if (-not $venvResult.IsValid) {
    throw "Die virtuelle Python-Umgebung besitzt kein funktionierendes SSL: $($venvResult.Details)"
}

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "pip konnte nicht aktualisiert werden."
}

Write-Host "Installiere Trinity-Abhängigkeiten ..."
Push-Location $InstallDir
try {
    & $venvPython -m pip install ".[windows]"
    if ($LASTEXITCODE -ne 0) {
        throw "Trinity-Abhängigkeiten konnten nicht installiert werden."
    }
}
finally {
    Pop-Location
}

Write-Host "Installiere Trinity Canvas ..."
$node = Get-Command "node.exe" -ErrorAction SilentlyContinue
$npm = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
if (-not $node -or -not $npm) {
    Write-Warning "Node.js/npm fehlt. Trinity läuft; Canvas kann nach der Node.js-Installation ergänzt werden."
}
elseif (Test-Path "$CanvasInstallDir\package.json") {
    Push-Location $CanvasInstallDir
    try {
        & $npm.Source ci
        if ($LASTEXITCODE -ne 0) { throw "Canvas-Abhängigkeiten konnten nicht installiert werden." }
        & $npm.Source run build
        if ($LASTEXITCODE -ne 0) { throw "Trinity Canvas konnte nicht gebaut werden." }
    }
    finally { Pop-Location }
}
else {
    throw "Die zu Trinity gehörende Canvas-Komponente fehlt."
}

$cliBin = "$InstallDir\bin"
$cliWrapper = "$cliBin\trinity.cmd"
New-Item -ItemType Directory -Path $cliBin -Force | Out-Null
$cliContent = @"
@echo off
"$venvPython" "$InstallDir\trinity_cli.py" %*
"@
[System.IO.File]::WriteAllText(
    $cliWrapper,
    $cliContent,
    [System.Text.UTF8Encoding]::new($false)
)

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$pathEntries = @($userPath -split ";" | Where-Object { $_ })
if ($cliBin -notin $pathEntries) {
    $newUserPath = (@($pathEntries) + $cliBin) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
}
if ($cliBin -notin ($env:Path -split ";")) {
    $env:Path = "$env:Path;$cliBin"
}

if ($isUpdate) {
    Write-Host "Pruefe den bereits konfigurierten Inhalts-Vault ..."
    & $venvPython "$InstallDir\trinity_cli.py" --home $InstallDir vault init
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Der bestehende Vault war noch nicht eindeutig konfiguriert."
        Write-Host "Bitte waehle jetzt den vorhandenen oder einen neuen Vault-Ordner."
        & $venvPython "$InstallDir\trinity_cli.py" --home $InstallDir vault setup
        if ($LASTEXITCODE -ne 0) {
            throw "Der Inhalts-Vault konnte nicht eingerichtet werden."
        }
    }
}
else {
    Write-Host "Richte den Inhalts-Vault fuer diese Neuinstallation ein ..."
    Write-Host "Du bestimmst selbst, wo der Vault liegen soll."
    & $venvPython "$InstallDir\trinity_cli.py" --home $InstallDir vault setup
    if ($LASTEXITCODE -ne 0) {
        throw "Der Inhalts-Vault konnte nicht eingerichtet werden."
    }
}

Write-Host "Initialisiere lokale MainHub-/Control-Plane-Daten ..."
Push-Location $InstallDir
try {
    & $venvPython "$InstallDir\trinity_cli.py" --home $InstallDir control-plane init | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Control Plane konnte jetzt nicht initialisiert werden. Später möglich mit: trinity control-plane init"
    }
}
finally {
    Pop-Location
}

$iconPng = "$InstallDir\core\icon.png"
$iconIco = "$InstallDir\assets\trinity_icon.ico"
if (Test-Path $iconPng) {
    $env:TRINITY_ICON_SOURCE = $iconPng
    $env:TRINITY_ICON_TARGET = $iconIco
    & $venvPython -c "import os; from PIL import Image; Image.open(os.environ['TRINITY_ICON_SOURCE']).save(os.environ['TRINITY_ICON_TARGET'], sizes=[(16,16),(32,32),(48,48),(256,256)])"
    Remove-Item Env:TRINITY_ICON_SOURCE, Env:TRINITY_ICON_TARGET
}

$pythonw = "$InstallDir\venv\Scripts\pythonw.exe"
$launcher = "$InstallDir\trinity_launcher.py"
$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$startup = [Environment]::GetFolderPath("Startup")

foreach ($shortcutPath in @(
    (Join-Path $desktop "Trinity.lnk"),
    (Join-Path $startMenu "Trinity.lnk"),
    (Join-Path $startup "Trinity.lnk")
)) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $pythonw
    $shortcut.Arguments = "`"$launcher`""
    $shortcut.WorkingDirectory = $InstallDir
    if (Test-Path $iconIco) {
        $shortcut.IconLocation = $iconIco
    }
    $shortcut.Description = "Trinity mit den konfigurierten Oberflächen starten"
    $shortcut.Save()
}

$legacyDiagnosticShortcut = Join-Path $desktop "Trinity Diagnose.lnk"
if (Test-Path $legacyDiagnosticShortcut) {
    Remove-Item $legacyDiagnosticShortcut -Force
}

$silentShortcut = $shell.CreateShortcut((Join-Path $desktop "Trinity ohne Terminal.lnk"))
$silentShortcut.TargetPath = $pythonw
$silentShortcut.Arguments = "`"$launcher`" --no-terminal"
$silentShortcut.WorkingDirectory = $InstallDir
if (Test-Path $iconIco) {
    $silentShortcut.IconLocation = $iconIco
}
$silentShortcut.Description = "Trinity ohne sichtbares Terminal starten"
$silentShortcut.Save()

Write-Host ""
Write-Host "Installation abgeschlossen."
Write-Host "Trinity liegt unter: $InstallDir"
Write-Host "Trinity startet mit den in den Einstellungen gewählten Oberflächen."
Write-Host "Eine zusätzliche Desktop-Verknüpfung unterdrückt das Terminal, sofern eine GUI aktiv ist."
Write-Host "In einer neuen PowerShell steht außerdem der Befehl 'trinity' bereit."
Write-Host "Canvas startet mit Trinity und erscheint ohne Portangabe im Desktop-Reiter 'Canvas'."
Write-Host "Trinity und die Werkstatt starten künftig automatisch bei der Windows-Anmeldung."
Write-Host "Im Browser ist die Werkstatt unter http://127.0.0.1:8765/#werkstatt erreichbar."
Write-Host ""
Write-Host "Beim ersten Start fragt Windows gegebenenfalls nach Mikrofonzugriff."
