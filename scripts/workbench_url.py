#!/usr/bin/env python3
"""Print the local Trinity workbench address selected by the active config."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = PROJECT_ROOT / "core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from configuration import load_config  # noqa: E402


def resolve_workbench_url(config: dict) -> str:
    companion = config.get("companion", {})
    server = config.get("server", {})
    selected = companion if companion.get("enabled") else server
    host = str(selected.get("host") or "127.0.0.1")
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    try:
        port = int(selected.get("port") or 8765)
    except (TypeError, ValueError):
        port = 8765
    return f"http://{host}:{port}"


def main() -> None:
    config = load_config(PROJECT_ROOT / "core" / "config.json")
    print(resolve_workbench_url(config))


if __name__ == "__main__":
    main()
