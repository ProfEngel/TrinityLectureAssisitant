import chat_protocol
from chat_protocol import (
    append_chat_event,
    build_chat_request,
    encode_chat_request,
    enqueue_chat_request,
    load_chat_events,
    parse_command,
    pop_next_chat_request,
    remove_chat_event,
)


def test_structured_chat_request_round_trip():
    request = build_chat_request(
        "Fasse die Anlage zusammen.",
        [{"name": "text.txt", "path": "/tmp/text.txt", "kind": "text"}],
        history_recorded=True,
    )

    parsed = parse_command(encode_chat_request(request))

    assert parsed["text"] == "Fasse die Anlage zusammen."
    assert parsed["attachments"][0]["name"] == "text.txt"
    assert parsed["history_recorded"] is True


def test_legacy_silent_command_stays_supported():
    parsed = parse_command("SILENT:Hallo Trinity")

    assert parsed["text"] == "Hallo Trinity"
    assert parsed["silent"] is True
    assert parsed["source"] == "legacy"


def test_chat_request_queue_preserves_multiple_requests(tmp_path):
    first = build_chat_request("Erste Nachricht")
    second = build_chat_request("Zweite Nachricht")

    enqueue_chat_request(tmp_path, first)
    enqueue_chat_request(tmp_path, second)

    assert pop_next_chat_request(tmp_path)["text"] == "Erste Nachricht"
    assert pop_next_chat_request(tmp_path)["text"] == "Zweite Nachricht"
    assert pop_next_chat_request(tmp_path) is None


def test_chat_request_queue_keeps_fifo_when_clock_values_are_identical(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(chat_protocol.time, "time_ns", lambda: 42)
    monkeypatch.setattr(chat_protocol, "_last_queue_timestamp", 0)

    enqueue_chat_request(tmp_path, build_chat_request("Erste Nachricht"))
    enqueue_chat_request(tmp_path, build_chat_request("Zweite Nachricht"))

    assert pop_next_chat_request(tmp_path)["text"] == "Erste Nachricht"
    assert pop_next_chat_request(tmp_path)["text"] == "Zweite Nachricht"


def test_chat_history_uses_json_lines(tmp_path):
    path = tmp_path / "history.jsonl"
    append_chat_event(path, {"role": "user", "text": "Hallo"})
    append_chat_event(path, {"role": "assistant", "text": "Hallo zurück"})

    events = load_chat_events(path)

    assert [event["role"] for event in events] == ["user", "assistant"]
    assert events[-1]["text"] == "Hallo zurück"


def test_chat_history_can_remove_single_event(tmp_path):
    path = tmp_path / "history.jsonl"
    first = append_chat_event(path, {"role": "user", "text": "Bleibt"})
    second = append_chat_event(path, {"role": "assistant", "text": "Weg"})

    assert remove_chat_event(path, second["event_id"]) is True

    events = load_chat_events(path)
    assert [event["event_id"] for event in events] == [first["event_id"]]
    assert remove_chat_event(path, "missing") is False
