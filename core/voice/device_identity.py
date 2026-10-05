"""A desktop installation's identity must not depend on its network hostname."""
import os
import time
import uuid
from pathlib import Path


def desktop_device_id(home: Path, profile: str) -> str:
    path = Path(home) / "TrinityRuntime" / "desktop_identity"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "w") as handle:
            handle.write(uuid.uuid4().hex)
    # The UI and audio process can start simultaneously; the winner may still
    # be writing the tiny file when the other process first opens it.
    for _ in range(100):
        value = path.read_text().strip()
        if value:
            uuid.UUID(value)  # Corruption is an error, never silently reidentify.
            return f"desktop:{profile.lower()}:{value}"
        time.sleep(0.01)
    raise RuntimeError("Desktop identity file remained empty")
