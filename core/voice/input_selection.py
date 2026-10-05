"""Persistent microphone selection with a short-lived G2 override.

The output speaker is deliberately independent. A G2 lease expires when its
app disappears without sending a release request, restoring the last desktop
or Companion input even if that device is temporarily offline.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from configuration import load_config, save_config
from .textedit_lease import TextEditVoiceLease


G2_LEASE_SECONDS = 12.0


class AudioInputSelection:
    def __init__(self, config_path: str | Path, lease_path: str | Path):
        self.config_path = Path(config_path)
        self.lease_path = Path(lease_path)
        self._lock = threading.Lock()

    @staticmethod
    def _device(payload, *, expected_kind=None):
        if not isinstance(payload, dict):
            raise ValueError("Audio-Eingabe erwartet ein Objekt.")
        kind = str(payload.get("kind") or "").strip().lower()
        device_id = str(payload.get("device_id") or "").strip()[:160]
        if expected_kind and kind != expected_kind:
            raise ValueError("Falscher Gerätetyp für diese Eingabe.")
        if kind not in {"g2", "desktop", "companion"} or not device_id:
            raise ValueError("Audio-Eingabe braucht Gerätetyp und Geräte-ID.")
        return {
            "kind": kind,
            "device_id": device_id,
            "label": str(payload.get("label") or device_id).strip()[:100],
            "updated_at": time.time(),
        }

    def _base(self):
        config = load_config(self.config_path)
        system = config.get("system", {})
        base = system.get("audio_input")
        if isinstance(base, dict) and base.get("device_id"):
            return base
        speaker = system.get("speech_output")
        if isinstance(speaker, dict) and speaker.get("kind") in {"desktop", "companion"}:
            return {key: speaker.get(key) for key in ("kind", "device_id", "label", "updated_at")}
        return {"kind": "none", "device_id": "none", "label": "Kein Mikrofon", "updated_at": 0.0}

    def _save_base(self, base):
        config = load_config(self.config_path)
        config.setdefault("system", {})["audio_input"] = base
        save_config(self.config_path, config)

    def _lease(self):
        try:
            lease = json.loads(self.lease_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(lease, dict) or lease.get("kind") != "g2":
            return None
        if float(lease.get("expires_at") or 0.0) <= time.time():
            return None
        return lease

    def _save_lease(self, lease):
        self.lease_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.lease_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(lease, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.lease_path)

    def current(self):
        lease = self._lease()
        if lease:
            return {"ok": True, **lease, "temporary": True}
        return {"ok": True, **self._base(), "temporary": False}

    def update(self, payload):
        action = str((payload or {}).get("action") or "claim").strip().lower()
        if action == "textedit_state":
            device = self._device(payload, expected_kind="desktop")
            allowed = load_config(self.config_path).get("system", {}).get("textedit_voice_device_id")
            if not allowed or allowed != device["device_id"]:
                raise PermissionError("Dieses Gerät darf kein TextEdit-Diktat bestätigen.")
            selection = self.current()
            active = bool(payload.get("dictating"))
            if active and selection.get("device_id") != device["device_id"]:
                raise PermissionError("Das Mac-Mikrofon ist nicht ausgewählt.")
            return TextEditVoiceLease(self.lease_path.with_name("textedit_lease.json")).update(
                device["device_id"], active, selection.get("updated_at"))
        if action not in {"claim", "heartbeat", "release"}:
            raise ValueError("Unbekannte Audio-Eingabe-Aktion.")
        device = self._device(payload)
        with self._lock:
            if device["kind"] == "g2":
                lease = self._lease()
                if action == "claim":
                    # Freeze the previous input before the override begins.
                    if not lease:
                        self._save_base(self._base())
                    self._save_lease({**device, "expires_at": time.time() + G2_LEASE_SECONDS})
                elif action == "heartbeat":
                    if not lease or lease.get("device_id") != device["device_id"]:
                        raise ValueError("G2-Vorrang abgelaufen; erneut übernehmen.")
                    self._save_lease({**lease, "expires_at": time.time() + G2_LEASE_SECONDS})
                elif lease and lease.get("device_id") == device["device_id"]:
                    self._save_lease({**lease, "expires_at": 0.0})
            elif action == "claim":
                self._save_base(device)
            elif action == "release" and self._base().get("device_id") == device["device_id"]:
                self._save_base({"kind": "none", "device_id": "none", "label": "Kein Mikrofon", "updated_at": time.time()})
            else:
                raise ValueError("Nur die G2 sendet einen Heartbeat.")
            return self.current()
