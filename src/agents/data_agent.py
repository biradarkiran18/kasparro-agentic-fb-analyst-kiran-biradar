"""
Data agent: load data, compute lightweight summary, compute schema fingerprint.

Responsibilities:
- Read CSV (or other sources) robustly with comprehensive error handling
- Validate schema pre-processing
- Produce `summary` object used by downstream agents:
    {
      "global": {"total_spend": x, "daily_roas": [{date, roas}, ...], "num_creatives": n},
      "by_campaign": [{ "campaign": "...", "spend": x, "ctr": y, "impressions": i, "clicks": c}, ...]
    }
- Handle missing columns, NaN values, empty groups gracefully
- Optionally write schema fingerprint (reports/schema_fingerprint.json)
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
import numpy as np

import pandas as pd

from src.utils.schema import fingerprint_and_write, validate_schema
from src.utils.observability import log_event

_DEFAULT_DATE_COL = "date"


def load_csv_safe(path: str, *, date_col: str = _DEFAULT_DATE_COL, chunksize: Optional[int] = None) -> pd.DataFrame:
    """
    Load a CSV defensively with comprehensive error handling.

    Handles:
    - File not found
    - Parse errors
    - Date conversion issues
    - Missing columns
    - Large files with chunked loading (if chunksize specified)

    Args:
        path: Path to CSV file
        date_col: Name of date column to parse
        chunksize: If specified, load file in chunks and combine (for large files)

    Returns:
        DataFrame with loaded data
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Data file not found: {path}")

    try:
        # If chunksize specified, load in batches
        if chunksize and chunksize > 0:
            log_event("data_agent", "chunked_loading_start", {
                "path": path,
                "chunksize": chunksize
            })

            chunks = []
            chunk_count = 0

            try:
                for chunk in pd.read_csv(path, chunksize=chunksize):
                    chunks.append(chunk)
                    chunk_count += 1

                    if chunk_count % 10 == 0:
                        log_event("data_agent", "chunk_loaded", {
                            "chunk_number": chunk_count,
                            "rows_so_far": sum(len(c) for c in chunks)
                        })

                df = pd.concat(chunks, ignore_index=True)

                log_event("data_agent", "chunked_loading_complete", {
                    "total_chunks": chunk_count,
                    "total_rows": len(df)
                })
            except Exception as e:
                log_event("data_agent", "chunked_loading_error", {"error": str(e)})
                # Fallback to regular loading
                df = pd.read_csv(path)
        else:
            # Regular single-read loading
            df = pd.read_csv(path)

    except pd.errors.EmptyDataError:
        raise ValueError(f"CSV file is empty: {path}")
    except pd.errors.ParserError as e:
        log_event("data_agent", "parse_error", {"path": path, "error": str(e)})
        # try with more permissive options
        try:
            df = pd.read_csv(path, low_memory=False, on_bad_lines='skip')
        except Exception as e2:
            raise ValueError(f"Failed to parse CSV {path}: {e2}")
    except Exception as e:
        raise ValueError(f"Failed to load CSV {path}: {e}")

    # Validate schema
    try:
        is_valid, errors = validate_schema(df, strict=False)
        if not is_valid:
            log_event("data_agent", "schema_validation_warning", {
                "path": path,
                "errors": errors
            })
    except Exception as e:
        log_event("data_agent", "schema_validation_error", {"error": str(e)})

    # coerce date if present
    if date_col in df.columns:
        try:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            # Count and log NaT values
            nat_count = df[date_col].isna().sum()
            if nat_count > 0:
                log_event("data_agent", "date_conversion_warning", {
                    "nat_count": int(nat_count),
                    "total_rows": len(df)
                })
        except Exception as e:
            log_event("data_agent", "date_conversion_error", {"error": str(e)})

    return df


