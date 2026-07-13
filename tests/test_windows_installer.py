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
