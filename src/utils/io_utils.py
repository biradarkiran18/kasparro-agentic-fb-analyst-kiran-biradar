import json
import os
from typing import Any, Optional
import pandas as pd


def load_csv(path: str, chunksize: Optional[int] = None, **kwargs) -> Optional[pd.DataFrame]:
    """
    Load a CSV file into a pandas DataFrame.

    Args:
        path: Path to CSV file
        chunksize: If specified, load in chunks and concatenate (for large files)
        **kwargs: Additional arguments to pass to pd.read_csv

    Returns:
        DataFrame or None if file doesn't exist
    """
    if not os.path.exists(path):
        return None
    try:
        # If chunksize specified, load in chunks
        if chunksize and chunksize > 0:
            chunks = []
            for chunk in pd.read_csv(path, chunksize=chunksize, **kwargs):
                chunks.append(chunk)
            return pd.concat(chunks, ignore_index=True) if chunks else None
        else:
            return pd.read_csv(path, **kwargs)
    except Exception:
        return None


def write_json(path: str, obj: Any) -> str:
    """Write JSON object to file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)
    return path
