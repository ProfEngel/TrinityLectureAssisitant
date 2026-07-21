import json

from unified_session import UnifiedSessionStore


def test_active_session_survives_new_store_instances(tmp_path):
    (tmp_path / "core").mkdir()
    config = {
        "system": {"profile": "BIZ", "mode": "office"},
        "control_plane": {"runtime_root": str(tmp_path / "runtime")},
    }
    (tmp_path / "core" / "config.json").write_text(json.dumps(config), encoding="utf-8")

    first = UnifiedSessionStore(tmp_path).current()
    second = UnifiedSessionStore(tmp_path).current()

    assert second.id == first.id
    assert UnifiedSessionStore(tmp_path).as_dict()["profile"] == "BIZ"


def test_client_session_ids_are_only_recorded_as_origin_hints(tmp_path):
    (tmp_path / "core").mkdir()
    store = UnifiedSessionStore(tmp_path)

    request = store.canonicalize(
        {"session_id": "device-only", "session_name": "iPad lokal"},
        source="ios",
    )

    assert request["session_id"] != "device-only"
    assert request["client_session_id"] == "device-only"
    assert request["client_session_name"] == "iPad lokal"
    assert request["profile"] == "PRIVAT"
