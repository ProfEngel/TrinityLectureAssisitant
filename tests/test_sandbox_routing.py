import pytest
from agents.sandbox_agent.script import can_handle


@pytest.mark.parametrize("query", [
    "Erkläre den Unterschied zwischen Korrelation und Kausalität.",
    "Trinity, was ist Regression?", "Erkläre Machine Learning am Beispiel.",
    "Was bedeutet eine Korrelation von 0,8?", "Zeig mir, wie man darüber nachdenkt.",
    "Was ist Python?", "Kannst du mir den Mittelwert erklären?",
    "Was bedeutet: Berechne die Korrelation?", "Analysiere meine Gedanken dazu.",
])
def test_concepts_do_not_launch_code(query):
    assert not can_handle(query)


@pytest.mark.parametrize("query", [
    "Berechne die Korrelation für diese Werte: X 1 2 3 und Y 2 4 6.",
    "Analysiere diesen CSV Datensatz", "Trainiere ein Modell auf diesen Daten",
    "Erstelle Python Code für eine Regression", "Zeige mir Python Code zur Korrelation",
])
def test_explicit_execution_intent(query):
    assert can_handle(query)
