from src.agents.evaluator import validate


def test_validate_empty_hypotheses():
    validated, metrics = validate([], {}, {"confidence_min": 0.5})
    assert metrics["num_hypotheses"] == 0
    assert isinstance(validated, list)


def test_validate_missing_fields():
    hyps = [{"id": None, "hypothesis": "", "initial_confidence": "not-a-number"}]
    validated, metrics = validate(hyps, {}, {"confidence_min": 0.3})
    assert metrics["num_hypotheses"] == 1
    assert validated[0]["validated"] is False


def test_validate_small_sample_adjustment():
    hyps = [{"id": "H1", "hypothesis": "test roas declined", "initial_confidence": 0.9, "metrics_used": ["ctr"]}]
    summary = {"global": {"total_spend": 5, "daily_roas": []}, "by_campaign": []}
    validated, metrics = validate(hyps, summary, {"confidence_min": 0.5})
    assert metrics["num_hypotheses"] == 1
    assert isinstance(validated, list)
