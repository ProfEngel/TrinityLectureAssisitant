import json
import time

from voice.input_selection import AudioInputSelection
from voice.textedit_lease import TextEditVoiceLease


def test_g2_temporarily_overrides_input_without_changing_output(tmp_path):
    config_path = tmp_path / "core" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text(json.dumps({"system": {"speech_output": {
        "kind": "companion", "device_id": "companion:ipad", "label": "iPad", "updated_at": 1.0,
    }}}))
    selection = AudioInputSelection(config_path, tmp_path / "voice" / "input_lease.json")
    mac = {"kind": "desktop", "device_id": "desktop:mac", "label": "Mac"}
    g2 = {"kind": "g2", "device_id": "g2:glasses", "label": "G2"}

    assert selection.update({**mac, "action": "claim"})["device_id"] == "desktop:mac"
    assert selection.update({**g2, "action": "claim"})["device_id"] == "g2:glasses"
    assert selection.update({**g2, "action": "heartbeat"})["device_id"] == "g2:glasses"
    assert json.loads(config_path.read_text())["system"]["speech_output"]["device_id"] == "companion:ipad"
    assert selection.update({**g2, "action": "release"})["device_id"] == "desktop:mac"


def test_g2_expiry_restores_last_device_even_if_offline(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"system": {"audio_input": {
        "kind": "companion", "device_id": "companion:iphone", "label": "iPhone", "updated_at": 1.0,
    }}}))
    lease_path = tmp_path / "input_lease.json"
    selection = AudioInputSelection(config_path, lease_path)
    selection.update({"kind": "g2", "device_id": "g2:glasses", "action": "claim"})
    lease = json.loads(lease_path.read_text())
    lease["expires_at"] = time.time() - 1
    lease_path.write_text(json.dumps(lease))

    assert selection.current()["device_id"] == "companion:iphone"
    assert selection.current()["temporary"] is False


def test_other_device_cannot_release_active_g2(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{}")
    selection = AudioInputSelection(config_path, tmp_path / "lease.json")
    selection.update({"kind": "g2", "device_id": "g2:one", "action": "claim"})

    assert selection.update({"kind": "g2", "device_id": "g2:other", "action": "release"})["device_id"] == "g2:one"


def test_writing_lease_requires_active_allowed_mac_and_expires(tmp_path, monkeypatch):
    import pytest
    import voice.textedit_lease as lease_module
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"system": {"textedit_voice_device_id": "desktop:mac"}}))
    selection = AudioInputSelection(path, tmp_path / "input_lease.json")
    mac = {"kind": "desktop", "device_id": "desktop:mac"}
    selected = selection.update({**mac, "action": "claim"})
    assert selection.update({**mac, "action": "textedit_state", "dictating": True})["dictating"]
    lease = TextEditVoiceLease(tmp_path / "textedit_lease.json")
    assert lease.active(selected)
    with pytest.raises(PermissionError):
        selection.update({"kind": "desktop", "device_id": "desktop:other",
                          "action": "textedit_state", "dictating": True})
    now = time.time()
    monkeypatch.setattr(lease_module.time, "time", lambda: now + 16)
    assert not lease.active(selected)
