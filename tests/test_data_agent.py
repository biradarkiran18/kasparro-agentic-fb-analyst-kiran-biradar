import pandas as pd
from src.agents.data_agent import load_data, summarize


def test_load_and_summarize(tmp_path):
    # create minimal csv
    p = tmp_path / "sample.csv"
    df = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-01", "2025-01-02"]),
        "campaign_name": ["A", "A"],
        "spend": [10, 20],
        "impressions": [100, 200],
        "clicks": [1, 2],
        "revenue": [50, 100],
        "creative_message": ["msg1", "msg2"]
    })
    df.to_csv(p, index=False)
    d = load_data(str(p), sample_mode=False)
    assert len(d) == 2
    s = summarize(d)
    assert "global" in s
    assert isinstance(s["by_campaign"], list)
