from agents.websearch_agent import script as websearch


def test_tavily_key_is_sent_only_as_bearer_header(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [{"title": "Quelle", "url": "https://example.org", "content": "Text"}]}

    def post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return Response()

    monkeypatch.setattr("requests.post", post)
    results, error = websearch._search_tavily("aktuelles Thema", "test-secret")
    assert error == ""
    assert len(results) == 1
    assert captured["headers"] == {"Authorization": "Bearer test-secret"}
    assert "api_key" not in captured["json"]


def test_websearch_voice_trigger_and_escaped_result(monkeypatch):
    class Brain:
        tavily_key = "test-secret"

        def ask_llm(self, _messages):
            return "Thema heute"

    monkeypatch.setattr(websearch, "_search_tavily", lambda *_args: ([
        {"title": "<script>bad</script>", "url": "https://example.org", "content": "<b>Text</b>"}
    ], ""))
    assert websearch.can_handle("Trinity, starte die Websuche")
    result = websearch.execute("Trinity, starte die Websuche", {"brain": Brain()})
    assert "https://example.org" in result["search_context"]
    assert "&lt;script&gt;" in result["html_payload"]
    assert "<script>" not in result["html_payload"]


def test_websearch_reports_invalid_provider_credentials(monkeypatch):
    class Brain:
        tavily_key = "configured-but-invalid"

        def ask_llm(self, _messages):
            return "aktuelle Nachrichten"

    monkeypatch.setattr(
        websearch,
        "_search_tavily",
        lambda _query, _key: ([], "Der Tavily-Schlüssel wurde abgelehnt."),
    )

    result = websearch.execute("Trinity, suche aktuelle Nachrichten", {"brain": Brain()})
    assert "abgelehnt" in result["direct_answer"]
    assert not result["has_payload"]
