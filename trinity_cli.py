"""Command line entry point for Trinity Assistant."""

import argparse
import getpass
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


VERSION = "0.15.1"


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
    if system.get("web_ui_enabled", False):
        current.append("web")
    if system.get("terminal_cli_enabled", system.get("show_terminal", False)):
        current.append("terminal")
    default = ",".join(current) or "terminal"
    raw = _prompt(
        "Oberflächen, kommagetrennt: eyes, classic, web, terminal",
        default,
        input_fn,
    )
    selected = {
        item.strip().casefold()
        for item in raw.split(",")
        if item.strip().casefold() in {"eyes", "classic", "web", "terminal"}
    }
    if not selected:
        selected = {"terminal"}
    if not selected.intersection({"eyes", "classic", "web"}):
        selected.add("terminal")
    system["eyes_ui_enabled"] = "eyes" in selected
    system["classic_ui_enabled"] = "classic" in selected
    system["web_ui_enabled"] = "web" in selected
    system["terminal_cli_enabled"] = "terminal" in selected
    system["show_terminal"] = "terminal" in selected


def _configure_control_plane(config, home, input_fn=input):
    core_dir = str(Path(home) / "core")
    if core_dir not in sys.path:
        sys.path.insert(0, core_dir)
    from trinity_paths import (  # pylint: disable=import-outside-toplevel
        TrinityPaths,
        default_runtime_root,
        default_vault_root,
    )

    print("\nMainHub / Control Plane")
    print("=======================")
    print(
        "Trinity trennt lokale Runtime und synchronisierten Vault. Die Runtime "
        "enthaelt laufende Jobs, Datenbanken, Cache, temporaere Dateien und "
        "Secrets und sollte nicht in iCloud, OneDrive oder Google Drive liegen. "
        "Der Vault ist die Cloud- oder Sync-Ablage fuer freigegebene Agenten, "
        "Projekte, Ergebnisse, Vorlagen, Wissen und Audit."
    )
    control = config.setdefault("control_plane", {})
    runtime_default = control.get("runtime_root") or str(
        default_runtime_root(home=home)
    )
    vault_default = control.get("vault_root") or str(default_vault_root())
    control["enabled"] = (
        _prompt_choice(
            "Control Plane/MainHub aktivieren",
            ("ja", "nein"),
            "ja" if control.get("enabled", True) else "nein",
            input_fn,
        )
        == "ja"
    )
    control["runtime_root"] = _prompt(
        "Lokaler Runtime-Ordner",
        runtime_default,
        input_fn,
    )
    control["vault_root"] = _prompt(
        "Synchronisierter Cloud-Vault-Ordner",
        vault_default,
        input_fn,
    )
    paths = TrinityPaths.from_config(home, config)
    warnings = paths.separation_warnings()
    if warnings:
        print("\nWarnung:")
        for warning in warnings:
            print(f"- {warning}")
        print("Passe die Pfade an, falls die Runtime versehentlich im Cloud-Ordner liegt.")


