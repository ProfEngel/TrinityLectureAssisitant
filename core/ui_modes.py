"""Resolve Trinity's presentation modes without platform-specific UI imports."""

import platform


def resolve_ui_modes(
    system_config=None,
    platform_name=None,
    force_terminal=False,
    suppress_terminal=False,
):
    system_config = system_config or {}
    host = platform_name or platform.system()

    eyes = bool(system_config.get("eyes_ui_enabled", True))
    classic = bool(system_config.get("classic_ui_enabled", False))
    terminal = bool(
        system_config.get(
            "terminal_cli_enabled",
            system_config.get("show_terminal", host == "Windows"),
        )
    )

    if suppress_terminal and (eyes or classic):
        terminal = False
    if force_terminal:
        terminal = True
    if not eyes and not classic:
        terminal = True

    return {
        "eyes": eyes,
        "classic": classic,
        "terminal": terminal,
    }
