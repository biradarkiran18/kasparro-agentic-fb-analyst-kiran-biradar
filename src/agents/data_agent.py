import hashlib
import json
import os
from typing import Dict, Generator, Optional

import pandas as pd


SCHEMA_FINGERPRINT_PATH = "reports/schema_fingerprint.json"


def _file_fingerprint(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: str, obj: Dict):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)


def load_data(path: str, sample_mode: bool = False, sample_size: int = 5000, chunksize: Optional[int] = None) -> pd.DataFrame:
    """
    Load CSV with safety checks, optional sample mode or streaming via chunksize.
    Returns a DataFrame. If chunksize provided, reads and concatenates in memory but in chunks.
    """
    try:
        if chunksize:
            frames = []
            for chunk in pd.read_csv(path, parse_dates=["date"], chunksize=chunksize):
                frames.append(chunk)
            df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        else:
            df = pd.read_csv(path, parse_dates=["date"])
    except Exception as e:
        raise RuntimeError(f"failed reading CSV {path}: {e}")

    required = {"date", "campaign_name", "spend", "impressions", "clicks", "revenue"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"missing required columns: {missing}")

    # normalize numeric columns
    for col in ("spend", "impressions", "clicks", "revenue"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # sample option
    if sample_mode and len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42).reset_index(drop=True)

    df["roas"] = df["revenue"] / df["spend"].replace(0, 1)

    # schema fingerprinting & drift detection (write current fingerprint)
    try:
        fingerprint = {
            "schema_columns": sorted(list(df.columns)),
            "row_count": int(len(df)),
            "file_hash": _file_fingerprint(path),
        }
        _write_json(SCHEMA_FINGERPRINT_PATH, fingerprint)
    except Exception:
        # do not break pipeline for fingerprint errors
        pass

    return df


def summarize(df: pd.DataFrame) -> Dict:
    df["roas"] = pd.to_numeric(df.get("roas", df["revenue"] / df["spend"].replace(0, 1)), errors="coerce").fillna(0.0)

    global_summary = {
        "start_date": str(df["date"].min()) if not df["date"].isnull().all() else None,
        "end_date": str(df["date"].max()) if not df["date"].isnull().all() else None,
        "total_spend": float(df["spend"].sum()),
        "total_revenue": float(df["revenue"].sum()),
        "daily_roas": df.groupby("date")["roas"].mean().reset_index().to_dict("records"),
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
