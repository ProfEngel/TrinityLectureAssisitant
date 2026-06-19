from workspace_context import (
    clear_workspace_attachment,
    load_workspace_attachment,
    save_workspace_attachment,
)


def test_workspace_context_only_returns_existing_files(tmp_path):
    core = tmp_path / "core"
    core.mkdir()
    document = tmp_path / "notes.txt"
    document.write_text("Inhalt", encoding="utf-8")
    attachment = {"name": "notes.txt", "path": str(document), "kind": "text"}

    save_workspace_attachment(core, attachment)

    assert load_workspace_attachment(core) == attachment
    clear_workspace_attachment(core, document)
    assert load_workspace_attachment(core) is None
