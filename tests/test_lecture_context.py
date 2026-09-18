import base64
import json

import pytest

from core.lecture_context import LectureContextStore, add_current_slide
from unified_session import UnifiedSessionStore


def payload(sequence=1, **changes):
    return {"client_id": "test-ipad", "sequence": sequence, "active": True,
            "title": "Testvortrag", "page": 4, "text": "Umsatz: 120 Euro",
            "image_base64": base64.b64encode(b"\xff\xd8\xfftest").decode(), **changes}


def test_slide_is_scoped_to_profile_session_and_expires(tmp_path, monkeypatch):
    store = LectureContextStore(tmp_path)
    store.update(payload(), profile="TEST", session_id="one")
    assert store.current(profile="TEST", session_id="one")["page"] == 4
    assert store.current(profile="BIZ", session_id="one") is None
    assert store.current(profile="TEST", session_id="two") is None
    stamp = store._read()["updated_at"]
    monkeypatch.setattr("core.lecture_context.time.time", lambda: stamp + 91)
    assert store.current(profile="TEST", session_id="one") is None


def test_slide_respects_existing_configured_runtime_without_rewriting_config(tmp_path):
    runtime = tmp_path / "existing-biz-runtime"
    config = tmp_path / "core" / "config.json"
    config.parent.mkdir()
    original = json.dumps({"system": {"profile": "BIZ"}, "control_plane": {"runtime_root": str(runtime)}})
    config.write_text(original)
    store = LectureContextStore(tmp_path)
    store.update(payload(), profile="BIZ", session_id="one")
    assert store.path == runtime / "lecture" / "current-slide.json"
    assert store.current(profile="BIZ", session_id="one")["page"] == 4
    assert config.read_text() == original


def test_late_upload_cannot_restore_old_slide_or_undo_clear(tmp_path):
    store = LectureContextStore(tmp_path)
    store.update(payload(2, page=5), profile="TEST", session_id="one")
    assert store.update(payload(1), profile="TEST", session_id="one")["ignored"]
    assert store.current(profile="TEST", session_id="one")["page"] == 5
    store.update(payload(3, active=False), profile="TEST", session_id="one")
    store.update(payload(2), profile="TEST", session_id="one")
    assert store.current(profile="TEST", session_id="one") is None
    assert not store._read()["image_base64"]
    assert not store._read()["text"]


def test_other_client_cannot_clear_current_presenter(tmp_path):
    store = LectureContextStore(tmp_path)
    store.update(payload(), profile="TEST", session_id="one")
    assert store.update(payload(100, active=False, client_id="another"),
                        profile="TEST", session_id="one")["ignored"]
    assert store.current(profile="TEST", session_id="one")


@pytest.mark.parametrize(
    "image", ["bad-base64", base64.b64encode(b"not a JPEG").decode(), "x" * 3000000],
    ids=["invalid-base64", "not-jpeg", "oversized-image"],
)
def test_invalid_images_are_rejected(tmp_path, image):
    with pytest.raises(ValueError):
        LectureContextStore(tmp_path).update(payload(image_base64=image), profile="TEST", session_id="one")


def test_slide_image_and_text_reach_multimodal_prompt_without_changing_original_question(tmp_path):
    sessions = UnifiedSessionStore(tmp_path)
    session = sessions.current()
    store = LectureContextStore(tmp_path)
    store.update(payload(), profile=sessions.profile, session_id=session.id)
    content = {"content": "Wie erkläre ich diese Tabelle?", "fallback_text": "Wie erkläre ich diese Tabelle?"}
    assert add_current_slide(content, tmp_path)
    assert content["content"][0]["text"] == "Wie erkläre ich diese Tabelle?"
    assert "Seite 4" in content["content"][1]["text"]
    assert "120 Euro" in content["content"][1]["text"]
    assert content["content"][-1]["type"] == "image_url"
    assert content["content"][-1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert "visuelle Unsicherheit" in content["fallback_text"]
    assert "Bild und Text" in content["lecture_status"]


def test_absent_and_text_only_slide_never_claim_visual_access(tmp_path):
    content = {"content": "Was steht auf der Folie?", "fallback_text": "Frage"}
    assert not add_current_slide(content, tmp_path)
    assert "Behaupte nicht" in content["lecture_status"]
    sessions = UnifiedSessionStore(tmp_path)
    session = sessions.current()
    LectureContextStore(tmp_path).update(payload(image_base64=""), profile=sessions.profile, session_id=session.id)
    assert not add_current_slide(content, tmp_path)
    assert "nur Text" in content["lecture_status"]
    assert not any(p.get("type") == "image_url" for p in content["content"])
