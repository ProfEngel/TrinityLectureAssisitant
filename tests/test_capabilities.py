from platform_adapters import capabilities


def test_windows_capabilities_detect_sapi_and_powerpoint(monkeypatch):
    monkeypatch.setattr(
        capabilities.shutil,
        "which",
        lambda name: "powershell.exe" if name in {"powershell.exe", "powershell"} else None,
    )
    monkeypatch.setattr(
        capabilities,
        "_module_available",
        lambda name: name == "win32com",
    )

    detected = capabilities.detect_capabilities("Windows")

    assert "speech_output" in detected
    assert "powerpoint_automation" in detected
    assert "mail_automation" not in detected


def test_macos_capabilities_preserve_automation(monkeypatch):
    monkeypatch.setattr(
        capabilities.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"say", "osascript"} else None,
    )
    monkeypatch.setattr(capabilities, "_module_available", lambda name: False)

    detected = capabilities.detect_capabilities("Darwin")

    assert "speech_output" in detected
    assert "powerpoint_automation" in detected
    assert "mail_automation" in detected


def test_windows_mail_message_explains_graph_requirement():
    message = capabilities.capability_message({"mail_automation"}, "Windows")

    assert "Microsoft-Graph" in message
    assert "klassisches Outlook" in message


def test_codex_capability_is_detected_on_any_supported_host(monkeypatch):
    monkeypatch.setattr(
        capabilities.shutil,
        "which",
        lambda name: "/usr/local/bin/codex" if name == "codex" else None,
    )
    monkeypatch.setattr(capabilities, "_module_available", lambda _name: False)

    detected = capabilities.detect_capabilities("Linux")

    assert "codex_cli" in detected


def test_codex_finder_checks_desktop_launcher_locations(monkeypatch):
    monkeypatch.setattr(capabilities.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        capabilities.Path,
        "is_file",
        lambda path: str(path) == "/opt/homebrew/bin/codex",
    )

    assert capabilities.find_codex_executable() == "/opt/homebrew/bin/codex"
