"""Shared profile guard for Trinity's local RAG index."""

import json
import os
import sys


VALID_PROFILES = {"BIZ", "PRIVAT", "TEST"}


def configured_profile(project_dir=None, platform_name=None):
    """Return the single profile this local, rebuildable index belongs to."""

    if project_dir is None:
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(os.fspath(project_dir), "core", "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            config = json.load(handle)
        profile = str(config.get("system", {}).get("profile") or "").upper()
    except (OSError, ValueError, TypeError):
        profile = ""
    if profile in VALID_PROFILES:
        return profile
    host = platform_name or sys.platform
    return "BIZ" if host == "win32" else "PRIVAT"


def index_profile_is_allowed(meta, active_profile):
    """Reject legacy, unscoped and foreign-profile indexes."""

    index_profile = str((meta or {}).get("profile") or "").strip().upper()
    return index_profile in VALID_PROFILES and index_profile == active_profile
