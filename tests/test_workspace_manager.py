from pathlib import Path

from workspace_manager import INBOX_WORKSPACE_ID, TrinityWorkspaceManager


def _config(runtime_root):
    return {
        "control_plane": {
            "runtime_root": str(runtime_root),
            "vault_root": str(runtime_root.parent / "BrainVault"),
        }
    }


def test_workspace_manager_creates_inbox_in_runtime(tmp_path):
    home = tmp_path / "Trinity"
    (home / "core").mkdir(parents=True)
    runtime = tmp_path / "Runtime"

    manager = TrinityWorkspaceManager(home, _config(runtime))
    layout = manager.ensure_layout()
    workspaces = manager.list_workspaces()

    assert layout["workspaces_root"] == str(runtime / "workspaces")
    assert workspaces[0].id == INBOX_WORKSPACE_ID
    assert workspaces[0].title == "Schnellsessions"
    assert (runtime / "workspaces" / INBOX_WORKSPACE_ID / "workspace.json").is_file()
    assert (runtime / "workspaces" / INBOX_WORKSPACE_ID / "notes").is_dir()


def test_workspace_session_lifecycle_and_move(tmp_path):
    home = tmp_path / "Trinity"
    (home / "core").mkdir(parents=True)
    runtime = tmp_path / "Runtime"
    manager = TrinityWorkspaceManager(home, _config(runtime))

    workspace = manager.create_workspace("Erendria", kind="writing", pinned=True)
    session = manager.create_session("20260701_1430_Kapitel3", mode="office")

    assert session.workspace_id == INBOX_WORKSPACE_ID
    assert Path(session.path / "session.json").is_file()
    assert Path(session.path / "events.jsonl").is_file()
    assert Path(session.path / "transcript.md").is_file()

    moved = manager.move_session(session.id, workspace.id)

    assert moved.workspace_id == workspace.id
    assert moved.path.parent == workspace.path / "sessions"
    assert manager.list_sessions(workspace.id)[0].id == session.id
    assert manager.list_sessions(INBOX_WORKSPACE_ID) == []

    queued = manager.update_session_summary_status(session.id, "queued")
    assert queued.summary_status == "queued"

    pinned_session = manager.update_session_pinned(session.id, True)
    pinned_workspace = manager.update_workspace_pinned(workspace.id, True)
    assert pinned_session.pinned is True
    assert pinned_workspace.pinned is True

    deleted = manager.delete_session(session.id)
    assert deleted["deleted"] is True
    assert manager.list_sessions(workspace.id) == []


def test_workspace_and_session_updates_are_persistent(tmp_path):
    home = tmp_path / "Trinity"
    (home / "core").mkdir(parents=True)
    runtime = tmp_path / "Runtime"
    manager = TrinityWorkspaceManager(home, _config(runtime))

    workspace = manager.create_workspace("Roman", kind="writing")
    updated_workspace = manager.update_workspace(workspace.id, title="Erendria", pinned=True)
    session = manager.create_session("Alt", workspace_id=INBOX_WORKSPACE_ID)
    updated_session = manager.update_session(
        session.id,
        title="Kapitel 3",
        workspace_id=workspace.id,
        pinned=True,
        status="active",
        summary_status="queued",
        mode="office",
    )

    assert updated_workspace.title == "Erendria"
    assert updated_workspace.pinned is True
    assert updated_session.title == "Kapitel 3"
    assert updated_session.workspace_id == workspace.id
    assert updated_session.pinned is True
    assert updated_session.status == "active"
    assert updated_session.summary_status == "queued"
    assert manager.list_sessions(workspace.id)[0].id == session.id
    assert manager.list_sessions(INBOX_WORKSPACE_ID) == []


def test_workspace_session_delete_can_archive(tmp_path):
    home = tmp_path / "Trinity"
    (home / "core").mkdir(parents=True)
    runtime = tmp_path / "Runtime"
    manager = TrinityWorkspaceManager(home, _config(runtime))

    session = manager.create_session("20260702_0815_Test")
    result = manager.delete_session(session.id, archive=True)

    assert result["archived"] is True
    assert not session.path.exists()
    assert (runtime / "archive" / "sessions" / session.id / "session.json").is_file()


def test_workspace_manager_closes_session_without_removing_contents(tmp_path):
    home = tmp_path / "Trinity"
    (home / "core").mkdir(parents=True)
    runtime = tmp_path / "Runtime"
    manager = TrinityWorkspaceManager(home, _config(runtime))
    session = manager.create_session("Vorlesung")
    medium = session.path / "media" / "diagramm.png"
    medium.write_bytes(b"png")

    closed = manager.close_session(session.id)

    assert closed.status == "closed"
    assert closed.summary_status == "queued"
    assert medium.read_bytes() == b"png"


def test_workspace_ids_are_unique(tmp_path):
    home = tmp_path / "Trinity"
    (home / "core").mkdir(parents=True)
    runtime = tmp_path / "Runtime"
    manager = TrinityWorkspaceManager(home, _config(runtime))

    first = manager.create_workspace("Agentenbau")
    second = manager.create_workspace("Agentenbau")

    assert first.id == "agentenbau"
    assert second.id == "agentenbau-2"


def test_workspace_notes_are_created_per_workspace(tmp_path):
    home = tmp_path / "Trinity"
    (home / "core").mkdir(parents=True)
    runtime = tmp_path / "Runtime"
    manager = TrinityWorkspaceManager(home, _config(runtime))

    workspace = manager.create_workspace("Vorlesung Winf")
    note = manager.create_note(workspace.id, "Tafelbild 1", "Erste Idee")
    notes = manager.list_notes(workspace.id)

    assert (workspace.path / "notes").is_dir()
    assert note.workspace_id == workspace.id
    assert note.path.read_text(encoding="utf-8").startswith("# Tafelbild 1")
    assert notes[0].id == note.id
