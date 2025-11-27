from src.agents.data_agent import load_data, summarize

def test_summary_keys():
    df = load_data("data/sample_fb_ads.csv")
    s = summarize(df)
    assert "global" in s and "by_campaign" in s
