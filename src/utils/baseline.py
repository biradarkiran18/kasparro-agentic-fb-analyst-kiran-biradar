# File: src/utils/baseline.py
# Compute baseline statistics (CTR, ROAS) and produce evidence merges.

from __future__ import annotations
from typing import Any, Dict
import pandas as pd
import numpy as np


def _safe_date_index(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    if date_col in df.columns:
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])
        df = df.sort_values(date_col)
    return df


def compute_global_baselines(
    df: pd.DataFrame,
    date_col: str = "date",
    impressions_col: str = "impressions",
    clicks_col: str = "clicks",
    revenue_col: str = "revenue",
    spend_col: str = "spend",
    window_days: int = 30,
) -> Dict[str, Any]:
    """
    Compute baseline statistics for CTR and ROAS over a historical window.

    Returns a dict with baselines and percentiles and rows_used.
    """
    df = _safe_date_index(df)
    if date_col not in df.columns:
        return {
            "ctr_baseline": 0.0,
            "ctr_pctile_10": 0.0,
            "ctr_pctile_90": 0.0,
            "roas_baseline": 0.0,
            "roas_pctile_10": 0.0,
            "roas_pctile_90": 0.0,
            "rows_used": 0,
        }

    daily = (
        df.groupby(pd.Grouper(key=date_col, freq="D"))
        .agg({impressions_col: "sum", clicks_col: "sum", revenue_col: "sum", spend_col: "sum"})
        .reset_index()
    )

    daily["ctr"] = daily[clicks_col] / daily[impressions_col].replace(0, np.nan)
    daily["roas"] = daily[revenue_col] / daily[spend_col].replace(0, np.nan)
    daily = daily.dropna(subset=["ctr", "roas"])
    rows_used = len(daily)

    if rows_used == 0:
        return {
            "ctr_baseline": 0.0,
            "ctr_pctile_10": 0.0,
            "ctr_pctile_90": 0.0,
            "roas_baseline": 0.0,
            "roas_pctile_10": 0.0,
            "roas_pctile_90": 0.0,
            "rows_used": 0,
        }

    if rows_used > window_days and "date" in daily.columns:
        last_cut = daily["date"].max() - pd.Timedelta(days=window_days)
        window = daily[daily["date"] > last_cut]
    else:
        window = daily

    ctr_vals = window["ctr"].astype(float).dropna()
    roas_vals = window["roas"].astype(float).dropna()

    def _safe_stats(arr: pd.Series):
        if arr.empty:
            return 0.0, 0.0, 0.0
        baseline = float(arr.mean())
        p10 = float(np.percentile(arr, 10))
        p90 = float(np.percentile(arr, 90))
        return baseline, p10, p90

    ctr_baseline, ctr_p10, ctr_p90 = _safe_stats(ctr_vals)
    roas_baseline, roas_p10, roas_p90 = _safe_stats(roas_vals)

    return {
        "ctr_baseline": ctr_baseline,
        "ctr_pctile_10": ctr_p10,
        "ctr_pctile_90": ctr_p90,
        "roas_baseline": roas_baseline,
        "roas_pctile_10": roas_p10,
        "roas_pctile_90": roas_p90,
        "rows_used": rows_used,
    }


def evidence_from_summary_and_baseline(summary: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge summary + baseline into a compact evidence object.

    Computes percent deltas for CTR and ROAS comparing the latest value
    to the baseline. Handles missing values safely.
    """
    last_roas = 0.0
    last_ctr = 0.0

    try:
        daily = summary.get("global", {}).get("daily_roas", [])
        if daily:
            last_roas = float(daily[-1].get("roas", 0.0))
    except Exception:
        last_roas = 0.0

    try:
        by_campaign = summary.get("by_campaign", []) or []
        tot_impr = sum(int(c.get("impressions", 0)) for c in by_campaign)
        tot_clicks = sum(int(c.get("clicks", 0)) for c in by_campaign)
        if tot_impr > 0:
            last_ctr = tot_clicks / tot_impr
    except Exception:
        last_ctr = last_ctr or 0.0

    def _pct_delta(latest: float, baseline_val: float) -> float:
        try:
            if baseline_val == 0:
                return 0.0 if latest == 0 else float("inf")
            return (latest - baseline_val) / baseline_val
        except Exception:
            return 0.0

    ctr_delta_pct = _pct_delta(last_ctr, baseline.get("ctr_baseline", 0.0))
    roas_delta_pct = _pct_delta(last_roas, baseline.get("roas_baseline", 0.0))

    ev = {
        "last_ctr": float(last_ctr),
        "ctr_baseline": float(baseline.get("ctr_baseline", 0.0)),
        "ctr_delta_pct": float(ctr_delta_pct),
        "last_roas": float(last_roas),
        "roas_baseline": float(baseline.get("roas_baseline", 0.0)),
        "roas_delta_pct": float(roas_delta_pct),
        "rows_used_for_baseline": int(baseline.get("rows_used", 0)),
    }
    return ev
