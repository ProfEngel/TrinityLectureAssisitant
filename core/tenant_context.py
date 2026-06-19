"""Paths for optional multi-user Trinity server operation.

The normal local desktop installation intentionally keeps using the historic
``memory/classic_chat_history.jsonl``.  A tenant id is only present for an
authenticated server request, which makes this additive and backwards
compatible.
"""

from __future__ import annotations

import re
from pathlib import Path


def safe_tenant_id(value):
    """Return a filesystem-safe, stable tenant identifier."""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "")).strip(".-")
    return cleaned[:96]


def tenant_memory_dir(home, tenant_id=""):
    """Return the per-user memory directory or Trinity's historic default."""
    root = Path(home).resolve() / "memory"
    tenant_id = safe_tenant_id(tenant_id)
    return root / "users" / tenant_id if tenant_id else root


def tenant_history_path(home, tenant_id=""):
    return tenant_memory_dir(home, tenant_id) / "classic_chat_history.jsonl"


def tenant_upload_dir(home, tenant_id=""):
    return tenant_memory_dir(home, tenant_id) / "uploads"


def tenant_memory_db_path(home, tenant_id=""):
    return tenant_memory_dir(home, tenant_id) / "trinity_memory.sqlite3"
