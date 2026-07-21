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
    assert 'vault setup' in script
    assert 'vault init' in script
    assert 'if [ "$IS_UPDATE" = true ]' in script
    assert "</dev/tty" in script


def test_macos_installer_uses_supported_python_and_preserves_recovery_copy():
    script = INSTALLER.read_text(encoding="utf-8")

    assert "Python 3.10 bis 3.14" in script
    assert 'PYTHON_BIN' in script
    assert 'status --porcelain' in script
    assert 'mv "$INSTALL_DIR" "$ROLLBACK_DIR"' in script
    assert 'rm -rf "$INSTALL_DIR"' not in script


def test_macos_app_is_kept_outside_icloud_managed_desktop():
    script = (ROOT_DIR / "scripts" / "create_app.sh").read_text(encoding="utf-8")

    assert 'APPLICATIONS_DIR="$HOME/Applications"' in script
    assert 'ln -s "$APP_PATH" "$DESKTOP_LINK"' in script
    assert "desktop-launch.log" in script
    assert "codesign --verify" in script
