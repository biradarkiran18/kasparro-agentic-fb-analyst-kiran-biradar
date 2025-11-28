import pandas as pd
from typing import Optional


def load_data(
    path: str,
    sample_mode: bool = False,
    sample_size: int = 5000,
    chunksize: Optional[int] = None,
) -> pd.DataFrame:
    """
    Load CSV data.

    Args:
        path: CSV path
        sample_mode: if True, return a deterministic sample of `sample_size`
        sample_size: number of rows to sample when sample_mode is True
        chunksize: if provided, read in chunks and concatenate (useful for large files)

    Returns:
        DataFrame with parsed dates
    """
    if chunksize:
        parts = []
        for chunk in pd.read_csv(path, parse_dates=["date"], chunksize=chunksize):
            parts.append(chunk)
        df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    else:
        df = pd.read_csv(path, parse_dates=["date"])

    # Basic defensive shape
    if df is None or df.shape[0] == 0:
        # return empty well-formed dataframe
        cols = [
            "date",
            "campaign_name",
            "adset_name",
            "spend",
            "impressions",
            "clicks",
            "purchases",
            "revenue",
            "creative_message",
        ]
        return pd.DataFrame(columns=cols)

    if sample_mode:
        # deterministic sample: use head if dataset smaller than sample_size
        if df.shape[0] <= sample_size:
            df = df.copy().reset_index(drop=True)
        else:
            df = df.sample(n=sample_size, random_state=42).reset_index(drop=True)

    # ensure numeric columns exist
    for col in ["spend", "impressions", "clicks", "purchases", "revenue"]:
        if col not in df.columns:
            df[col] = 0

    # ensure date dtype
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def summarize(df: pd.DataFrame):
    """
    Produce a summary dict expected by downstream agents/tests.
    Ensures 'global' and 'by_campaign' keys always exist.
    """
    # defensive: empty df
    if df is None or df.shape[0] == 0:
        return {
            "global": {
                "start_date": None,
                "end_date": None,
                "total_spend": 0.0,
                "total_revenue": 0.0,
                "daily_roas": [],
            },
            "by_campaign": [],
        }

    # safe arithmetic
    df["spend"] = pd.to_numeric(df.get("spend", 0), errors="coerce").fillna(0)
    df["revenue"] = pd.to_numeric(df.get("revenue", 0), errors="coerce").fillna(0)
    df["impressions"] = pd.to_numeric(df.get("impressions", 0), errors="coerce").fillna(0)
    df["clicks"] = pd.to_numeric(df.get("clicks", 0), errors="coerce").fillna(0)

    # compute roas per-row where possible
    df["roas"] = df["revenue"] / df["spend"].replace(0, 1)

    total_spend = float(df["spend"].sum())
    total_revenue = float(df["revenue"].sum())

    daily_roas = (
        df.groupby("date")["roas"].mean().reset_index().to_dict("records")
        if "date" in df.columns and not df["date"].isnull().all()
        else []
    )

    global_summary = {
        "start_date": str(df["date"].min()) if "date" in df.columns and not df["date"].isnull().all() else None,
        "end_date": str(df["date"].max()) if "date" in df.columns and not df["date"].isnull().all() else None,
        "total_spend": total_spend,
        "total_revenue": total_revenue,
        "daily_roas": daily_roas,
    }

    by_campaign = (
        df.groupby("campaign_name")
        .agg(
            {
                "spend": "sum",
                "impressions": "sum",
                "clicks": "sum",
                "purchases": "sum",
                "revenue": "sum",
            }
        )
        .reset_index()
    )

    # safe computations for ctr and roas
    if not by_campaign.empty:
        by_campaign["ctr"] = (
            by_campaign["clicks"] / by_campaign["impressions"].replace(0, 1)
        )
        by_campaign["roas"] = (
            by_campaign["revenue"] / by_campaign["spend"].replace(0, 1)
        )
    else:
        by_campaign = by_campaign.assign(ctr=[], roas=[])

    return {"global": global_summary, "by_campaign": by_campaign.to_dict("records")}
