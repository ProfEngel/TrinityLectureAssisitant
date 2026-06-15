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
