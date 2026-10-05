"""Apply the Mac identity allowlist on the server, preserving all other settings.

Run on the Linux server with its Trinity root and the Mac's stable device ID.
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

home = Path(sys.argv[1])
device_id = sys.argv[2]
if not device_id.startswith("desktop:privat:"):
    raise ValueError("Unexpected desktop identity")
path = home / "core" / "config.json"
config = json.loads(path.read_text())
backup = path.with_name("config.json.pre-stability-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
shutil.copy2(path, backup)
config.setdefault("system", {})["textedit_voice_device_id"] = device_id
temp = path.with_suffix(".stability.tmp")
temp.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
temp.chmod(0o600)
temp.replace(path)
print("Mac writing identity updated; configuration backup created")
