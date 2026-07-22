import json

from configuration import save_config
from memory_store import MemoryStore
from runtime_reset import delete_session_summary, reset_operational_memory
from workspace_manager import TrinityWorkspaceManager


def _installation(tmp_path):
    home = tmp_path / "Trinity"
    runtime = tmp_path / "Runtime"
    vault = tmp_path / "BrainVault"
    canvas = tmp_path / "Canvas"
    (home / "core").mkdir(parents=True)
    vault.mkdir()
    canvas.mkdir()
    config = {
        "system": {"profile": "PRIVAT"},
        "control_plane": {
            "runtime_root": str(runtime),
            "vault_root": str(vault),
        },
        "canvas": {"enabled": True, "install_dir": str(canvas), "port": 8787},
    }
    save_config(home / "core" / "config.json", config)
    (home / "core" / "Soul.md").write_text("Soul bleibt", encoding="utf-8")
    (home / "core" / "User.md").write_text("User bleibt", encoding="utf-8")
    (home / "RAG").mkdir()
    (home / "RAG" / "quelle.md").write_text("RAG bleibt", encoding="utf-8")
    (vault / "projekt.md").write_text("Vault bleibt", encoding="utf-8")
    return home, runtime, vault, canvas, config


def test_operational_reset_is_recoverable_and_preserves_durable_sources(tmp_path, monkeypatch):
    home, runtime, vault, canvas, config = _installation(tmp_path)
    recovery_root = tmp_path / "Recovery"
    monkeypatch.setenv("TRINITY_RECOVERY_ROOT", str(recovery_root))

    manager = TrinityWorkspaceManager(home, config)
    session = manager.create_session("Nur ein Test")
    (session.path / "summary.md").write_text("Testsummary", encoding="utf-8")
    memory = MemoryStore(home / "memory" / "trinity_memory.sqlite3")
    memory.add_message(session.id, "user", "Testnachricht")
    memory.remember("Testmemory", session_id=session.id, kind="session-summary")
    (home / "gen_images").mkdir()
    (home / "gen_images" / "test.png").write_bytes(b"png")
    (runtime / "canvas").mkdir(parents=True)
    (runtime / "canvas" / "trinity-store.json").write_text("{}", encoding="utf-8")
    (canvas / "data").mkdir()
    (canvas / "data" / "legacy.json").write_text("{}", encoding="utf-8")

    result = reset_operational_memory(
        home,
        include_generated=True,
        include_canvas=True,
    )

    backup = recovery_root / next(recovery_root.iterdir()).name
    manifest = json.loads((backup / "RESET_MANIFEST.json").read_text(encoding="utf-8"))
    assert result["backup"] == str(backup)
    assert manifest["before"]["database"]["memories"] == 1
    assert (backup / "memory" / "trinity_memory.sqlite3").is_file()
    assert (backup / "generated_media" / "test.png").is_file()
    assert (backup / "canvas" / "trinity-store.json").is_file()
    assert (backup / "canvas_legacy_data" / "legacy.json").is_file()
    assert MemoryStore(home / "memory" / "trinity_memory.sqlite3").stats()["memories"] == 0
    assert len(TrinityWorkspaceManager(home, config).list_sessions()) == 1
    assert not (home / "gen_images").exists()
    assert not (runtime / "canvas").exists()
    assert not (canvas / "data").exists()
    assert (vault / "projekt.md").read_text(encoding="utf-8") == "Vault bleibt"
    assert (home / "RAG" / "quelle.md").read_text(encoding="utf-8") == "RAG bleibt"
    assert (home / "core" / "Soul.md").read_text(encoding="utf-8") == "Soul bleibt"
    assert (home / "core" / "User.md").read_text(encoding="utf-8") == "User bleibt"


def test_session_summary_can_be_deleted_without_deleting_session(tmp_path):
    home, _runtime, _vault, _canvas, config = _installation(tmp_path)
    manager = TrinityWorkspaceManager(home, config)
    session = manager.create_session("Zusammenfassung")
    manager.update_session_summary_status(session.id, "complete")
    (session.path / "summary.md").write_text("Summary", encoding="utf-8")
    summary_dir = home / "memory" / "summaries"
    summary_dir.mkdir(parents=True)
    (summary_dir / f"Summary_{session.id}.md").write_text("Copy", encoding="utf-8")
    memory = MemoryStore(home / "memory" / "trinity_memory.sqlite3")
    memory.remember("Summary memory", session_id=session.id, kind="session-summary")
    memory.remember("Andere Erinnerung", session_id=session.id, kind="episodic")

    result = delete_session_summary(home, session.id)

    assert len(result["removed_files"]) == 2
    assert result["removed_memories"] == 1
    assert manager.get_session(session.id).summary_status == "none"
    remaining = memory.list_memories()
    assert [item["kind"] for item in remaining] == ["episodic"]
