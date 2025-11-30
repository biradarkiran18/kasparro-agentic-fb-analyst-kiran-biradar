# src/utils/schema.py
import hashlib
import json
import os
from typing import Any, Dict
import pandas as pd


def _column_dtype_name(series: Any) -> str:
    try:
        return str(series.dtype)
    except Exception:
        return type(series).__name__


def schema_fingerprint_from_df(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Build a stable fingerprint for a DataFrame schema.
    Returns:
      {
        "columns": [{"name": <col>, "dtype": <dtype_str>}, ...],  # sorted by name
        "hash": "<sha256 hex>"
      }
    """
    cols = []
    for col in sorted(df.columns.tolist()):
        series = df[col]
        dtype_name = _column_dtype_name(series)
        cols.append({"name": col, "dtype": dtype_name})

    fingerprint = {"columns": cols}
    canonical = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    fingerprint["hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return fingerprint


def detect_schema_drift(base_fp: Dict[str, Any], comp_fp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare two schema fingerprints and return:
      { "drift": bool,
        "diff": {
          "added": [col_names present in comp but not in base],
          "removed": [col_names present in base but not in comp],
          "dtype_changes": { col: {"from": dtype1, "to": dtype2}, ... }
        }
      }
    """
    base_cols = {c["name"]: c.get("dtype") for c in base_fp.get("columns", [])}
    comp_cols = {c["name"]: c.get("dtype") for c in comp_fp.get("columns", [])}

    added = sorted([c for c in comp_cols.keys() if c not in base_cols])
    removed = sorted([c for c in base_cols.keys() if c not in comp_cols])

    dtype_changes = {}
    for col in sorted(set(base_cols.keys()).intersection(comp_cols.keys())):
        from_dt = base_cols.get(col)
        to_dt = comp_cols.get(col)
        if (from_dt or "") != (to_dt or ""):
            dtype_changes[col] = {"from": from_dt, "to": to_dt}

    drift = bool(added or removed or dtype_changes)
    return {"drift": drift, "diff": {"added": added, "removed": removed, "dtype_changes": dtype_changes}}


def fingerprint_and_write(df: pd.DataFrame, path: str = "reports/schema_fingerprint.json") -> Dict[str, Any]:
    """
    Compute fingerprint from DataFrame and write it to `path` (creates dirs).
    Returns the fingerprint dict.
    """
    fp = schema_fingerprint_from_df(df)
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fp, f, indent=2, sort_keys=True, ensure_ascii=False)
    return fp


def read_schema_fingerprint(path: str = "reports/schema_fingerprint.json") -> Dict[str, Any]:
    """
    Read fingerprint JSON from `path`. If file missing or invalid, return empty fingerprint structure.
    """
    if not os.path.exists(path):
        return {"columns": [], "hash": ""}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"columns": [], "hash": ""}
