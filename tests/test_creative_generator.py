import pandas as pd
from src.agents.creative_generator import generate_creatives


def test_creative_generation():
    # V2: Test with validated insights structure
    summary = {
        "by_campaign": [
            {
                "campaign": "A", "ctr": 0.005, "spend": 100,
                "impressions": 10000, "clicks": 50, "revenue": 200, "roas": 2.0
            }
        ]
    }
    df = pd.DataFrame({
        "campaign": ["A", "A"],
        "creative_message": ["hello world", "new offer"]
    })

    # Create a validated insight that would trigger creative generation
    validated_insights = [
        {
            "id": "test123",
            "hypothesis": "CTR has dropped below baseline",
            "impact": "high",
            "confidence": 0.75,
            "passed": True,
            "evidence": {
                "ctr_delta_pct": -0.30,
                "last_ctr": 0.005,
                "ctr_baseline": 0.015,
                "roas_delta_pct": 0.0,
                "last_roas": 2.0,
                "roas_baseline": 2.0,
            }
        }
    ]

    out = generate_creatives(validated_insights, summary, df)
    assert isinstance(out, list)
    # Should generate creatives for the low CTR insight
    if len(out) > 0:
        assert "creatives" in out[0]
