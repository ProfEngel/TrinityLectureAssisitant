"""Shared command and history format for Trinity's graphical chat."""

import json
import os
import threading
import time
import uuid
from pathlib import Path


_QUEUE_CLOCK_LOCK = threading.Lock()
_last_queue_timestamp = 0


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


def command_queue_dir(core_dir):
    return Path(core_dir) / "cmd_queue"


def enqueue_chat_request(core_dir, request):
    queue_dir = command_queue_dir(core_dir)
    queue_dir.mkdir(parents=True, exist_ok=True)
    request.setdefault("request_id", uuid.uuid4().hex)
    filename = f"{_next_queue_timestamp()}-{request['request_id']}.json"
    destination = queue_dir / filename
    temporary = queue_dir / f"{filename}.tmp"
    temporary.write_text(encode_chat_request(request), encoding="utf-8")
    os.replace(temporary, destination)
    return destination


def _next_queue_timestamp():
    """Return a process-local strictly increasing timestamp for FIFO names."""

    global _last_queue_timestamp
    with _QUEUE_CLOCK_LOCK:
        _last_queue_timestamp = max(time.time_ns(), _last_queue_timestamp + 1)
        return _last_queue_timestamp


def pop_next_chat_request(core_dir):
    queue_dir = command_queue_dir(core_dir)
    if queue_dir.exists():
        for path in sorted(queue_dir.glob("*.json")):
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                path.unlink()
            except OSError:
                pass
            return parse_command(raw)

    legacy_path = Path(core_dir) / "cmd.txt"
    try:
        raw = legacy_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        legacy_path.unlink()
    except OSError:
        pass
    return parse_command(raw)


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


def remove_chat_event(history_path, event_id):
    path = Path(history_path)
    target = str(event_id or "").strip()
    if not target:
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False

    kept = []
    removed = False
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            kept.append(line)
            continue
        if isinstance(event, dict) and str(event.get("event_id") or "") == target:
            removed = True
            continue
        kept.append(line)

    if not removed:
        return False

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")
    os.replace(temporary, path)
    return True
