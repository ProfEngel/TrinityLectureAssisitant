[CmdletBinding()]
param(
    [string]$InstallDir = "$env:LOCALAPPDATA\Trinity",
    [string]$Repository = "https://github.com/ProfEngel/TrinityLectureAssisitant.git",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Write-Host "Trinity Assistant Installer for Windows 11"
Write-Host "=========================================="
Write-Host ""

function Get-PythonCommand {
    $pyLauncher = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return @{
            Executable = $pyLauncher.Source
            Prefix = @("-3.11")
        }
    }

    $python = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if ($python) {
        return @{
            Executable = $python.Source
            Prefix = @()
        }
    }

    throw "Python 3.11 wurde nicht gefunden. Bitte Python von https://www.python.org/downloads/windows/ installieren und 'Add Python to PATH' aktivieren."
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

$pythonCommand = Get-PythonCommand
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "$InstallDir`_backup_$timestamp"
$isUpdate = Test-Path $InstallDir

if ($isUpdate) {
    Write-Host "Bestehende Installation erkannt. Sichere Nutzerdaten ..."
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

    Copy-IfPresent "$InstallDir\core\config.json" "$backupDir\config.json"
    Copy-IfPresent "$InstallDir\core\Soul.md" "$backupDir\Soul.md"
    Copy-IfPresent "$InstallDir\core\User.md" "$backupDir\User.md"
    Copy-DirectoryContents "$InstallDir\memory" "$backupDir\memory"
    Copy-DirectoryContents "$InstallDir\RAG" "$backupDir\RAG"
    Copy-DirectoryContents "$InstallDir\gen_images" "$backupDir\gen_images"

    Remove-Item $InstallDir -Recurse -Force
}

Write-Host "Lade Trinity herunter ..."
$git = Get-Command "git.exe" -ErrorAction SilentlyContinue
if ($git) {
    & $git.Source clone --branch $Branch --single-branch $Repository $InstallDir
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
}

if ($isUpdate) {
    Write-Host "Stelle Nutzerdaten wieder her ..."
    Copy-IfPresent "$backupDir\config.json" "$InstallDir\core\config.json"
    Copy-IfPresent "$backupDir\Soul.md" "$InstallDir\core\Soul.md"
    Copy-IfPresent "$backupDir\User.md" "$InstallDir\core\User.md"
    Copy-DirectoryContents "$backupDir\memory" "$InstallDir\memory"
    Copy-DirectoryContents "$backupDir\RAG" "$InstallDir\RAG" @("build_index.py")
    Copy-DirectoryContents "$backupDir\gen_images" "$InstallDir\gen_images"
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

foreach ($shortcutPath in @(
    (Join-Path $desktop "Trinity.lnk"),
    (Join-Path $startMenu "Trinity.lnk")
)) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $pythonw
    $shortcut.Arguments = "`"$launcher`""
    $shortcut.WorkingDirectory = $InstallDir
    if (Test-Path $iconIco) {
        $shortcut.IconLocation = $iconIco
    }
    $shortcut.Description = "Trinity Academic Personal Concierge"
    $shortcut.Save()
}

Write-Host ""
Write-Host "Installation abgeschlossen."
Write-Host "Trinity liegt unter: $InstallDir"
Write-Host "Desktop- und Startmenü-Verknüpfung wurden erstellt."
Write-Host ""
Write-Host "Beim ersten Start fragt Windows gegebenenfalls nach Mikrofonzugriff."
