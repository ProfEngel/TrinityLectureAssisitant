"""File-backed handoff for live STT chunks from companion clients."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path


def append_external_stt_event(feed_path, event):
    path = Path(feed_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event_id": uuid.uuid4().hex,
        "timestamp": time.time(),
        **event,
    }
    line = json.dumps(record, ensure_ascii=False) + "\n"
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        remaining = memoryview(line.encode("utf-8"))
        while remaining:
            written = os.write(descriptor, remaining)
            remaining = remaining[written:]
    finally:
        os.close(descriptor)
    return record


def pop_external_stt_events(feed_path):
    path = Path(feed_path)
    if not path.exists():
        return []

    processing = path.with_name(f"{path.name}.{uuid.uuid4().hex}.processing")
    try:
        os.replace(path, processing)
    except FileNotFoundError:
        return []

    events = []
    try:
        for line in processing.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    finally:
        processing.unlink(missing_ok=True)
    return events
