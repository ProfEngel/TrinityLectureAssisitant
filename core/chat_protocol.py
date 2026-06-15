"""Shared command and history format for Trinity's graphical chat."""

import json
import os
import time
import uuid
from pathlib import Path


def build_chat_request(text, attachments=None, history_recorded=False):
    return {
        "type": "chat_request",
        "request_id": uuid.uuid4().hex,
        "source": "classic",
        "silent": True,
        "text": text.strip(),
        "attachments": list(attachments or []),
        "history_recorded": bool(history_recorded),
    }


def encode_chat_request(request):
    return json.dumps(request, ensure_ascii=False)


def parse_command(raw_command):
    raw = raw_command.strip()
    if raw.startswith("{"):
        try:
            request = json.loads(raw)
            if request.get("type") == "chat_request":
                request.setdefault("request_id", uuid.uuid4().hex)
                request.setdefault("source", "classic")
                request.setdefault("silent", True)
                request.setdefault("attachments", [])
                request["text"] = str(request.get("text", "")).strip()
                return request
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    silent = raw.startswith("SILENT:")
    text = raw[7:] if silent else raw
    return {
        "type": "chat_request",
        "request_id": uuid.uuid4().hex,
        "source": "legacy",
        "silent": silent,
        "text": text.strip(),
        "attachments": [],
        "history_recorded": False,
    }


def append_chat_event(history_path, event):
    path = Path(history_path)
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


def load_chat_events(history_path, limit=200):
    path = Path(history_path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    events = []
    for line in lines[-limit:]:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events
