from chat_protocol import (
    append_chat_event,
    build_chat_request,
    encode_chat_request,
    load_chat_events,
    parse_command,
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


def test_chat_history_uses_json_lines(tmp_path):
    path = tmp_path / "history.jsonl"
    append_chat_event(path, {"role": "user", "text": "Hallo"})
    append_chat_event(path, {"role": "assistant", "text": "Hallo zurück"})

    events = load_chat_events(path)

    assert [event["role"] for event in events] == ["user", "assistant"]
    assert events[-1]["text"] == "Hallo zurück"