def summarize_df(df: pd.DataFrame, *, date_col: str = _DEFAULT_DATE_COL) -> Dict[str, Any]:
    """
    Compute a minimal summary used by insight & evaluator agents.

    Handles:
    - Missing columns gracefully
    - NaN/infinity values
    - Empty groups
    - Division by zero
    """
    out: Dict[str, Any] = {"global": {}, "by_campaign": [], "data_quality": {}}

    # Track data quality metrics
    quality = {
        "total_rows": len(df),
        "columns_present": list(df.columns),
        "missing_values": {},
    }

    try:
        # Check for missing values in key columns
        key_cols = ["spend", "revenue", "impressions", "clicks", "campaign"]
        for col in key_cols:
            if col in df.columns:
                missing_count = int(df[col].isna().sum())
                if missing_count > 0:
                    quality["missing_values"][col] = missing_count

        # global totals - handle missing columns gracefully
        spend = float(df["spend"].sum()) if "spend" in df.columns else 0.0
        revenue = float(df["revenue"].sum()) if "revenue" in df.columns else 0.0
        impressions = int(df["impressions"].sum()) if "impressions" in df.columns else 0
        clicks = int(df["clicks"].sum()) if "clicks" in df.columns else 0

        # Replace NaN and inf with 0
        spend = 0.0 if (np.isnan(spend) or np.isinf(spend)) else spend
        revenue = 0.0 if (np.isnan(revenue) or np.isinf(revenue)) else revenue

        out["global"]["total_spend"] = spend
        out["global"]["total_revenue"] = revenue
        out["global"]["total_impressions"] = impressions
        out["global"]["total_clicks"] = clicks
        out["global"]["num_creatives"] = int(df["creative_id"].nunique()) if "creative_id" in df.columns else None

        # daily roas series (sorted)
        if date_col in df.columns and "spend" in df.columns and "revenue" in df.columns:
            try:
                # Filter out NaT dates
                df_clean = df[df[date_col].notna()].copy()

                daily = (
                    df_clean.groupby(pd.Grouper(key=date_col, freq="D"))
                    .agg({"spend": "sum", "revenue": "sum"})
                    .reset_index()
                    .sort_values(date_col)
                )

                # Safe division for ROAS
                daily["roas"] = daily.apply(
                    lambda r: float(r["revenue"] / r["spend"]) if (r["spend"]
                                                                   > 0 and not np.isnan(r["spend"])) else 0.0,
                    axis=1
                )

                # Filter out invalid ROAS values
                daily = daily[daily["roas"].notna() & ~np.isinf(daily["roas"])]

                out["global"]["daily_roas"] = [
                    {"date": str(d[date_col].date()), "roas": float(d["roas"])}
                    for _, d in daily.iterrows()
                ]
            except Exception as e:
                log_event("data_agent", "daily_roas_error", {"error": str(e)})
                out["global"]["daily_roas"] = []
        else:
            out["global"]["daily_roas"] = []

        # by-campaign aggregation with robust error handling
        # Handle both 'campaign' and 'campaign_name' columns
        campaign_col = None
        if "campaign" in df.columns:
            campaign_col = "campaign"
        elif "campaign_name" in df.columns:
            campaign_col = "campaign_name"

        if campaign_col:
            try:
                # Remove rows with NaN campaign names
                df_campaign = df[df[campaign_col].notna()].copy()

                if len(df_campaign) == 0:
                    log_event("data_agent", "empty_campaigns", {"message": "No valid campaign data after filtering"})
                    out["by_campaign"] = []
                else:
                    grp = (
                        df_campaign.groupby(campaign_col)
                        .agg({
                            "spend": "sum" if "spend" in df.columns else lambda x: 0,
                            "impressions": "sum" if "impressions" in df.columns else lambda x: 0,
                            "clicks": "sum" if "clicks" in df.columns else lambda x: 0,
                            "revenue": "sum" if "revenue" in df.columns else lambda x: 0,
                        })
                        .reset_index()
                    )

                    rows: List[Dict[str, Any]] = []
                    for _, r in grp.iterrows():
                        impressions_i = int(r.get("impressions", 0) or 0)
                        clicks_i = int(r.get("clicks", 0) or 0)
                        spend_i = float(r.get("spend", 0.0) or 0.0)
                        revenue_i = float(r.get("revenue", 0.0) or 0.0)

                        # Safe CTR calculation
                        ctr = float(clicks_i / impressions_i) if impressions_i > 0 else 0.0
                        # Safe ROAS calculation
                        roas = float(revenue_i / spend_i) if spend_i > 0 else 0.0

                        # Filter out NaN/inf
                        ctr = 0.0 if (np.isnan(ctr) or np.isinf(ctr)) else ctr
                        roas = 0.0 if (np.isnan(roas) or np.isinf(roas)) else roas

                        rows.append(
                            {
                                "campaign": str(r.get(campaign_col, "")),
                                "spend": spend_i,
                                "impressions": impressions_i,
                                "clicks": clicks_i,
                                "ctr": ctr,
                                "revenue": revenue_i,
                                "roas": roas,
                            }
                        )
                    # sort by spend desc
                    out["by_campaign"] = sorted(rows, key=lambda x: x.get("spend", 0.0), reverse=True)
            except Exception as e:
                log_event("data_agent", "campaign_aggregation_error", {"error": str(e)})
                out["by_campaign"] = []
        else:
            out["by_campaign"] = []

        out["data_quality"] = quality

    except Exception as e:
        # if summarization fails, return safe defaults and log
        log_event("data_agent", "summarize_error", {"error": str(e)})
        out["global"]["daily_roas"] = []
        out["by_campaign"] = []
        out["data_quality"] = quality

    return out


