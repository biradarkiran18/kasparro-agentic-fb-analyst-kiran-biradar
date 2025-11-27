from src.agents.evaluator import validate


def test_evaluator_runs():
    hyps = [
        {
            "id": "H1",
            "hypothesis": "Creative fatigue in top spend campaigns",
            "initial_confidence": 0.5,
        }
    ]
    summary = {
        "by_campaign": [{"campaign_name": "x", "spend": 100, "ctr": 0.005}],
        "global": {
            "daily_roas": [
                {"date": 1, "roas": 1},
                {"date": 2, "roas": 0.5},
                {"date": 3, "roas": 0.4},
            ]
        },
    }
    th = {"ctr_low_threshold": 0.01, "roas_drop_threshold": 0.1}
    out = validate(hyps, summary, th)
    assert len(out) == 1
