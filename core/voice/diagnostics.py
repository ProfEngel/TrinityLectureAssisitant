"""Small status events shared with the selected voice clients (no image data)."""
import json
import os
import time
from pathlib import Path


def diagnostic(home, stage, message):
    message = str(message)[:400]
    print(f"Trinity [{stage}]: {message}", flush=True)
    path = Path(home) / "TrinityRuntime/voice/diagnostic_events.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "a") as handle:
            handle.write(json.dumps({"type": "trinity.debug", "at": time.time(),
                                     "stage": stage, "message": message}, ensure_ascii=False) + "\n")
    except OSError:
        pass
