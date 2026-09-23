from agents.websearch_agent import script as websearch


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
