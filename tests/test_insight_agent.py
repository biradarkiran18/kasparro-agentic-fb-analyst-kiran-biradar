from src.agents.insight_agent import generate_hypotheses


def test_insights_format():
    summary = {
        "global": {
            "daily_roas": [
                {"date": "2024-01-01", "roas": 1},
                {"date": "2024-01-02", "roas": 0.8},
                {"date": "2024-01-03", "roas": 0.7},
            ]
        },
        "by_campaign": [],
    }
    h = generate_hypotheses(summary)
    assert isinstance(h, list)
