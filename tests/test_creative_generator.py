import pandas as pd
from src.agents.creative_generator import find_low_ctr, generate_creatives


def test_creative_generation():
    summary = {"by_campaign": [{"campaign_name": "A", "ctr": 0.005, "spend": 100}]}
    df = pd.DataFrame(
        {"campaign_name": ["A", "A"], "creative_message": ["hello world", "new offer"]}
    )
    out = generate_creatives(find_low_ctr(summary), df)
    assert isinstance(out, list)