def _configure_pi(config, input_fn=input):
    pi = config.setdefault("pi", {})
    pi["enabled"] = (
        _prompt_choice(
            "Pi-Agent aktivieren",
            ("nein", "ja"),
            "ja" if pi.get("enabled") else "nein",
            input_fn,
        )
        == "ja"
    )
    pi["executable"] = _prompt(
        "Pi-Programm oder Wrapper",
        pi.get("executable", "pi"),
        input_fn,
    )
    raw_args = pi.get("arguments", [])
    if isinstance(raw_args, list):
        default_args = " ".join(str(item) for item in raw_args)
    else:
        default_args = str(raw_args or "")
    arguments = _prompt(
        "Pi-Argumente (optional, {prompt} setzt den Prompt als Argument)",
        default_args,
        input_fn,
    )
    try:
        pi["arguments"] = shlex.split(arguments) if arguments else []
    except ValueError:
        pi["arguments"] = arguments.split() if arguments else []
    try:
        timeout = int(_prompt("Pi-Zeitlimit Sekunden", pi.get("timeout_seconds", 600), input_fn))
    except (TypeError, ValueError):
        timeout = 600
    pi["timeout_seconds"] = max(30, min(timeout, 3600))


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
        print("5  OpenCode")
        print("6  Pi")
        print("7  MainHub / Control Plane")
        print("8  Telegram")
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
            opencode = config.setdefault("opencode", {})
            opencode["enabled"] = (
                _prompt_choice(
                    "OpenCode aktivieren",
                    ("nein", "ja"),
                    "ja" if opencode.get("enabled") else "nein",
                    input_fn,
                )
                == "ja"
            )
            opencode["executable"] = _prompt(
                "OpenCode-Programm",
                opencode.get("executable", "opencode"),
                input_fn,
            )
            opencode["agent"] = _prompt(
                "OpenCode-Agent",
                opencode.get("agent", "build"),
                input_fn,
            )
        elif choice == "6":
            _configure_pi(config, input_fn)
        elif choice == "7":
            _configure_control_plane(config, home, input_fn)
        elif choice == "8":
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
    _configure_control_plane(config, home, input_fn)
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
        "opencode": {
            "enabled": config.get("opencode", {}).get("enabled", False),
            "projects": sorted(config.get("opencode", {}).get("projects", {})),
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


def run_tui_command(home, args):
    from trinity_tui import run_tui  # pylint: disable=import-outside-toplevel

    return run_tui(home, args)


def run_bridge_command(home, args):
    core_path = str(Path(home) / "core")
    if core_path not in sys.path:
        sys.path.insert(0, core_path)
    from configuration import load_config  # pylint: disable=import-outside-toplevel
    from trinity_bridge import run_bridge  # pylint: disable=import-outside-toplevel

    companion = load_config(Path(home) / "core" / "config.json").get("companion", {})
    host = args.host or companion.get("host") or "127.0.0.1"
    port = args.port or companion.get("port") or 8765
    token = args.token
    if token is None:
        token = companion.get("token", os.environ.get("TRINITY_BRIDGE_TOKEN", ""))
    return run_bridge(home, host=host, port=port, token=token)


def run_server_command(home, args):
    core_path = str(Path(home) / "core")
    if core_path not in sys.path:
        sys.path.insert(0, core_path)
    from configuration import load_config  # pylint: disable=import-outside-toplevel
    from trinity_server import run_server  # pylint: disable=import-outside-toplevel

    server = load_config(Path(home) / "core" / "config.json").get("server", {})
    host = args.host or server.get("host") or "127.0.0.1"
    port = args.port or server.get("port") or 8765
    token = args.token if args.token is not None else server.get("token", "")
    auth_enabled = bool(getattr(args, "auth", False) or server.get("auth_enabled", False))
    if auth_enabled:
        return run_server(home, host=host, port=port, token=token, auth_enabled=True)
    return run_server(home, host=host, port=port, token=token)


def run_client_command(home, args):
    modules = _core_modules(home)
    config_path = Path(home) / "core" / "config.json"
    config = modules["load_config"](config_path)
    client_config = config.setdefault("client", {})
    core_path = str(Path(home) / "core")
    if core_path not in sys.path:
        sys.path.insert(0, core_path)
    from remote_client import RemoteTrinityClient  # pylint: disable=import-outside-toplevel

    if args.client_action == "logout":
        client_config.update({"enabled": False, "server_url": "", "username": "", "token": ""})
        modules["save_config"](config_path, config)
        print("Trinity arbeitet wieder lokal. Gespeicherte Client-Anmeldung entfernt.")
        return 0

    server_url = args.url or client_config.get("server_url", "")
    if not server_url:
        raise ValueError("Bitte Server-URL mit --url angeben.")
    remote = RemoteTrinityClient(server_url, client_config.get("token", ""))
    if args.client_action == "login":
        username = args.username or _prompt("Benutzername", client_config.get("username", ""))
        password = getpass.getpass("Passwort: ")
        status = remote.auth_status()
        result = remote.login(username, password, register=bool(status.get("bootstrap_required")))
        client_config.update(
            {
                "enabled": True,
                "server_url": remote.server_url,
                "username": result["user"]["username"],
                "token": remote.token,
            }
        )
        modules["save_config"](config_path, config)
        print(f"Als {result['user']['username']} mit {remote.server_url} verbunden.")
        return 0
    if args.client_action == "add-user":
        username = args.username or _prompt("Neuer Benutzername")
        password = getpass.getpass("Passwort fuer neuen Account: ")
        result = remote.create_user(username, password, role=args.role)
        print(f"Account {result['user']['username']} angelegt ({result['user']['role']}).")
        return 0
    if args.client_action == "status":
        if not client_config.get("token"):
            print("Kein Remote-Client konfiguriert.")
            return 1
        result = remote._request("/health", method="GET")
        print(json.dumps({"server_url": remote.server_url, **result}, ensure_ascii=False, indent=2))
        return 0
    raise ValueError("Unbekannte Client-Aktion.")


def _agent_ecosystem_modules(home):
    core_path = str(Path(home) / "core")
    if core_path not in sys.path:
        sys.path.insert(0, core_path)
    from approval_manager import ApprovalManager  # pylint: disable=import-outside-toplevel
    from job_manager import JobManager  # pylint: disable=import-outside-toplevel
    from skill_registry import SkillRegistry  # pylint: disable=import-outside-toplevel

    return SkillRegistry(home), JobManager(home), ApprovalManager(home)


def run_skills_command(home, args):
    registry, _jobs, approvals = _agent_ecosystem_modules(home)
    if args.skills_action == "list":
        print(
            json.dumps(
                {
                    "summary": registry.summary(),
                    "skills": [record.summary() for record in registry.list(args.tier)],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.skills_action == "reload":
        registry.reload()
        print(json.dumps(registry.summary(), ensure_ascii=False, indent=2))
        return 0
    if args.skills_action == "promote":
        if not args.skill_id or not args.approval_id:
            raise ValueError("promote braucht SKILL_ID und --approval-id.")
        record = registry.promote(args.skill_id, approvals, args.approval_id)
        print(json.dumps(record.summary(), ensure_ascii=False, indent=2))
        return 0
    raise ValueError("Unbekannte Skill-Aktion.")


def run_jobs_command(home, args):
    _registry, jobs, _approvals = _agent_ecosystem_modules(home)
    if args.jobs_action == "list":
        print(json.dumps(jobs.list(limit=args.limit, status=args.status), ensure_ascii=False, indent=2))
        return 0
    if args.jobs_action == "show":
        if not args.job_id:
            raise ValueError("show braucht eine JOB_ID.")
        print(json.dumps(jobs.get(args.job_id), ensure_ascii=False, indent=2))
        return 0
    if args.jobs_action == "cancel":
        if not args.job_id:
            raise ValueError("cancel braucht eine JOB_ID.")
        print(
            json.dumps(
                jobs.set_status(args.job_id, "CANCELLED", "Vom Nutzer abgebrochen."),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    raise ValueError("Unbekannte Job-Aktion.")


def run_approvals_command(home, args):
    _registry, _jobs, approvals = _agent_ecosystem_modules(home)
    if args.approvals_action == "list":
        print(json.dumps(approvals.list_pending(args.job_id or ""), ensure_ascii=False, indent=2))
        return 0
    if args.approvals_action == "request":
        if not args.job_id or not args.action_type or not args.summary:
            raise ValueError("request braucht --job-id, --action-type und --summary.")
        result = approvals.request(
            args.job_id,
            args.action_type,
            args.summary,
            risk_level=args.risk_level,
            parent_approval_id=args.parent_approval_id or "",
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.approvals_action in {"approve", "reject"}:
        if not args.approval_id:
            raise ValueError("approve oder reject braucht eine APPROVAL_ID.")
        child_actions = [
            item.strip() for item in (args.child_action or []) if item.strip()
        ]
        result = approvals.decide(
            args.approval_id,
            args.approvals_action,
            actor=args.actor,
            child_actions=child_actions,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    raise ValueError("Unbekannte Freigabe-Aktion.")


def run_control_plane_command(home, args):
    core_path = str(Path(home) / "core")
    if core_path not in sys.path:
        sys.path.insert(0, core_path)
    from configuration import load_config, save_config  # pylint: disable=import-outside-toplevel
    from control_plane import TrinityControlPlane  # pylint: disable=import-outside-toplevel

    config_path = Path(home) / "core" / "config.json"
    config = load_config(config_path)
    control = config.setdefault("control_plane", {})
    changed = False
    if args.runtime_root:
        control["runtime_root"] = args.runtime_root
        changed = True
    if args.vault_root:
        control["vault_root"] = args.vault_root
        changed = True
    if changed:
        save_config(config_path, config)
        config = load_config(config_path)

    plane = TrinityControlPlane(home, config)
    if args.control_action == "init":
        result = plane.ensure_foundation()
    elif args.control_action == "status":
        result = plane.status()
    elif args.control_action == "catalog":
        result = plane.export_agent_catalog()
    else:
        raise ValueError("Unbekannte Control-Plane-Aktion.")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


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
        choices=("configured", "classic", "eyes", "web", "terminal", "all"),
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
    tui = subparsers.add_parser(
        "tui",
        help="Terminal-Chat mit Slash-Commands, Sessions und Memory",
    )
    tui.add_argument("--session", help="Vorhandene Session-ID fortsetzen")

    doctor = subparsers.add_parser("doctor", help="Installation prüfen")
    doctor.add_argument("--fix", action="store_true", help="Sichere Reparaturen anwenden")
    doctor.add_argument(
        "--online",
        action="store_true",
        help="Zusätzlich origin/main auf Aktualität prüfen",
    )
    bridge = subparsers.add_parser(
        "bridge",
        help="HTTP-Bridge für Companion-Apps starten",
    )
    bridge.add_argument(
        "--host",
        default=None,
        help="Bind-Adresse, z.B. 0.0.0.0 für Tailscale",
    )
    bridge.add_argument("--port", type=int, default=None, help="HTTP-Port")
    bridge.add_argument(
        "--token",
        default=None,
        help="Optionales Bearer-Token für Companion-Clients",
    )
    server = subparsers.add_parser(
        "server",
        help="Headless Trinity-Kern mit browserbasierter WebUI starten",
    )
    server.add_argument("--host", default=None, help="Bind-Adresse, z.B. 0.0.0.0 für Tailscale")
    server.add_argument("--port", type=int, default=None, help="HTTP-Port")
    server.add_argument("--token", default=None, help="Bearer-Token für die WebUI")
    server.add_argument("--auth", action="store_true", help="Passwort-Accounts und getrennte Nutzerbereiche aktivieren")
    client = subparsers.add_parser("client", help="Diese Desktop-Installation mit einem Trinity-Server verbinden")
    client.add_argument("client_action", choices=("login", "status", "logout", "add-user"))
    client.add_argument("--url", help="URL des Trinity-Servers, z.B. http://100.x.y.z:8765")
    client.add_argument("--username", help="Benutzername für login")
    client.add_argument("--role", choices=("user", "admin"), default="user", help="Rolle bei add-user")

    skills = subparsers.add_parser("skills", help="Shared-, Personal- und Staging-Skills verwalten")
    skills.add_argument("skills_action", choices=("list", "reload", "promote"))
    skills.add_argument("skill_id", nargs="?", help="Skill-ID bei promote")
    skills.add_argument("--tier", choices=("shared", "personal", "staging"))
    skills.add_argument("--approval-id", default="", help="Einmalige Freigabe-ID bei promote")

    jobs = subparsers.add_parser("jobs", help="Geplante und laufende Trinity-Jobs anzeigen")
    jobs.add_argument("jobs_action", choices=("list", "show", "cancel"))
    jobs.add_argument("job_id", nargs="?", help="Job-ID bei show oder cancel")
    jobs.add_argument("--status", default="", help="Nach Status filtern")
    jobs.add_argument("--limit", type=int, default=50)

    approvals = subparsers.add_parser("approvals", help="Lokale Freigaben verwalten")
    approvals.add_argument("approvals_action", choices=("list", "request", "approve", "reject"))
    approvals.add_argument("approval_id", nargs="?", help="Freigabe-ID bei approve oder reject")
    approvals.add_argument("--job-id", default="", help="Zugehoeriger Job")
    approvals.add_argument("--action-type", default="", help="Aktion bei request")
    approvals.add_argument("--summary", default="", help="Zusammenfassung bei request")
    approvals.add_argument("--risk-level", default="medium")
    approvals.add_argument("--parent-approval-id", default="")
    approvals.add_argument("--child-action", action="append", default=[])
    approvals.add_argument("--actor", default="local-user")

    control = subparsers.add_parser(
        "control-plane",
        help="Harness-agnostische Control Plane und MainHub/Vault verwalten",
    )
    control.add_argument("control_action", choices=("init", "status", "catalog"))
    control.add_argument("--runtime-root", default="", help="Lokaler TrinityRuntime-Pfad")
    control.add_argument("--vault-root", default="", help="Synchronisierter TrinityVault-Pfad")
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
        if args.command == "tui":
            return run_tui_command(home, args)
        if args.command == "doctor":
            return run_doctor_command(home, args)
        if args.command == "bridge":
            return run_bridge_command(home, args)
        if args.command == "server":
            return run_server_command(home, args)
        if args.command == "client":
            return run_client_command(home, args)
        if args.command == "skills":
            return run_skills_command(home, args)
        if args.command == "jobs":
            return run_jobs_command(home, args)
        if args.command == "approvals":
            return run_approvals_command(home, args)
        if args.command == "control-plane":
            return run_control_plane_command(home, args)
    except (OSError, ValueError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
