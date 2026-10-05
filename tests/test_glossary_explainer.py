from glossary_explainer import explain_lecture_term


def test_glossary_returns_only_term_actually_spoken(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"term":"Nash-Gleichgewicht","definition":"Niemand gewinnt durch einseitigen Wechsel."}'}}]}

    monkeypatch.setattr("glossary_explainer.requests.post", lambda *args, **kwargs: Response())
    config = {"llm": {"active_slot": "local", "local": {"url": "http://localhost/v1/chat/completions", "model": "Gemma"}}}
    result = explain_lecture_term("Das Nash-Gleichgewicht sehen wir nun.", config)
    assert result["term"] == "Nash-Gleichgewicht"
    assert explain_lecture_term("Eine andere lange Aussage ohne diesen Begriff.", config)["term"] == ""
