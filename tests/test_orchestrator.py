from src.orchestrator.orchestrator import run


def test_orchestrator_executes():
    # V2: orchestrator returns a dict, and needs valid CSV path
    result = run("data/sample_fb_ads.csv")
    assert isinstance(result, dict)
    assert "validated" in result
    assert "creatives" in result
    assert isinstance(result["validated"], list)
    assert isinstance(result["creatives"], list)
