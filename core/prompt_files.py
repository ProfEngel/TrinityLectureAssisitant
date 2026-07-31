"""Safe persistence for Trinity's private Soul and User prompt files."""

from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path


class EmptyPromptError(ValueError):
    """Raised when a UI tries to replace a prompt with blank content."""


def validate_prompt_text(name: str, content: object) -> str:
    text = str(content or "")
    if not text.strip():
        raise EmptyPromptError(
            f"{name} ist leer. Die vorhandene Datei wurde aus Sicherheitsgruenden nicht ersetzt."
        )
    return text


def safe_write_prompt(path: str | Path, content: object, max_bytes: int | None = None) -> Path | None:
    """Atomically write a non-empty prompt and privately back up its predecessor."""

    target = Path(path)
    text = validate_prompt_text(target.name, content)
    if max_bytes is not None and len(text.encode("utf-8")) > max_bytes:
        raise ValueError(f"{target.name} ist zu gross.")

    previous = target.read_text(encoding="utf-8") if target.is_file() else ""
    if previous == text:
        return None

    backup_path = None
    if previous.strip():
        home = target.parent.parent
        backup_dir = home / "TrinityRuntime" / "recovery" / "prompts"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = backup_dir / f"{stamp}_{target.name}"
        shutil.copy2(target, backup_path)

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return backup_path
