import json
import time

from memory_store import MemoryStore, render_graph_html


def test_memory_store_remembers_searches_bakes_and_graphs(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    session_id = store.create_session("Test Session")

    store.add_message(session_id, "user", "Bitte merke dir das Projekt Momora.")
    memory_id = store.remember(
        "Momora nutzt eine lokale Memory-Datenbank mit Graphansicht.",
        tags=["momora", "memory"],
        session_id=session_id,
    )

    results = store.search("Graphansicht", limit=3)
    assert results[0]["id"] == memory_id
    assert "momora" in results[0]["tags"]

    bake = store.bake_unbaked()
    assert bake["baked"] == 1
    assert bake["summaries"] == 1

    graph = store.graph_data()
    assert graph["nodes"]
    assert graph["links"]
    assert "Memory-Knoten" in render_graph_html(graph)
    assert "#f8fafc" in render_graph_html(graph, "light")


def test_memory_store_imports_classic_chat_history(tmp_path):
    history = tmp_path / "classic_chat_history.jsonl"
    history.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_id": "one",
                        "request_id": "req",
                        "role": "user",
                        "text": "Merke #Trinity Memory.",
                    }
                ),
                json.dumps(
                    {
                        "event_id": "two",
                        "request_id": "req",
                        "role": "assistant",
                        "text": "Ich habe das notiert.",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    store = MemoryStore(tmp_path / "memory.sqlite3")

    result = store.bake_chat_history(history)

    assert result["imported"] == 2
    assert store.status()["memories"] >= 2


def test_dreaming_decays_old_memory_and_keeps_recent_memory_relevant(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    old_id = store.remember("Altes Detail", tags=["trinity"], weight=0.8)
    recent_id = store.remember("Neues Detail", tags=["trinity"], weight=0.8)
    old_created = time.time() - 90 * 86400
    with store.connect() as db:
        db.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            (old_created, old_created, old_id),
        )

    store.dream_tick()
    memories = {item["id"]: item for item in store.search("", limit=10)}

    assert memories[old_id]["weight"] < memories[recent_id]["weight"]


def test_memory_store_deletes_individual_memory_and_whole_session(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    first_session = store.create_session("Erste Session")
    second_session = store.create_session("Zweite Session")
    first_memory = store.remember("Nur diese Erinnerung", session_id=first_session)
    store.remember("Session-Erinnerung", session_id=first_session)
    store.remember("Bleibt bestehen", session_id=second_session)
    store.add_message(first_session, "user", "Wird entfernt")

    assert store.delete_memory(first_memory) is True
    assert store.delete_memory(first_memory) is False
    result = store.delete_session(first_session)

    assert result == {
        "session_id": first_session,
        "deleted": True,
        "messages": 1,
        "memories": 1,
    }
    assert store.stats()["sessions"] == 1
    assert [item["session_id"] for item in store.list_memories()] == [second_session]


def test_search_finds_older_memory_across_sessions_and_cites_source(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    old_session = store.create_session("Vorlesung Data Science")
    identifier = store.remember(
        "In der Data Science Vorlesung erklärten wir die Konfusionsmatrix anhand einer Tabelle.",
        source="lecture-notes", session_id=old_session,
        metadata={"source_path": "DataScience/Folie-12.pdf"},
    )
    for index in range(230):
        store.remember(f"Unverbundener Testeintrag Nummer {index}", weight=0.95)

    matches = store.search("Welche Tabelle zur Konfusionsmatrix gab es in Data Science?")
    assert matches[0]["id"] == identifier
    context = store.context_for_prompt("Konfusionsmatrix Data Science")
    assert "[M1]" in context
    assert "DataScience/Folie-12.pdf" in context
    assert "Session " + old_session in context


def test_memory_search_filters_time_and_updates_index_after_delete(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    old_id = store.remember("Vorlesung zur Regression im April", source="lecture")
    current_id = store.remember("Vorlesung zur Regression im September", source="lecture")
    with store.connect() as db:
        db.execute("UPDATE memories SET created_at = 1000000 WHERE id = ?", (old_id,))
        db.execute("UPDATE memories SET created_at = 2000000 WHERE id = ?", (current_id,))

    assert [item["id"] for item in store.search("Regression", since=1500000)] == [current_id]
    assert [item["id"] for item in store.search("Regression", until=1500000)] == [old_id]
    assert store.delete_memory(current_id)
    assert store.search("September") == []


def test_baked_original_remains_searchable(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    identifier = store.remember("Die Vorlesung behandelte die ROC-Kurve im Detail.")
    store.bake_unbaked()
    assert identifier in {item["id"] for item in store.search("ROC-Kurve")}


def test_relative_week_query_filters_by_date(tmp_path):
    import time

    store = MemoryStore(tmp_path / "memory.sqlite3")
    older = store.remember("Vorlesung zur Konfusionsmatrix im April")
    newer = store.remember("Vorlesung zur Konfusionsmatrix im Mai")
    with store.connect() as db:
        db.execute("UPDATE memories SET created_at = ? WHERE id = ?", (time.time() - 28 * 86400, older))
        db.execute("UPDATE memories SET created_at = ? WHERE id = ?", (time.time() - 3 * 86400, newer))
    context = store.context_for_prompt("Was war zur Konfusionsmatrix vor vier Wochen?")
    assert "im April" in context
    assert "im Mai" not in context
