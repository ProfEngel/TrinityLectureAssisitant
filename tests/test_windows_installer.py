from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
INSTALLER = ROOT_DIR / "install_windows.ps1"


def test_windows_installer_targets_main_and_creates_both_launch_modes():
    script = INSTALLER.read_text(encoding="utf-8")

    assert '[string]$Branch = "main"' in script
    assert '"Trinity.lnk"' in script
    assert '"Trinity ohne Terminal.lnk"' in script
    assert "$shortcut.TargetPath = $pythonw" in script
    assert '$shortcut.Arguments = "`"$launcher`""' in script
    assert '--no-terminal' in script
    assert "trinity.cmd" in script
    assert "SetEnvironmentVariable(\"Path\"" in script
    assert "TrinityRuntime" in script
    assert "control-plane init" in script
    assert "vault setup" in script
    assert "vault init" in script
    assert "if ($isUpdate)" in script
    assert 'Join-Path $InstallDir "components\\TrinityCanvas"' in script
    assert "ProfEngel/TrinityCreativeCanvas.git" in script
    assert '$CanvasRevision = "21099e2d17181be2d3e0ad62210abfe1fda87cf8"' in script
    assert "archive/$CanvasRevision.zip" in script
    assert "archive/refs/heads/main.zip" not in script
    assert "--recurse-submodules" in script
    assert "$npm.Source run build" in script


def test_windows_installer_stops_running_trinity_before_replacing_update():
    script = INSTALLER.read_text(encoding="utf-8")

    assert "function Stop-TrinityProcesses" in script
    assert "function Remove-InstallationDirectory" in script
    assert "Get-CimInstance Win32_Process" in script
    assert "Stop-TrinityProcesses $InstallDir" in script
    assert "Remove-InstallationDirectory $InstallDir" in script
    assert script.index("Stop-TrinityProcesses $InstallDir") < script.index(
        'Copy-IfPresent "$InstallDir\\core\\config.json"'
    )
