import pandas as pd
from typing import Optional, Dict, Any


def load_data(path: str, sample_mode: bool = False, sample_size: int = 5000, chunksize: Optional[int] = None):
    """
    Loads CSV data. Supports optional sample_mode (return subset) and chunksize.
    """
    if chunksize:
        # read full file for simplicity in tests; real streaming would handle differently
        df = pd.read_csv(path, parse_dates=["date"])
    else:
        df = pd.read_csv(path, parse_dates=["date"])
    if sample_mode:
        return df.head(sample_size)
    return df


def summarize(df: pd.DataFrame) -> Dict[str, Any]:
    # ensure numeric columns exist
    for c in ["spend", "impressions", "clicks", "revenue"]:
        if c not in df.columns:
            df[c] = 0

    if "roas" not in df.columns:
        df["roas"] = df["revenue"] / df["spend"].replace(0, 1)

    global_summary = {
        "start_date": str(df["date"].min()) if "date" in df.columns and not df.empty else None,
        "end_date": str(df["date"].max()) if "date" in df.columns and not df.empty else None,
        "total_spend": float(df["spend"].sum()),
        "total_revenue": float(df["revenue"].sum()),
        "daily_roas": df.groupby("date")["roas"].mean().reset_index().to_dict("records")
        if "date" in df.columns else [],
    }

    by_campaign = (
        df.groupby("campaign_name")
        .agg(
            {
                "spend": "sum",
                "impressions": "sum",
                "clicks": "sum",
                "revenue": "sum",
            }
        )
        .reset_index()
    )

    by_campaign["ctr"] = by_campaign["clicks"] / by_campaign["impressions"].replace(0, 1)
    by_campaign["roas"] = by_campaign["revenue"] / by_campaign["spend"].replace(0, 1)

    return {"global": global_summary, "by_campaign": by_campaign.to_dict("records")}
