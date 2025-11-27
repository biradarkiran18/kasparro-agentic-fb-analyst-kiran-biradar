from src.orchestrator.orchestrator import run


def test_orchestrator_executes():
    insights, creatives = run("test query")
    assert isinstance(insights, list)
