"""Persist the file currently open in Trinity's desktop workspace."""

from __future__ import annotations

import json
from pathlib import Path


def load_workspace_attachment(core_dir):
    path = Path(core_dir) / "workspace_attachment.json"
    try:
        item = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(item, dict) or not Path(str(item.get("path", ""))).is_file():
        return None
    return item


def save_workspace_attachment(core_dir, attachment):
    path = Path(core_dir) / "workspace_attachment.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(attachment, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_workspace_attachment(core_dir, expected_path=None):
    path = Path(core_dir) / "workspace_attachment.json"
    if expected_path:
        active = load_workspace_attachment(core_dir)
        if active and str(active.get("path")) != str(expected_path):
            return
    path.unlink(missing_ok=True)
