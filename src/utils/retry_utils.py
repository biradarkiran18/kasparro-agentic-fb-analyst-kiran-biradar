from typing import Any, Dict, List


def compute_extra_aggregates(df) -> Dict[str, Any]:
    # minimal safe extra aggregates for retry/augmentation
    try:
        rows = len(df)
        total_spend = float(df["spend"].sum()) if "spend" in df.columns else 0.0
    except Exception:
        rows = 0
        total_spend = 0.0
    return {"rows": rows, "total_spend": total_spend}


def apply_retry_logic(validated: List[Dict[str, Any]], extra: Dict[str, Any]) -> List[Dict[str, Any]]:
    # If small dataset and low confidence, nudge confidence upward slightly
    out = []
    for v in validated:
        v2 = dict(v)
        if extra.get("rows", 0) < 50 and v2.get("final_confidence", 0) < 0.6:
            v2["final_confidence"] = min(0.6, v2.get("final_confidence", 0) + 0.1)
            v2.setdefault("notes", []).append("confidence_adjusted_for_small_sample")
        out.append(v2)
    return out
