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
    assert "':(exclude)core/payload.html'" in script
    assert "':(exclude)core/state.txt'" in script
    assert 'mv "$INSTALL_DIR" "$ROLLBACK_DIR"' in script
    assert 'rm -rf "$INSTALL_DIR"' not in script


def test_macos_installer_only_ignores_known_runtime_ui_files():
    script = INSTALLER.read_text(encoding="utf-8")

    assert 'LOCAL_CODE_CHANGES="$(git -C "$INSTALL_DIR" status --porcelain -- .' in script
    assert 'if [ -n "$LOCAL_CODE_CHANGES" ]' in script
    assert script.count("':(exclude)core/") == 2


def test_macos_app_is_kept_outside_icloud_managed_desktop():
    script = (ROOT_DIR / "scripts" / "create_app.sh").read_text(encoding="utf-8")

    assert 'APPLICATIONS_DIR="$HOME/Applications"' in script
    assert 'ln -s "$APP_PATH" "$DESKTOP_LINK"' in script
    assert "desktop-launch.log" in script
    assert "codesign --verify" in script


def test_macos_installer_manages_canvas_outside_the_vault():
    script = INSTALLER.read_text(encoding="utf-8")
    submodules = (ROOT_DIR / ".gitmodules").read_text(encoding="utf-8")

    assert 'CANVAS_DIR="$INSTALL_DIR/components/TrinityCanvas"' in script
    assert "ProfEngel/TrinityCreativeCanvas.git" in submodules
    assert "--recurse-submodules" in script
    assert 'npm ci && npm run build' in script
    assert "trinity canvas install" in script
