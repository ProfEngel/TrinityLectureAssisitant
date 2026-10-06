"""Private, file-backed sound deck shared by Bridge and the voice process.

Media is deliberately outside the source tree, in ignored TrinityRuntime.
Only manifest IDs can address files. Revisions fence stale downloads/acks.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import unicodedata
import uuid
from pathlib import Path


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value).casefold().replace("ß", "ss"))
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in text if not unicodedata.combining(c))).strip()


class SoundDeck:
    def __init__(self, home):
        self.home = Path(home)
        self.root = self.home / "TrinityRuntime" / "sounddeck"

    def catalog(self):
        try:
            entries = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))["sounds"]
        except (OSError, ValueError, KeyError):
            return []
        result, seen = [], set()
        for entry in entries[:64]:
            identifier = str(entry.get("id", ""))
            name = str(entry.get("name", ""))
            if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", identifier) or len(name.split()) != 1 or identifier in seen:
                continue
            if not (self.root / (identifier + ".mp3")).is_file():
                continue
            seen.add(identifier)
            result.append({"id": identifier, "name": name[:32], "icon": str(entry.get("icon") or "waveform")[:60],
                           "duration": min(600, max(0, float(entry.get("duration") or 0))),
                           "url": "/deck/audio/" + identifier,
                           "pcm_url": "/deck/pcm/" + identifier})
        return result

    def media(self, identifier, *, pcm=False):
        if identifier not in {entry["id"] for entry in self.catalog()}:
            raise ValueError("Unbekannter Deck-Klang.")
        path = self.root / (identifier + (".wav" if pcm else ".mp3"))
        # Symlinks outside this private library are never downloadable.
        if not path.is_file() or path.resolve().parent != self.root.resolve():
            raise ValueError("Deck-Audiodatei fehlt.")
        return path

    def output(self):
        try:
            output = json.loads((self.home / "core/config.json").read_text(encoding="utf-8")).get("system", {}).get("speech_output", {})
            return str(output.get("device_id") or "") if output.get("kind") != "none" else ""
        except (OSError, ValueError):
            return ""

    def _connect(self):
        self.root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.root / "control.sqlite3", timeout=3)
        connection.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
        connection.execute("INSERT OR IGNORE INTO state VALUES (1, '{}')")
        connection.commit()
        return connection

    @staticmethod
    def _save(connection, state):
        connection.execute("UPDATE state SET data=? WHERE id=1", (json.dumps(state, ensure_ascii=False),))

    def state(self):
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = json.loads(connection.execute("SELECT data FROM state WHERE id=1").fetchone()[0])
            now = time.time()
            if state.get("active") and (state.get("output_id") != self.output() or now > state.get("deadline", 0)
                                       or now > state.get("lease_until", 0)):
                state.update(active=False, revision=uuid.uuid4().hex, error="Ausgabe gewechselt oder Wiedergabe nicht bestätigt.")
                self._save(connection, state)
            return state

    def toggle(self, identifier, *, stop=False):
        catalog = {entry["id"]: entry for entry in self.catalog()}
        if not stop and identifier not in catalog:
            raise ValueError("Unbekannter Deck-Klang.")
        output = self.output()
        if not stop and not output:
            raise ValueError("Bitte zuerst ein Ausgabegerät auswählen.")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            old = json.loads(connection.execute("SELECT data FROM state WHERE id=1").fetchone()[0])
            active = not stop and not (old.get("active") and old.get("sound_id") == identifier and old.get("output_id") == output)
            now = time.time()
            entry = catalog.get(identifier, {})
            state = {"type": "trinity.deck", "revision": uuid.uuid4().hex, "sound_id": identifier,
                     "name": entry.get("name", ""), "url": entry.get("url", ""), "pcm_url": entry.get("pcm_url", ""),
                     "output_id": output, "active": active, "playing": False, "started_at": now,
                     "deadline": now + entry.get("duration", 600) + 20, "lease_until": now + 15, "error": ""}
            self._save(connection, state)
            return state

    def acknowledge(self, revision, device_id, status):
        if status not in {"playing", "ended", "error"}:
            raise ValueError("Ungültiger Wiedergabestatus.")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = json.loads(connection.execute("SELECT data FROM state WHERE id=1").fetchone()[0])
            if state.get("revision") != revision or state.get("output_id") != device_id or self.output() != device_id:
                return state  # A late completion must not stop the following sound.
            if state.get("active"):
                state.update(playing=status == "playing", active=status == "playing", lease_until=time.time() + 6)
                if status != "playing":
                    state["revision"] = uuid.uuid4().hex
                    state["error"] = "Wiedergabe fehlgeschlagen." if status == "error" else ""
                self._save(connection, state)
            return state

    def command(self, text):
        query = normalize(text)
        # Only a whole, deliberate command: a word in conversation is not a cue.
        deliberate = bool(re.match(r"^(?:trinity|triniti|trindy|trinitys|drinity|spiele|spiel|starte)\s+", query))
        query = re.sub(r"^(?:trinity|triniti|trindy|trinitys|drinity)\s+", "", query)
        if query in {"deck stoppen", "deck stop", "sound stoppen", "klang stoppen"}:
            return ("", True)
        if not deliberate:
            return None
        query = re.sub(r"^(?:spiele|spiel|starte|spiel bitte|spiele bitte)\s+", "", query)
        query = re.sub(r"\s+(?:ab|bitte)$", "", query)
        for entry in self.catalog():
            if query in {normalize(entry["name"]), normalize(entry["id"])}:
                return (entry["id"], False)
        return None

    def execute_voice(self, text):
        command = self.command(text)
        if command is None:
            return False
        self.toggle(command[0], stop=command[1])
        return True
