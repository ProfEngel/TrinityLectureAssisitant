"""Import an explicitly selected private MP3 library; never scan extra files.

python tools/import_sound_deck.py --home SERVER_HOME --manifest PRIVATE_JSON
The input JSON is {"sounds": [{"id": "cue", "name": "Cue", "source": "/...mp3", "icon": "waveform"}]}.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    root = args.home / "TrinityRuntime/sounddeck"
    entries = json.loads(args.manifest.read_text(encoding="utf-8"))["sounds"]
    # Validate the complete import before replacing any entry.
    ids, names = set(), set()
    for entry in entries:
        identifier, name = entry["id"], entry["name"]
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", identifier) or identifier in ids or name in names or len(name.split()) != 1:
            raise ValueError("IDs and one-word names must be unique")
        if not Path(entry["source"]).is_file():
            raise FileNotFoundError(entry["source"])
        ids.add(identifier); names.add(name)
    root.mkdir(parents=True, exist_ok=True)
    manifest = []
    for entry in entries:
        source = Path(entry["source"])
        duration = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(source)], text=True).strip())
        if source.stat().st_size > 16 * 1024 * 1024 or not 0 < duration <= 600:
            raise ValueError("Sound exceeds 16 MiB / 10 minutes")
        destination = root / (entry["id"] + ".mp3")
        if source.resolve() != destination.resolve():
            shutil.copyfile(source, destination)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(destination), "-ac", "1", "-ar", "24000",
            "-c:a", "pcm_s16le", str(root / (entry["id"] + ".wav"))], check=True)
        manifest.append({"id": entry["id"], "name": entry["name"], "icon": entry.get("icon", "waveform"),
            "duration": round(duration, 3), "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()})
    staging = root / "manifest.json.tmp"
    staging.write_text(json.dumps({"sounds": manifest}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    staging.replace(root / "manifest.json")
    print(f"Imported {len(manifest)} private deck sounds.")


if __name__ == "__main__":
    main()
