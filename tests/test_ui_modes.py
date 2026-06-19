from core.ui_modes import resolve_ui_modes


def test_first_start_uses_classic_ui_as_default():
    modes = resolve_ui_modes({}, platform_name="Darwin")

    assert modes == {
        "eyes": False,
        "classic": True,
        "web": False,
        "terminal": False,
    }


def test_legacy_terminal_setting_remains_supported():
    modes = resolve_ui_modes(
        {"show_terminal": True},
        platform_name="Darwin",
    )

    assert modes["terminal"] is True


def test_terminal_is_forced_when_both_graphical_uis_are_disabled():
    modes = resolve_ui_modes(
        {
            "eyes_ui_enabled": False,
            "classic_ui_enabled": False,
            "terminal_cli_enabled": False,
        },
        platform_name="Linux",
    )

    assert modes == {
        "eyes": False,
        "classic": False,
        "web": False,
        "terminal": True,
    }


def test_no_terminal_flag_only_applies_when_a_gui_remains():
    graphical = resolve_ui_modes(
        {
            "eyes_ui_enabled": False,
            "classic_ui_enabled": True,
            "terminal_cli_enabled": True,
        },
        suppress_terminal=True,
    )
    headless = resolve_ui_modes(
        {
            "eyes_ui_enabled": False,
            "classic_ui_enabled": False,
            "terminal_cli_enabled": True,
        },
        suppress_terminal=True,
    )

    assert graphical["terminal"] is False
    assert headless["terminal"] is True


def test_diagnostic_mode_forces_terminal():
    modes = resolve_ui_modes(
        {
            "eyes_ui_enabled": True,
            "classic_ui_enabled": False,
            "terminal_cli_enabled": False,
        },
        force_terminal=True,
    )

    assert modes["terminal"] is True


def test_web_ui_is_a_valid_surface_without_terminal():
    modes = resolve_ui_modes(
        {
            "eyes_ui_enabled": False,
            "classic_ui_enabled": False,
            "web_ui_enabled": True,
            "terminal_cli_enabled": False,
        },
        platform_name="Darwin",
    )

    assert modes == {
        "eyes": False,
        "classic": False,
        "web": True,
        "terminal": False,
    }