def load_and_summarize(
    path: str,
    *,
    write_schema_fp: bool = True,
    schema_path: str = "reports/schema_fingerprint.json",
    date_col: Optional[str] = None,
    chunksize: Optional[int] = None,
    base_dir: str = "logs/observability",
) -> Dict[str, Any]:
    """
    Load data, write schema fingerprint if requested, and return summary.

    Args:
        path: Path to CSV file
        write_schema_fp: Whether to write schema fingerprint
        schema_path: Path for schema fingerprint output
        date_col: Name of date column
        chunksize: If specified, load file in chunks (for large files)
        base_dir: Base directory for logs

    Returns:
        Summary dict
    """
    base_dir = base_dir or "logs/observability"
    log_event("data_agent", "load_started", {"path": path, "chunksize": chunksize}, base_dir=base_dir)

    date_col = date_col or _DEFAULT_DATE_COL
    df = load_csv_safe(path, date_col=date_col, chunksize=chunksize)

    # write schema fingerprint (best-effort)
    try:
        if write_schema_fp:
            fingerprint_and_write(df, schema_path)
    except Exception as e:
        log_event("data_agent", "schema_write_error", {"error": str(e)}, base_dir=base_dir)

    summary = summarize_df(df, date_col=date_col)
    log_event("data_agent", "load_completed", {"rows": len(df),
              "summary_keys": list(summary.keys())}, base_dir=base_dir)
    return summary


def summarize_data(df: pd.DataFrame, cfg: Dict[str, Any], *, base_dir: str = "logs/observability") -> Dict[str, Any]:
    """
    Wrapper for summarize_df to match orchestrator's expected signature.
    Used by orchestrator when df is already loaded.
    """
    date_col = cfg.get("date_col", _DEFAULT_DATE_COL)
    return summarize_df(df, date_col=date_col)


# Backward-compatible aliases for tests
def load_data(path: str, *, sample_mode: bool = False, **kwargs) -> pd.DataFrame:
    """Backward-compatible wrapper for tests."""
    # Remove sample_size from kwargs if present (not supported by load_csv_safe)
    kwargs.pop('sample_size', None)
    return load_csv_safe(path, **kwargs)


def summarize(df: pd.DataFrame, *, date_col: str = _DEFAULT_DATE_COL) -> Dict[str, Any]:
    """Backward-compatible wrapper for tests."""
    return summarize_df(df, date_col=date_col)
