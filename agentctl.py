"""Small CLI for BrainVault agent libraries."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _load_core():
    core_dir = _repo_root() / "core"
    if str(core_dir) not in sys.path:
        sys.path.insert(0, str(core_dir))
    from brainvault_agents import (  # pylint: disable=import-outside-toplevel
        audit_candidates,
        brainvault_root_from_config,
        build_catalog,
        create_agent,
        ensure_brainvault_layout,
        inspect_agent,
        import_agent_directory,
        list_agents,
        register_external_agent,
        validate_agent,
    )
    from configuration import load_config  # pylint: disable=import-outside-toplevel

    return {
        "audit_candidates": audit_candidates,
        "brainvault_root_from_config": brainvault_root_from_config,
        "build_catalog": build_catalog,
        "create_agent": create_agent,
        "ensure_brainvault_layout": ensure_brainvault_layout,
        "inspect_agent": inspect_agent,
        "import_agent_directory": import_agent_directory,
        "list_agents": list_agents,
        "load_config": load_config,
        "register_external_agent": register_external_agent,
        "validate_agent": validate_agent,
    }


def _config(home: Path) -> dict:
    core = _load_core()
    return core["load_config"](home / "core" / "config.json")


def _vault_root(args) -> Path:
    home = Path(args.home or os.environ.get("TRINITY_HOME") or _repo_root()).expanduser().resolve()
    if args.vault_root:
        return Path(args.vault_root).expanduser().resolve()
    core = _load_core()
    return core["brainvault_root_from_config"](home, _config(home))


def cmd_init(args) -> int:
    core = _load_core()
    result = core["ensure_brainvault_layout"](_vault_root(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_list(args) -> int:
    core = _load_core()
    agents = core["list_agents"](_vault_root(args))
    if args.json:
        print(json.dumps(agents, ensure_ascii=False, indent=2))
        return 0
    if not agents:
        print("Keine BrainVault-Agenten gefunden.")
        return 0
    for agent in agents:
        enabled = "enabled" if agent.get("enabled") else "disabled"
        print(f"{agent.get('id')} [{agent.get('status')}/{enabled}] {agent.get('path')}")
    return 0


def cmd_inspect(args) -> int:
    core = _load_core()
    agent = core["inspect_agent"](_vault_root(args), args.agent_id)
    if not agent:
        print(f"Agent nicht gefunden: {args.agent_id}", file=sys.stderr)
        return 2
    print(json.dumps(agent, ensure_ascii=False, indent=2))
    return 0


def cmd_validate(args) -> int:
    core = _load_core()
    result = core["validate_agent"](_vault_root(args), args.agent_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def cmd_catalog_build(args) -> int:
    core = _load_core()
    result = core["build_catalog"](_vault_root(args))
    print(json.dumps({"path": result["path"], "summary": result["summary"]}, ensure_ascii=False, indent=2))
    return 0


def cmd_create(args) -> int:
    core = _load_core()
    result = core["create_agent"](
        _vault_root(args),
        args.area,
        args.agent_id,
        name=args.name,
        description=args.description or "",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_import(args) -> int:
    core = _load_core()
    result = core["import_agent_directory"](
        _vault_root(args),
        args.source_path,
        area=args.area,
        preferred_harness=args.preferred_harness,
        status=args.status,
        enabled=not args.disabled,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_register(args) -> int:
    core = _load_core()
    result = core["register_external_agent"](
        _vault_root(args),
        args.source_path,
        area=args.area,
        agent_id=args.agent_id,
        name=args.name,
        description=args.description,
        preferred_harness=args.preferred_harness,
        status=args.status,
        enabled=not args.disabled,
        kind=args.kind,
        workspace=args.workspace,
        entrypoint=args.entrypoint,
        parent_agent=args.parent_agent,
        tags=[item.strip() for item in args.tags.split(",") if item.strip()],
        copy_source=args.copy_source,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_audit(args) -> int:
    core = _load_core()
    root = _vault_root(args)
    output = Path(args.output or root / "BRAINVAULT_AGENT_AUDIT.md")
    result = core["audit_candidates"](args.roots, output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentctl")
    parser.add_argument("--home", default="", help="Trinity home; default: current package or TRINITY_HOME")
    parser.add_argument("--vault-root", default="", help="BrainVault root; overrides config")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create BrainVault technical layout")
    init.set_defaults(func=cmd_init)

    list_cmd = sub.add_parser("list", help="List BrainVault agents")
    list_cmd.add_argument("--json", action="store_true")
    list_cmd.set_defaults(func=cmd_list)

    inspect = sub.add_parser("inspect", help="Inspect one BrainVault agent")
    inspect.add_argument("agent_id")
    inspect.set_defaults(func=cmd_inspect)

    validate = sub.add_parser("validate", help="Validate one BrainVault agent")
    validate.add_argument("agent_id")
    validate.set_defaults(func=cmd_validate)

    catalog = sub.add_parser("catalog", help="Catalog operations")
    catalog_sub = catalog.add_subparsers(dest="catalog_command", required=True)
    catalog_build = catalog_sub.add_parser("build", help="Rebuild BrainVault catalog")
    catalog_build.set_defaults(func=cmd_catalog_build)

    create = sub.add_parser("create", help="Create a draft BrainVault agent")
    create.add_argument("area")
    create.add_argument("agent_id")
    create.add_argument("--name", default="")
    create.add_argument("--description", default="")
    create.set_defaults(func=cmd_create)

    import_cmd = sub.add_parser("import", help="Import an existing agent folder into BrainVault/.agents")
    import_cmd.add_argument("source_path")
    import_cmd.add_argument("--area", default="skills")
    import_cmd.add_argument("--preferred-harness", default="codex")
    import_cmd.add_argument("--status", default="active", choices=["draft", "active", "disabled", "archived"])
    import_cmd.add_argument("--disabled", action="store_true")
    import_cmd.set_defaults(func=cmd_import)

    register = sub.add_parser("register", help="Register an external file or project as a BrainVault agent")
    register.add_argument("source_path")
    register.add_argument("--area", default="external")
    register.add_argument("--agent-id", default="")
    register.add_argument("--name", default="")
    register.add_argument("--description", default="")
    register.add_argument("--preferred-harness", default="codex")
    register.add_argument("--status", default="active", choices=["draft", "active", "disabled", "archived"])
    register.add_argument("--disabled", action="store_true")
    register.add_argument("--kind", default="project")
    register.add_argument("--workspace", default="")
    register.add_argument("--entrypoint", default="")
    register.add_argument("--parent-agent", default="")
    register.add_argument("--tags", default="")
    register.add_argument("--copy-source", action="store_true")
    register.set_defaults(func=cmd_register)

    audit = sub.add_parser("audit", help="Audit existing folders for agent candidates")
    audit.add_argument("roots", nargs="+")
    audit.add_argument("--output", default="")
    audit.set_defaults(func=cmd_audit)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
