import pandas as pd

def load_data(path: str):
    df = pd.read_csv(path, parse_dates=["date"])
    if "roas" not in df.columns:
        df["roas"] = df["revenue"] / df["spend"].replace(0, 1)
    return df

def summarize(df: pd.DataFrame):
    df["roas"] = df["revenue"] / df["spend"].replace(0,1)

    global_summary = {
        "start_date": str(df["date"].min()),
        "end_date": str(df["date"].max()),
        "total_spend": float(df["spend"].sum()),
        "total_revenue": float(df["revenue"].sum()),
        "daily_roas": df.groupby("date")["roas"].mean().reset_index().to_dict("records")
    }

    by_campaign = df.groupby("campaign_name").agg({
        "spend":"sum",
        "impressions":"sum",
        "clicks":"sum",
        "purchases":"sum",
        "revenue":"sum"
    }).reset_index()

    by_campaign["ctr"] = by_campaign["clicks"] / by_campaign["impressions"].replace(0,1)
    by_campaign["roas"] = by_campaign["revenue"] / by_campaign["spend"].replace(0,1)

    return {
        "global": global_summary,
        "by_campaign": by_campaign.to_dict("records")
    }
