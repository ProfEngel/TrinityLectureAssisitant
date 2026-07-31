import pytest

from prompt_files import EmptyPromptError, safe_write_prompt


def test_blank_prompt_cannot_replace_existing_private_prompt(tmp_path):
    target = tmp_path / "core" / "Soul.md"
    target.parent.mkdir()
    target.write_text("Trinity bleibt", encoding="utf-8")

    with pytest.raises(EmptyPromptError):
        safe_write_prompt(target, "  \n")

    assert target.read_text(encoding="utf-8") == "Trinity bleibt"


def test_prompt_update_is_atomic_and_creates_private_recovery_copy(tmp_path):
    target = tmp_path / "core" / "User.md"
    target.parent.mkdir()
    target.write_text("Vorher", encoding="utf-8")

    backup = safe_write_prompt(target, "Nachher")

    assert target.read_text(encoding="utf-8") == "Nachher"
    assert backup is not None
    assert backup.read_text(encoding="utf-8") == "Vorher"
    assert backup.parent == tmp_path / "TrinityRuntime" / "recovery" / "prompts"
