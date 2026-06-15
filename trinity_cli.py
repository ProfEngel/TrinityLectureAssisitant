"""Command line entry point for Trinity Assistant."""

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path


VERSION = "0.10.3"


def find_trinity_home(explicit=None):
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    if os.environ.get("TRINITY_HOME"):
        candidates.append(Path(os.environ["TRINITY_HOME"]).expanduser())
    candidates.extend(
        [
            Path.cwd(),
            Path(sys.prefix).resolve().parent,
            Path(__file__).resolve().parent,
            Path.home() / "Trinity_Assistant",
        ]
    )
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata) / "Trinity")

    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / "trinity_launcher.py").is_file():
            return resolved
    return None


def _core_modules(home):
    core_dir = str(Path(home) / "core")
    if core_dir not in sys.path:
        sys.path.insert(0, core_dir)
    from configuration import (  # pylint: disable=import-outside-toplevel
        ensure_support_files,
        load_config,
        parse_setting_value,
        save_config,
        set_config_value,
    )

    return {
        "ensure_support_files": ensure_support_files,
        "load_config": load_config,
        "parse_setting_value": parse_setting_value,
        "save_config": save_config,
        "set_config_value": set_config_value,
    }


def _prompt(label, default="", input_fn=input):
    suffix = f" [{default}]" if default not in ("", None) else ""
    value = input_fn(f"{label}{suffix}: ").strip()
    return value if value else default


def _prompt_choice(label, choices, default, input_fn=input):
    rendered = "/".join(choices)
    while True:
        value = _prompt(f"{label} ({rendered})", default, input_fn).casefold()
        if value in choices:
            return value
        print("Bitte eine der angezeigten Optionen wählen.")


def _configure_surfaces(config, input_fn=input):
    system = config.setdefault("system", {})
    current = []
    if system.get("eyes_ui_enabled", True):
        current.append("eyes")
    if system.get("classic_ui_enabled", False):
        current.append("classic")
    if system.get("terminal_cli_enabled", system.get("show_terminal", False)):
        current.append("terminal")
    default = ",".join(current) or "terminal"
    raw = _prompt(
        "Oberflächen, kommagetrennt: eyes, classic, terminal",
        default,
        input_fn,
    )
    selected = {
        item.strip().casefold()
        for item in raw.split(",")
        if item.strip().casefold() in {"eyes", "classic", "terminal"}
    }
    if not selected:
        selected = {"terminal"}
    if not selected.intersection({"eyes", "classic"}):
        selected.add("terminal")
    system["eyes_ui_enabled"] = "eyes" in selected
    system["classic_ui_enabled"] = "classic" in selected
    system["terminal_cli_enabled"] = "terminal" in selected
    system["show_terminal"] = "terminal" in selected


def _configure_llm(config, input_fn=input, secret_fn=getpass.getpass):
    llm = config.setdefault("llm", {})
    slot = _prompt_choice(
        "Provider-Slot",
        ("local", "remote_1", "remote_2"),
        llm.get("active_slot", "local"),
        input_fn,
    )
    provider = llm.setdefault(slot, {})
    provider["url"] = _prompt(
        "API-URL",
        provider.get("url", ""),
        input_fn,
    )
    provider["model"] = _prompt(
        "Modellname",
        provider.get("model", ""),
        input_fn,
    )
    if _prompt_choice(
        "API-Key ändern",
        ("nein", "ja"),
        "nein",
        input_fn,
    ) == "ja":
        provider["api_key"] = secret_fn("API-Key: ").strip()
    llm["active_slot"] = slot


def interactive_settings(home, input_fn=input, secret_fn=getpass.getpass):
    modules = _core_modules(home)
    config_path = Path(home) / "core" / "config.json"
    config = modules["load_config"](config_path)

    while True:
        system = config.get("system", {})
        print("\nTrinity Settings CLI")
        print("====================")
        print(f"1  Oberflächen")
        print(f"2  Betriebsmodus ({system.get('mode', 'chat')})")
        print(f"3  LLM-Provider ({config.get('llm', {}).get('active_slot', 'local')})")
        print("4  Codex")
        print("5  Telegram")
        print("s  Speichern und beenden")
        print("q  Verwerfen")
        choice = input_fn("Auswahl: ").strip().casefold()

        if choice == "1":
            _configure_surfaces(config, input_fn)
        elif choice == "2":
            system["mode"] = _prompt_choice(
                "Betriebsmodus",
                ("chat", "office", "lecture"),
                system.get("mode", "chat"),
                input_fn,
            )
        elif choice == "3":
            _configure_llm(config, input_fn, secret_fn)
        elif choice == "4":
            codex = config.setdefault("codex", {})
            codex["enabled"] = (
                _prompt_choice(
                    "Codex aktivieren",
                    ("nein", "ja"),
                    "ja" if codex.get("enabled") else "nein",
                    input_fn,
                )
                == "ja"
            )
            codex["executable"] = _prompt(
                "Codex-Programm",
                codex.get("executable", "codex"),
                input_fn,
            )
        elif choice == "5":
            telegram = config.setdefault("telegram", {})
            telegram["enabled"] = (
                _prompt_choice(
                    "Telegram aktivieren",
                    ("nein", "ja"),
                    "ja" if telegram.get("enabled") else "nein",
                    input_fn,
                )
                == "ja"
            )
            telegram["chat_id"] = _prompt(
                "Telegram Chat-ID",
                telegram.get("chat_id", ""),
                input_fn,
            )
            if _prompt_choice(
                "Bot-Token ändern",
                ("nein", "ja"),
                "nein",
                input_fn,
            ) == "ja":
                telegram["bot_token"] = secret_fn("Bot-Token: ").strip()
        elif choice == "s":
            modules["save_config"](config_path, config)
            print(f"Einstellungen gespeichert: {config_path}")
            return 0
        elif choice == "q":
            print("Änderungen verworfen.")
            return 0


