from typing import Dict, Any
import pandas as pd
import numpy as np


def _safe_date_index(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Ensure dataframe has a cleaned, sorted datetime index."""
    if date_col in df.columns:
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])
        df = df.sort_values(date_col)
    return df


def compute_global_ctr_baseline(
    df: pd.DataFrame,
    date_col: str = "date",
    impressions_col: str = "impressions",
    clicks_col: str = "clicks",
    window_days: int = 30,
    min_days: int = 7,
    z_score: float = 1.5,
) -> Dict[str, Any]:
    """
    Compute a baseline and low-CTR threshold from historical CTR values.
    """
    df = _safe_date_index(df)

    if (
        date_col not in df.columns
        or impressions_col not in df.columns
        or clicks_col not in df.columns
    ):
        return {
            "baseline_ctr": 0.0,
            "ctr_std": 0.0,
            "ctr_low_threshold": 0.01,
            "rows_used": 0,
        }

    daily = (
        df.groupby(pd.Grouper(key=date_col, freq="D"))
        .agg({impressions_col: "sum", clicks_col: "sum"})
        .reset_index()
    )

    daily["ctr"] = daily[clicks_col] / daily[impressions_col].replace(0, np.nan)
    daily = daily.dropna(subset=["ctr"])
    rows_used = len(daily)

    if rows_used < min_days:
        agg_impr = df[impressions_col].sum()
        agg_clicks = df[clicks_col].sum()
        baseline = float(agg_clicks / agg_impr) if agg_impr > 0 else 0.0

        return {
            "baseline_ctr": baseline,
            "ctr_std": 0.0,
            "ctr_low_threshold": max(1e-6, baseline * 0.5),
            "rows_used": rows_used,
        }

    last_cut = daily[date_col].max() - pd.Timedelta(days=window_days)
    window = daily[daily[date_col] > last_cut] if rows_used > window_days else daily

    baseline = float(window["ctr"].mean())
    std = float(window["ctr"].std(ddof=0) if len(window) > 1 else 0.0)

    threshold = baseline - z_score * std
    threshold = max(threshold, max(1e-6, baseline * 0.3))

    return {
        "baseline_ctr": baseline,
        "ctr_std": std,
        "ctr_low_threshold": float(threshold),
        "rows_used": rows_used,
    }


def compute_roas_drop_threshold(
    df: pd.DataFrame,
    date_col: str = "date",
    revenue_col: str = "revenue",
    spend_col: str = "spend",
    window_days: int = 30,
    min_days: int = 7,
    z_score: float = 1.0,
    min_threshold: float = 0.08,
) -> Dict[str, Any]:
    """
    Compute a threshold for identifying significant ROAS drops.
    """
    df = _safe_date_index(df)

    if (
        date_col not in df.columns
        or revenue_col not in df.columns
        or spend_col not in df.columns
    ):
        return {
            "median_drop": 0.0,
            "drop_std": 0.0,
            "roas_drop_threshold": min_threshold,
            "rows_used": 0,
        }

    daily = (
        df.groupby(pd.Grouper(key=date_col, freq="D"))
        .agg({revenue_col: "sum", spend_col: "sum"})
        .reset_index()
    )
    daily["roas"] = daily[revenue_col] / daily[spend_col].replace(0, np.nan)
    daily = daily.dropna(subset=["roas"])
    rows_used = len(daily)

    if rows_used < min_days:
        return {
            "median_drop": 0.0,
            "drop_std": 0.0,
            "roas_drop_threshold": min_threshold,
            "rows_used": rows_used,
        }

    roas = daily["roas"].astype(float).reset_index(drop=True)
    prev = roas.shift(1)

    drops = ((prev - roas) / prev.replace(0, np.nan)).dropna()
    drops = drops[drops > 0]

    if drops.empty:
        return {
            "median_drop": 0.0,
            "drop_std": 0.0,
            "roas_drop_threshold": min_threshold,
            "rows_used": rows_used,
        }

    median_drop = float(drops.median())
    drop_std = float(drops.std(ddof=0) if len(drops) > 1 else 0.0)

    threshold = median_drop + z_score * drop_std
    threshold = max(threshold, min_threshold)

    return {
        "median_drop": median_drop,
        "drop_std": drop_std,
        "roas_drop_threshold": float(threshold),
        "rows_used": rows_used,
    }


def compute_dynamic_thresholds(
    df: pd.DataFrame,
    *,
    window_days: int = 30,
    min_days: int = 7,
    ctr_z: float = 1.5,
    roas_z: float = 1.0,
) -> Dict[str, Any]:
    """
    Compute both CTR baseline and ROAS-drop threshold.
    """
    ctr = compute_global_ctr_baseline(
        df,
        window_days=window_days,
        min_days=min_days,
        z_score=ctr_z,
    )

    roas = compute_roas_drop_threshold(
        df,
        window_days=window_days,
        min_days=min_days,
        z_score=roas_z,
    )

    return {
        "ctr_baseline": ctr,
        "roas_baseline": roas,
        "ctr_low_threshold": ctr["ctr_low_threshold"],
        "roas_drop_threshold": roas["roas_drop_threshold"],
        "rows_used": max(ctr["rows_used"], roas["rows_used"]),
    }
