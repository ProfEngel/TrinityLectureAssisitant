[CmdletBinding()]
param(
    [string]$TrinityRoot = "$env:LOCALAPPDATA\Trinity",
    [string]$VoiceSource = "",
    [switch]$OpenFirewall
)

$ErrorActionPreference = "Stop"
$python = Join-Path $TrinityRoot "venv\Scripts\python.exe"
$voiceDir = Join-Path $TrinityRoot "TrinityRuntime\voices\eve"
$refText = Join-Path $TrinityRoot "assets\voices\eve\ref_text.txt"

if (-not (Test-Path $python)) {
    throw "Trinity Python environment not found: $python"
}
if ([Environment]::OSVersion.Version.Major -lt 10) {
    throw "The Eve server profile requires Windows 11."
}

& $python -m pip install "speech-to-speech==0.2.11" "websockets>=14,<18"
if ($LASTEXITCODE -ne 0) { throw "Voice dependencies could not be installed." }

New-Item -ItemType Directory -Path $voiceDir -Force | Out-Null
Copy-Item $refText (Join-Path $voiceDir "ref_text.txt") -Force
if ($VoiceSource) {
    if (-not (Test-Path $VoiceSource)) { throw "Voice sample not found: $VoiceSource" }
    Copy-Item $VoiceSource (Join-Path $voiceDir "Eve_Schule.mp3") -Force
} else {
    Write-Warning "No voice sample copied. Re-run with -VoiceSource after authorization."
}

$nvidia = Get-Command "nvidia-smi.exe" -ErrorAction SilentlyContinue
if ($nvidia) {
    Write-Host "NVIDIA GPU detected. Install the Qwen3-TTS CUDA adapter required by your selected checkpoint."
} else {
    Write-Warning "No NVIDIA GPU detected. Windows can retain Legacy TTS; Eve synthesis is not practical on CPU."
}

$tailscale = Get-Command "tailscale.exe" -ErrorAction SilentlyContinue
Write-Host $(if ($tailscale) { "Tailscale detected." } else { "Tailscale not detected (optional)." })

if ($OpenFirewall) {
    $ruleName = "Trinity Eve Voice 8766"
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8766 -Profile Private -ErrorAction Stop | Out-Null
    Write-Host "Private-network firewall rule created for TCP 8766."
}

Write-Host "Eve dependencies installed. Trinity still uses the Legacy voice engine."
Write-Host "Next: trinity voice doctor --profile eve-windows-server"