def run_onboarding(home, input_fn=input, secret_fn=getpass.getpass):
    modules = _core_modules(home)
    modules["ensure_support_files"](home)
    config_path = Path(home) / "core" / "config.json"
    config = modules["load_config"](config_path)

    print("\nTrinity Onboarding")
    print("==================")
    print("Die Einrichtung kann später mit `trinity settings` geändert werden.\n")

    persona = config.setdefault("persona", {})
    persona["agent_name"] = _prompt(
        "Name der Assistenz",
        persona.get("agent_name", "Trinity"),
        input_fn,
    )
    system = config.setdefault("system", {})
    system["mode"] = _prompt_choice(
        "Haupteinsatz",
        ("chat", "office", "lecture"),
        system.get("mode", "chat"),
        input_fn,
    )
    _configure_surfaces(config, input_fn)
    _configure_llm(config, input_fn, secret_fn)
    modules["save_config"](config_path, config)

    print("\nOnboarding abgeschlossen.")
    print("Prüfung: `trinity doctor`")
    print("Start:   `trinity start`")
    return 0


def _sanitized_summary(config):
    result = {
        "persona": {
            "agent_name": config.get("persona", {}).get("agent_name"),
        },
        "system": config.get("system", {}),
        "llm": {
            "active_slot": config.get("llm", {}).get("active_slot"),
        },
        "codex": {
            "enabled": config.get("codex", {}).get("enabled", False),
            "projects": sorted(config.get("codex", {}).get("projects", {})),
        },
        "telegram": {
            "enabled": config.get("telegram", {}).get("enabled", False),
        },
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


def run_settings(home, args):
    if args.gui:
        return subprocess.call(
            [sys.executable, str(Path(home) / "core" / "settings_ui.py")],
            cwd=str(home),
        )

    modules = _core_modules(home)
    config_path = Path(home) / "core" / "config.json"
    config = modules["load_config"](config_path)
    if args.show:
        print(_sanitized_summary(config))
        return 0
    if args.set_values:
        for assignment in args.set_values:
            if "=" not in assignment:
                raise ValueError(
                    f"Ungültige Einstellung `{assignment}`; erwartet wird pfad=wert."
                )
            path, raw_value = assignment.split("=", 1)
            modules["set_config_value"](
                config,
                path.strip(),
                modules["parse_setting_value"](raw_value),
            )
        modules["save_config"](config_path, config)
        print(f"{len(args.set_values)} Einstellung(en) gespeichert.")
        return 0
    return interactive_settings(home)


def run_doctor_command(home, args):
    core_dir = str(Path(home) / "core")
    if core_dir not in sys.path:
        sys.path.insert(0, core_dir)
    from doctor import doctor_exit_code, run_doctor  # pylint: disable=import-outside-toplevel

    results = run_doctor(home, fix=args.fix, online=args.online)
    print("\nTrinity Doctor")
    print("==============")
    for item in results:
        print(f"[{item['level']:<5}] {item['name']}: {item['message']}")
    return doctor_exit_code(results)


def run_start(home, args):
    command = [sys.executable, str(Path(home) / "trinity_launcher.py")]
    if args.surface != "configured":
        command.extend(["--surface", args.surface])
    return subprocess.call(command, cwd=str(home))


def build_parser():
    parser = argparse.ArgumentParser(
        prog="trinity",
        description="Trinity Assistant verwalten und starten.",
    )
    parser.add_argument("--home", help="Pfad zur Trinity-Installation")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    subparsers = parser.add_subparsers(dest="command")

    start = subparsers.add_parser("start", help="Trinity starten")
    start.add_argument(
        "--surface",
        choices=("configured", "classic", "eyes", "terminal", "all"),
        default="configured",
        help="Oberflächen für diesen Start temporär überschreiben",
    )

    settings = subparsers.add_parser(
        "settings",
        help="Einstellungen im Terminal bearbeiten",
    )
    settings.add_argument("--gui", action="store_true", help="Grafische Settings öffnen")
    settings.add_argument("--show", action="store_true", help="Sichere Übersicht anzeigen")
    settings.add_argument(
        "--set",
        dest="set_values",
        action="append",
        default=[],
        metavar="PFAD=WERT",
        help="Einstellung direkt setzen, mehrfach verwendbar",
    )

    subparsers.add_parser("onboarding", help="Geführte Ersteinrichtung")
    doctor = subparsers.add_parser("doctor", help="Installation prüfen")
    doctor.add_argument("--fix", action="store_true", help="Sichere Reparaturen anwenden")
    doctor.add_argument(
        "--online",
        action="store_true",
        help="Zusätzlich origin/main auf Aktualität prüfen",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    home = find_trinity_home(args.home)
    if not home:
        print(
            "Trinity-Installation nicht gefunden. Setze TRINITY_HOME oder nutze --home.",
            file=sys.stderr,
        )
        return 2

    try:
        if args.command == "start":
            return run_start(home, args)
        if args.command == "settings":
            return run_settings(home, args)
        if args.command == "onboarding":
            return run_onboarding(home)
        if args.command == "doctor":
            return run_doctor_command(home, args)
    except (OSError, ValueError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
