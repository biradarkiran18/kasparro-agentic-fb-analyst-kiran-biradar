# File: src/utils/schema.py
# Provides schema fingerprinting + drift detection + pre-run validation helpers.

from __future__ import annotations
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple


# Define expected schema for FB Ads data
EXPECTED_SCHEMA = {
    "required_columns": [
        "date",
        # Accept either 'campaign' or 'campaign_name'
        "spend",
        "impressions",
        "clicks",
        "revenue",
    ],
    "optional_columns": [
        "campaign",
        "campaign_name",
        "creative_id",
        "creative_message",
        "ad_set",
        "adset_name",
        "conversions",
        "purchases",
        "ctr",
        "roas",
        "platform",
        "country",
        "audience_type",
        "creative_type",
    ],
    "expected_dtypes": {
        "spend": ["float64", "float32", "int64", "int32"],
        "impressions": ["int64", "int32", "float64"],
        "clicks": ["int64", "int32", "float64"],
        "revenue": ["float64", "float32", "int64", "int32"],
    }
}


class SchemaValidationError(Exception):
    """Raised when schema validation fails."""
    pass


def _hash_schema(schema_dict: Dict[str, Any]) -> str:
    """
    Deterministic hash of the schema dictionary. Uses stable ordering.
    """
    # build canonical representation: list of (col, dtype) sorted by col
    items = sorted(
        [(str(k), str(v)) for k, v in schema_dict.get("dtypes", {}).items()]
    )
    s = json.dumps({"columns": sorted(schema_dict.get("columns", [])), "dtypes": items})
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def schema_from_frame_like(df_like: Any) -> Dict[str, Any]:
    """
    Create a minimal schema dict from a pandas-like object that has columns and dtypes.
    This helper keeps code resilient in tests/dry runs where a full DataFrame may not be present.
    """
    # avoid importing pandas at module import time in case tests stub frames
    try:
        cols = list(df_like.columns)
        dtypes = {c: str(df_like[c].dtype) for c in cols}
    except Exception:
        # fallback: if it's already a dict-like (tests may pass simple dict)
        try:
            cols = list(df_like.keys())
            dtypes = {c: "object" for c in cols}
        except Exception:
            cols = []
            dtypes = {}
    return {"columns": cols, "dtypes": dtypes}


def schema_fingerprint_from_df(df_like: Any) -> Dict[str, Any]:
    """
    Build a schema fingerprint dict from a DataFrame-like object.

    Returns:
      {
        "columns": [...],
        "dtypes": { col: dtype_str, ... },
        "hash": "<sha256>",
        "version": 1
      }
    """
    sch = schema_from_frame_like(df_like)
    h = _hash_schema(sch)
    out = {"columns": sch.get("columns", []), "dtypes": sch.get("dtypes", {}), "hash": h, "version": 1}
    return out


def fingerprint_and_write(df_like: Any, path: str = "reports/schema_fingerprint.json") -> str:
    """
    Compute fingerprint and write to `path`. Returns the path.
    Creates a minimal JSON object with fingerprint information.
    """
    fp = schema_fingerprint_from_df(df_like)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(fp, fh, indent=2, default=str)
    except Exception:
        # swallow write errors (orchestrator should handle) but re-raise for visibility
        raise
    return path


def read_schema_fingerprint(path: str) -> Optional[Dict[str, Any]]:
    """
    Read fingerprint JSON from path. Returns None if not present/readable.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def detect_schema_drift(old_fp: Dict[str, Any], new_fp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare two fingerprint dicts and return a drift report.

    Report format:
      {
        "drift": bool,
        "diff": {
          "added": [cols],
          "removed": [cols],
          "dtype_changes": { col: { "from": old_dtype, "to": new_dtype }, ... }
        }
      }
    """
    old_cols = set(old_fp.get("columns", []) if isinstance(old_fp, dict) else [])
    new_cols = set(new_fp.get("columns", []) if isinstance(new_fp, dict) else [])

    added = sorted(list(new_cols - old_cols))
    removed = sorted(list(old_cols - new_cols))

    dtype_changes: Dict[str, Dict[str, Any]] = {}
    old_dtypes = old_fp.get("dtypes", {}) if isinstance(old_fp, dict) else {}
    new_dtypes = new_fp.get("dtypes", {}) if isinstance(new_fp, dict) else {}

    for c in sorted(list(old_cols & new_cols)):
        old_dt = str(old_dtypes.get(c, "unknown"))
        new_dt = str(new_dtypes.get(c, "unknown"))
        if old_dt != new_dt:
            dtype_changes[c] = {"from": old_dt, "to": new_dt}

    drift = bool(added or removed or dtype_changes)

    return {"drift": drift, "diff": {"added": added, "removed": removed, "dtype_changes": dtype_changes}}


def validate_schema(df_like: Any, strict: bool = True) -> Tuple[bool, List[str]]:
    """
    Validate that a DataFrame matches the expected schema.

    Args:
        df_like: DataFrame-like object to validate
        strict: If True, raise SchemaValidationError on failure

    Returns:
        (is_valid, error_messages)

    Raises:
        SchemaValidationError: If strict=True and validation fails
    """
    errors = []

    try:
        cols = set(df_like.columns)
    except Exception as e:
        errors.append(f"Cannot access columns: {e}")
        if strict:
            raise SchemaValidationError(f"Schema validation failed: {errors}")
        return False, errors

    # Check required columns
    required = set(EXPECTED_SCHEMA["required_columns"])
    missing = required - cols

    # Special case: campaign_name can substitute for campaign
    if "campaign" in missing and "campaign_name" in cols:
        missing.discard("campaign")

    if missing:
        error_msg = (
            f"Missing required columns: {sorted(missing)}. "
            f"Required columns are: {sorted(required)}. "
            f"Found columns: {sorted(cols)}"
        )
        errors.append(error_msg)

    # Check data types for key columns
    for col, expected_types in EXPECTED_SCHEMA["expected_dtypes"].items():
        if col in cols:
            try:
                actual_dtype = str(df_like[col].dtype)
                if actual_dtype not in expected_types:
                    errors.append(
                        f"Column '{col}' has dtype '{actual_dtype}', "
                        f"expected one of {expected_types}"
                    )
            except Exception as e:
                errors.append(f"Cannot check dtype for column '{col}': {e}")

    # Check for empty DataFrame
    try:
        if len(df_like) == 0:
            errors.append("DataFrame is empty (0 rows)")
    except Exception:
        pass

    is_valid = len(errors) == 0

    if not is_valid and strict:
        raise SchemaValidationError(
            f"Schema validation failed with {len(errors)} error(s):\n" +
            "\n".join(f"  - {e}" for e in errors)
        )

    return is_valid, errors
