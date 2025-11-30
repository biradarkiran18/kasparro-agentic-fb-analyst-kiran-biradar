import pandas as pd
from src.utils.thresholds import compute_dynamic_thresholds


def make_sample_df():
    dates = pd.date_range("2025-01-01", periods=40, freq="D")
    # create trend: impressions constant, clicks ~ binomial so CTR small stable, revenue/spend fluctuates
    data = {
        "date": list(dates),
        "campaign_name": ["A"] * len(dates),
        "impressions": [1000] * len(dates),
        "clicks": [max(1, int(10 + (i % 5) - 2)) for i in range(len(dates))],
        "spend": [100.0 + (i % 7) * 1.0 for i in range(len(dates))],
        "revenue": [300.0 - (i % 6) * 2.0 for i in range(len(dates))],
    }
    return pd.DataFrame(data)


def test_compute_dynamic_thresholds_basic():
    df = make_sample_df()
    t = compute_dynamic_thresholds(df, window_days=30, min_days=7)
    assert "ctr_low_threshold" in t
    assert "roas_drop_threshold" in t
    assert t["rows_used"] > 0
    # thresholds must be numeric and non-negative
    assert isinstance(t["ctr_low_threshold"], float)
    assert isinstance(t["roas_drop_threshold"], float)
    assert t["ctr_low_threshold"] >= 0
    assert t["roas_drop_threshold"] >= 0
