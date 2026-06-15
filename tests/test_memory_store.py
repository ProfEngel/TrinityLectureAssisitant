import json

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
