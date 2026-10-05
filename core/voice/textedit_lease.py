"""Only a confirmed, live Mac editor may suppress conversational answers."""
import json
import os
import time
import uuid
from pathlib import Path

TTL_SECONDS = 15


class TextEditVoiceLease:
    def __init__(self, path):
        self.path = Path(path)

    def update(self, device_id, active, input_epoch):
        value = {"device_id": device_id, "active": bool(active),
                 "input_epoch": input_epoch, "expires_at": time.time() + TTL_SECONDS}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + "." + uuid.uuid4().hex)
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle)
        os.replace(temporary, self.path)
        return {"ok": True, "dictating": bool(active)}

    def active(self, selection):
        try:
            value = json.loads(self.path.read_text())
            return bool(value.get("active") and value.get("device_id") == selection.get("device_id")
                        and value.get("input_epoch") == selection.get("updated_at")
                        and value.get("expires_at", 0) > time.time())
        except (OSError, ValueError, TypeError):
            return False
