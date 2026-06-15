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
