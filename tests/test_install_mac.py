from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
INSTALLER = ROOT_DIR / "install_mac.sh"


def test_macos_installer_adds_trinity_cli_to_user_path():
    script = INSTALLER.read_text(encoding="utf-8")

    assert '".[macos]"' in script
    assert 'CLI_PATH="$CLI_BIN/trinity"' in script
    assert 'export PATH="$HOME/.local/bin:$PATH"' in script
    assert '"$INSTALL_DIR/TrinityRuntime"' in script
    assert 'control-plane init' in script
