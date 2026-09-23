import json

from core.voice.transport.auth_proxy import AuthenticatedWebSocketProxy


def test_explicit_speaker_claim_selects_one_device(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"system": {"speech_output": {
        "device_id": "companion:iphone",
        "kind": "companion",
        "client_ip": "100.90.5.25",
    }}}))
    proxy = AuthenticatedWebSocketProxy("127.0.0.1", 0, 1, "token", path)
    target = proxy._speaker_target()

    assert proxy._selected_for_client(target, "companion:iphone", "100.90.5.25")
    assert proxy._selected_for_client(target, "", "100.90.5.25")  # older iPhone
    assert not proxy._selected_for_client(target, "desktop:privat:mac", "100.103.186.67")
    assert not proxy._selected_for_client(target, "", "100.103.186.67")


def test_mute_releases_gpu_voice_slot(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"system": {"speech_output": {"device_id": "none", "kind": "none"}}}))
    proxy = AuthenticatedWebSocketProxy("127.0.0.1", 0, 1, "token", path)

    assert not proxy._selected_for_client(proxy._speaker_target(), "companion:iphone", "100.90.5.25")
